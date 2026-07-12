import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from integrations.daraja import DarajaClient
from landlords.models import LandlordDarajaCredential

logger = logging.getLogger(__name__)


@shared_task
def ingest_c2b_confirmation(raw_payload: dict):
    """
    Entry point for the shared C2B webhook. Discriminates by shortcode in
    the payload to resolve which landlord/invoice this belongs to, then
    idempotently records a Payment and its FeeLedgerEntry.

    Idempotency: the DB-level unique constraint on
    Payment.mpesa_transaction_id is the real safety net — this task must
    be safe to run twice for the same payload.
    """
    from billing.models import FeeLedgerEntry, Invoice, Payment

    shortcode = raw_payload.get("BusinessShortCode")
    transaction_id = raw_payload.get("TransData") or raw_payload.get("TransID")
    amount = raw_payload.get("TransAmount")
    account_reference = raw_payload.get("BillRefNumber")  # maps to Invoice/Lease

    if not (shortcode and transaction_id and amount):
        logger.warning("Malformed C2B payload, missing required fields: %s", raw_payload)
        return

    try:
        credential = LandlordDarajaCredential.objects.get(shortcode=shortcode)
    except LandlordDarajaCredential.DoesNotExist:
        logger.error("C2B confirmation for unknown shortcode %s", shortcode)
        return

    if Payment.objects.filter(mpesa_transaction_id=transaction_id).exists():
        logger.info("Duplicate C2B callback for %s — already recorded, skipping.", transaction_id)
        return

    # TODO(M2): resolve the correct open Invoice from account_reference.
    # Placeholder lookup shown for shape only.
    invoice = Invoice.objects.filter(lease__unit__property__landlord=credential.landlord).order_by(
        "-created_at"
    ).first()
    if invoice is None:
        logger.error("No matching invoice found for payment %s (ref %s)", transaction_id, account_reference)
        return

    with transaction.atomic():
        payment = Payment.objects.create(
            invoice=invoice,
            landlord_credential=credential,
            amount=amount,
            mpesa_transaction_id=transaction_id,
            raw_callback_payload=raw_payload,
        )
        # TODO(M2): pull the real platform fee rate from a configurable
        # per-organization/landlord setting rather than a flat constant.
        platform_fee_rate = 0.05
        platform_fee_amount = round(float(amount) * platform_fee_rate, 2)

        reseller = credential.landlord.referred_by
        reseller_commission_amount = 0
        if reseller:
            rule = reseller.commission_rules.filter(landlord=credential.landlord).first()
            if rule and (rule.is_perpetual or (rule.expires_at and rule.expires_at > timezone.now())):
                reseller_commission_amount = round(platform_fee_amount * float(rule.rate_percent) / 100, 2)

        FeeLedgerEntry.objects.create(
            payment=payment,
            platform_fee_amount=platform_fee_amount,
            reseller_commission_amount=reseller_commission_amount,
            reseller=reseller,
        )

    logger.info("Recorded payment %s for landlord %s, fee %s", transaction_id, credential.landlord, platform_fee_amount)


@shared_task
def generate_fee_invoices(period_start=None, period_end=None):
    """
    Rolls up un-invoiced FeeLedgerEntry rows per landlord into a single
    FeeInvoice for the period. Scheduled monthly via Celery Beat.
    """
    from billing.models import FeeInvoice, FeeLedgerEntry
    from landlords.models import Landlord

    period_start = period_start or timezone.now().replace(day=1).date()
    period_end = period_end or timezone.now().date()

    for landlord in Landlord.objects.all():
        entries = FeeLedgerEntry.objects.filter(
            payment__landlord_credential__landlord=landlord, invoiced=False
        )
        total = sum(e.platform_fee_amount for e in entries)
        if not entries.exists() or total <= 0:
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
def reconcile_landlord_transactions(landlord_credential_id: str):
    """
    Nightly, per-landlord reconciliation: cross-checks the fee ledger
    against Safaricom's own Transaction Status API using THAT landlord's
    credentials. Flags discrepancies for admin review rather than
    silently trusting callbacks alone.
    """
    try:
        credential = LandlordDarajaCredential.objects.get(id=landlord_credential_id)
    except LandlordDarajaCredential.DoesNotExist:
        logger.error("reconcile_landlord_transactions: no credential %s", landlord_credential_id)
        return

    client = DarajaClient.for_landlord(credential)
    # TODO(M2): fetch this landlord's Payments for the reconciliation
    # window, call client.query_transaction_status per transaction, and
    # raise an admin-visible discrepancy record for any mismatch.
    logger.info("Reconciliation stub ran for %s (client=%s)", credential.shortcode, client.environment)


@shared_task
def reconcile_all_landlords():
    """Celery Beat entry point — fans out reconciliation per landlord."""
    for credential in LandlordDarajaCredential.objects.filter(status="live"):
        reconcile_landlord_transactions.delay(str(credential.id))
