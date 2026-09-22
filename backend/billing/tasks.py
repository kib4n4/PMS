# backend/billing/tasks.py

import logging
from decimal import ROUND_HALF_UP, Decimal

from celery import shared_task
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from accounts.phone import normalize_msisdn
from integrations.daraja import DarajaClient, DarajaError
from landlords.models import LandlordDarajaCredential

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")


def _platform_fee_rate() -> Decimal:
    # Still a single global rate — see settings.PLATFORM_FEE_RATE.
    # TODO(Phase 4+): make this configurable per organization/landlord rather than flat.
    return Decimal(str(settings.PLATFORM_FEE_RATE))


def _money(value) -> Decimal:
    """Money must never touch binary float — Decimal all the way from the
    DB field through to the rounded fee amount."""
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _resolve_invoice(credential, account_reference: str, msisdn: str = ""):
    """
    Resolve which open Invoice a payment belongs to. Reference match
    (the AccountReference we set when initiating STK Push, or whatever
    the tenant typed manually via the Paybill menu) is authoritative;
    phone-number match is the fallback for reference typos/omissions.
    """
    from billing.models import Invoice, InvoiceStatus

    base_qs = Invoice.objects.filter(lease__unit__property__landlord=credential.landlord).exclude(
        status=InvoiceStatus.PAID
    )

    if account_reference:
        invoice = base_qs.filter(reference__iexact=account_reference.strip()).first()
        if invoice:
            return invoice

    if msisdn:
        invoice = (
            base_qs.filter(lease__tenant__user__phone_number=normalize_msisdn(msisdn))
            .order_by("due_date")
            .first()
        )
        if invoice:
            return invoice

    return None


def _record_payment(*, invoice, credential, amount, transaction_id: str, raw_payload: dict, checkout_request_id: str = ""):
    """
    Shared by both inbound-payment paths (C2B confirmation and STK Push
    callback): idempotently create the Payment + FeeLedgerEntry, refresh
    the Invoice's status from real payment totals, and queue the receipt
    email.

    Idempotency: the DB-level unique constraint on
    Payment.mpesa_transaction_id is the real safety net against two
    near-simultaneous deliveries of the same Safaricom callback (which it
    explicitly retries) both passing the pre-check below before either
    commits — the `IntegrityError` that constraint raises in that race is
    caught and treated as "someone else already recorded it," not an
    error.
    """
    from billing.models import FeeLedgerEntry, Payment

    if Payment.objects.filter(mpesa_transaction_id=transaction_id).exists():
        logger.info("Duplicate payment callback for %s — already recorded, skipping.", transaction_id)
        return None

    try:
        with transaction.atomic():
            payment = Payment.objects.create(
                invoice=invoice,
                landlord_credential=credential,
                amount=amount,
                mpesa_transaction_id=transaction_id,
                mpesa_checkout_request_id=checkout_request_id,
                raw_callback_payload=raw_payload,
            )
            platform_fee_amount = _money(Decimal(str(amount)) * _platform_fee_rate())

            reseller = credential.landlord.referred_by
            reseller_commission_amount = Decimal("0")
            if reseller:
                rule = reseller.commission_rules.filter(landlord=credential.landlord).first()
                if rule and (rule.is_perpetual or (rule.expires_at and rule.expires_at > timezone.now())):
                    reseller_commission_amount = _money(
                        platform_fee_amount * Decimal(str(rule.rate_percent)) / Decimal("100")
                    )

            FeeLedgerEntry.objects.create(
                payment=payment,
                platform_fee_amount=platform_fee_amount,
                reseller_commission_amount=reseller_commission_amount,
                reseller=reseller,
            )
    except IntegrityError:
        logger.info("Payment %s lost a create race — another delivery recorded it first, skipping.", transaction_id)
        return None

    invoice.refresh_status()
    send_payment_receipt_email.delay(str(payment.id))
    logger.info(
        "Recorded payment %s for landlord %s against invoice %s, fee %s",
        transaction_id, credential.landlord, invoice.reference, platform_fee_amount,
    )
    return payment


@shared_task
def ingest_c2b_confirmation(raw_payload: dict):
    """
    Entry point for the shared C2B webhook (manual Paybill-menu payments,
    or any STK-Push-initiated payment on a shortcode that ALSO has C2B
    validation/confirmation URLs registered). Discriminates by shortcode
    to resolve the landlord, then by AccountReference/MSISDN to resolve
    the Invoice.
    """
    shortcode = raw_payload.get("BusinessShortCode")
    transaction_id = raw_payload.get("TransID")
    amount = raw_payload.get("TransAmount")
    account_reference = raw_payload.get("BillRefNumber", "")
    msisdn = raw_payload.get("MSISDN", "")

    if not (shortcode and transaction_id and amount):
        logger.warning("Malformed C2B payload, missing required fields: %s", raw_payload)
        return

    try:
        credential = LandlordDarajaCredential.objects.get(shortcode=shortcode)
    except LandlordDarajaCredential.DoesNotExist:
        logger.error("C2B confirmation for unknown shortcode %s", shortcode)
        return

    invoice = _resolve_invoice(credential, account_reference, msisdn)
    if invoice is None:
        logger.error(
            "No matching open invoice for payment %s (landlord=%s, ref=%s, msisdn=%s)",
            transaction_id, credential.landlord, account_reference, msisdn,
        )
        return

    _record_payment(
        invoice=invoice, credential=credential, amount=amount,
        transaction_id=transaction_id, raw_payload=raw_payload,
    )


@shared_task
def ingest_stk_callback(raw_payload: dict):
    """
    Entry point for the STK Push CallBackURL. Shape:
      {"Body": {"stkCallback": {
          "MerchantRequestID", "CheckoutRequestID", "ResultCode", "ResultDesc",
          "CallbackMetadata": {"Item": [{"Name": "Amount", "Value": ...}, ...]}
      }}}
    Unlike C2B, this does NOT echo back the AccountReference — correlation
    is via CheckoutRequestID against the STKPushRequest we persisted at
    initiation time (billing/api_views.py).
    """
    from billing.models import STKPushRequest, STKPushRequestStatus

    stk_callback = (raw_payload.get("Body") or {}).get("stkCallback") or {}
    checkout_request_id = stk_callback.get("CheckoutRequestID")
    result_code = stk_callback.get("ResultCode")
    result_desc = stk_callback.get("ResultDesc", "")

    if checkout_request_id is None or result_code is None:
        logger.warning("Malformed STK callback payload: %s", raw_payload)
        return

    # select_for_update + the PENDING re-check inside the same transaction
    # closes the race two near-simultaneous deliveries of the same
    # callback would otherwise hit: both reading PENDING before either
    # writes SUCCESS/FAILED. The second delivery now blocks on the row
    # lock until the first commits, then sees the already-resolved status.
    with transaction.atomic():
        try:
            stk_request = STKPushRequest.objects.select_for_update().select_related(
                "invoice", "landlord_credential", "fee_invoice"
            ).get(checkout_request_id=checkout_request_id)
        except STKPushRequest.DoesNotExist:
            logger.error("STK callback for unknown CheckoutRequestID %s", checkout_request_id)
            return

        if stk_request.status != STKPushRequestStatus.PENDING:
            logger.info("Duplicate STK callback for %s — already resolved, skipping.", checkout_request_id)
            return

        if result_code != 0:
            stk_request.status = STKPushRequestStatus.FAILED
            stk_request.result_description = result_desc
            stk_request.resolved_at = timezone.now()
            stk_request.save(update_fields=["status", "result_description", "resolved_at"])
            logger.info("STK push %s failed/cancelled: %s", checkout_request_id, result_desc)
            return

        items = {
            item.get("Name"): item.get("Value")
            for item in (stk_callback.get("CallbackMetadata") or {}).get("Item", [])
        }
        transaction_id = items.get("MpesaReceiptNumber")
        amount = items.get("Amount")

        if not (transaction_id and amount):
            logger.error("STK callback %s missing MpesaReceiptNumber/Amount: %s", checkout_request_id, raw_payload)
            return

        if stk_request.fee_invoice_id:
            success = _record_fee_invoice_payment(stk_request.fee_invoice, transaction_id)
        else:
            payment = _record_payment(
                invoice=stk_request.invoice,
                credential=stk_request.landlord_credential,
                amount=amount,
                transaction_id=transaction_id,
                raw_payload=raw_payload,
                checkout_request_id=checkout_request_id,
            )
            success = payment is not None

        stk_request.status = STKPushRequestStatus.SUCCESS if success else STKPushRequestStatus.FAILED
        stk_request.result_description = result_desc
        stk_request.resolved_at = timezone.now()
        stk_request.save(update_fields=["status", "result_description", "resolved_at"])


def _record_fee_invoice_payment(fee_invoice, transaction_id: str) -> bool:
    """Platform-fee side of the STK callback — a landlord paying down
    their FeeInvoice via the platform's own shortcode. No Payment/
    FeeLedgerEntry here (those model tenant->landlord rent, not
    landlord->platform fee); just marks the FeeInvoice paid."""
    if fee_invoice.mpesa_transaction_id == transaction_id:
        logger.info("Duplicate fee invoice payment callback for %s — already recorded.", transaction_id)
        return True
    fee_invoice.mark_paid(mpesa_transaction_id=transaction_id)
    logger.info("FeeInvoice %s marked paid via STK push, transaction %s", fee_invoice.id, transaction_id)
    return True


@shared_task
def send_payment_receipt_email(payment_id: str):
    """Emails the payment receipt (PDF attached) to the tenant, if they have an email on file."""
    from billing.models import Payment
    from billing.pdf import render_receipt_pdf
    from integrations.resend_client import EmailAttachment, ResendClient, ResendError
    from messaging.models import EmailMessage

    try:
        payment = Payment.objects.select_related("invoice__lease__tenant__user").get(id=payment_id)
    except Payment.DoesNotExist:
        logger.error("send_payment_receipt_email: no payment %s", payment_id)
        return

    tenant = payment.invoice.lease.tenant
    tenant_email = tenant.user.email
    if not tenant_email:
        logger.info("No email on file for tenant %s — skipping receipt email for payment %s", tenant.id, payment.mpesa_transaction_id)
        return

    subject = f"Payment received — {payment.invoice.reference}"
    html = (
        f"<p>Hi {tenant.full_name},</p>"
        f"<p>We've recorded your payment of <strong>KES {payment.amount:,.2f}</strong> "
        f"for invoice {payment.invoice.reference} (M-Pesa transaction {payment.mpesa_transaction_id}).</p>"
        f"<p>Your receipt is attached.</p>"
    )

    record = EmailMessage.objects.create(
        to_email=tenant_email, subject=subject, body=html,
        related_object_type="Payment", related_object_id=str(payment.id),
    )
    try:
        result = ResendClient.default().send_email(
            to=tenant_email, subject=subject, html=html,
            attachments=[EmailAttachment(filename=f"receipt-{payment.mpesa_transaction_id}.pdf", content=render_receipt_pdf(payment))],
        )
    except ResendError:
        logger.exception("Failed to send receipt email for payment %s", payment.mpesa_transaction_id)
        record.delivery_status = "failed"
        record.save(update_fields=["delivery_status"])
        return

    record.delivery_status = "sent"
    record.resend_message_id = result.id
    record.save(update_fields=["delivery_status", "resend_message_id"])


@shared_task
def generate_fee_invoices(period_start=None, period_end=None):
    """
    Rolls up un-invoiced FeeLedgerEntry rows per landlord into a single
    FeeInvoice for the period. Scheduled monthly via Celery Beat (see
    messaging/management/commands/seed_periodic_tasks.py).

    Entries are scoped to payments actually received within
    [period_start, period_end] — an entry from outside that window stays
    un-invoiced and gets picked up by whichever future run's window
    covers it, rather than being invoiced regardless of when the
    underlying payment landed.
    """
    from billing.models import FeeInvoice, FeeLedgerEntry
    from landlords.models import Landlord

    period_start = period_start or timezone.now().replace(day=1).date()
    period_end = period_end or timezone.now().date()

    landlord_ids = (
        FeeLedgerEntry.objects.filter(
            invoiced=False,
            payment__received_at__date__gte=period_start,
            payment__received_at__date__lte=period_end,
        )
        .values_list("payment__landlord_credential__landlord_id", flat=True)
        .distinct()
    )

    for landlord in Landlord.objects.filter(id__in=landlord_ids):
        entries = FeeLedgerEntry.objects.filter(
            payment__landlord_credential__landlord=landlord,
            invoiced=False,
            payment__received_at__date__gte=period_start,
            payment__received_at__date__lte=period_end,
        )
        total = entries.aggregate(total=Sum("platform_fee_amount"))["total"] or Decimal("0")
        if total <= 0:
            continue

        with transaction.atomic():
            fee_invoice = FeeInvoice.objects.create(
                landlord=landlord,
                period_start=period_start,
                period_end=period_end,
                total_amount=total,
            )
            fee_invoice.ledger_entries.set(entries)
            entries.update(invoiced=True)

        logger.info("Generated FeeInvoice %s for landlord %s, total %s", fee_invoice.id, landlord, total)


@shared_task
def reconcile_landlord_transactions(landlord_credential_id: str, window_hours: int = 48):
    """
    Nightly, per-landlord reconciliation: for every Payment recorded in
    the last `window_hours`, ask Safaricom's Transaction Status API to
    confirm it independently rather than trusting our own callback record
    alone. Like B2C, this API is asynchronous — query_transaction_status
    only returns an acknowledgment; the actual answer lands later on
    /webhooks/mpesa/transactionstatus/result/
    (billing/webhook_views.py::mpesa_transaction_status_result), which is
    where a real mismatch gets logged for admin review.
    """
    from billing.models import Payment

    try:
        credential = LandlordDarajaCredential.objects.get(id=landlord_credential_id)
    except LandlordDarajaCredential.DoesNotExist:
        logger.error("reconcile_landlord_transactions: no credential %s", landlord_credential_id)
        return

    client = DarajaClient.for_landlord(credential)
    window_start = timezone.now() - timezone.timedelta(hours=window_hours)
    recent_payments = Payment.objects.filter(landlord_credential=credential, received_at__gte=window_start)

    checked = 0
    for payment in recent_payments:
        try:
            client.query_transaction_status(payment.mpesa_transaction_id)
            checked += 1
        except DarajaError:
            logger.exception(
                "reconcile_landlord_transactions: query failed for payment %s (landlord=%s)",
                payment.mpesa_transaction_id, credential.landlord,
            )

    logger.info(
        "Reconciliation queried %s/%s recent payments for %s",
        checked, recent_payments.count(), credential.shortcode,
    )


@shared_task
def reconcile_all_landlords():
    """Celery Beat entry point — fans out reconciliation per landlord."""
    for credential in LandlordDarajaCredential.objects.filter(status="live"):
        reconcile_landlord_transactions.delay(str(credential.id))


@shared_task
def log_transaction_status_result(raw_payload: dict):
    """
    Receives the async answer to a query_transaction_status call fired
    from reconcile_landlord_transactions. A non-zero ResultCode is the
    actual "discrepancy" reconciliation exists to catch — persisted as an
    AuditLog entry (reused from the audit app, not a bespoke discrepancy
    model) so it's queryable/actionable from the admin instead of only
    ever a log line that scrolls away.
    """
    from audit.models import AuditLog

    result = raw_payload.get("Result", {})
    result_code = result.get("ResultCode")

    if result_code == 0:
        logger.info("Transaction status reconciliation OK: %s", result.get("ResultDesc"))
        return

    logger.error("Transaction status reconciliation MISMATCH/FAILURE: %s", result)
    AuditLog.objects.create(
        actor=None,
        action="reconciliation_mismatch",
        target_object_type="Payment",
        target_object_id=str(result.get("TransactionID", "unknown")),
        reason=result.get("ResultDesc", "Transaction status query returned a non-zero ResultCode."),
        metadata={"result_code": result_code, "raw_result": result},
    )


@shared_task
def log_transaction_status_timeout(raw_payload: dict):
    logger.error("Transaction status query timed out: %s", raw_payload)
