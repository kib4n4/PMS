import logging

from celery import shared_task
from django.db import transaction

from integrations.daraja import DarajaClient, DarajaError

logger = logging.getLogger(__name__)

LOW_FLOAT_ALERT_THRESHOLD = 5000  # KES — placeholder, make configurable in a later phase


@shared_task
def sweep_reseller_payouts():
    """
    Scheduled (default monthly) B2C sweep paying each Reseller their
    accrued referral commission, funded from the PLATFORM's own Daraja
    app — never from a landlord's paybill or tenant rent directly.
    """
    from billing.models import FeeLedgerEntry
    from partners.models import Disbursement, DisbursementRecipientType, DisbursementStatus, Reseller

    client = DarajaClient.for_platform()
    _check_platform_float(client)

    for reseller in Reseller.objects.all():
        entries = FeeLedgerEntry.objects.filter(
            reseller=reseller, disbursements__isnull=True, reseller_commission_amount__gt=0
        )
        total = sum(e.reseller_commission_amount for e in entries)
        if total <= 0:
            continue

        with transaction.atomic():
            disbursement = Disbursement.objects.create(
                recipient_type=DisbursementRecipientType.RESELLER,
                reseller=reseller,
                amount=total,
            )
            disbursement.fee_ledger_entries.set(entries)

        _send_disbursement(client, disbursement, reseller.payout_account.phone_number, remarks="Reseller commission payout")


@shared_task
def sweep_investor_payouts():
    """
    Scheduled B2C sweep paying each Investor their accrued revenue share
    against their RevenueShareAgreement scope, funded from the platform's
    own collected fee revenue.
    """
    from partners.models import Disbursement, DisbursementRecipientType, Investor

    client = DarajaClient.for_platform()
    _check_platform_float(client)

    for investor in Investor.objects.all():
        for agreement in investor.agreements.all():
            # TODO(Phase 4+): real computation against FeeInvoice/
            # FeeLedgerEntry totals scoped to agreement.organization (or
            # portfolio-wide) and agreement.basis (gross fee revenue vs
            # net profit) — this is a revenue-accounting question
            # independent of the B2C payout plumbing being wired here.
            amount = _compute_revenue_share_amount(agreement)
            if amount <= 0:
                continue

            disbursement = Disbursement.objects.create(
                recipient_type=DisbursementRecipientType.INVESTOR,
                investor=investor,
                amount=amount,
            )
            _send_disbursement(client, disbursement, investor.payout_account.phone_number, remarks="Investor revenue share payout")


def _send_disbursement(client: DarajaClient, disbursement, phone_number: str, remarks: str):
    """Fires the B2C request and records the acknowledgment. The actual
    outcome (success/failure) arrives later on /webhooks/mpesa/b2c/result/
    (handle_b2c_result below) — a SENT status here means Safaricom
    accepted the request, not that money moved."""
    from partners.models import DisbursementStatus

    try:
        result = client.initiate_b2c_payment(
            phone_number=phone_number, amount=str(disbursement.amount), remarks=remarks,
        )
    except DarajaError:
        logger.exception("B2C initiation failed for disbursement %s", disbursement.id)
        disbursement.status = DisbursementStatus.FAILED
        disbursement.save(update_fields=["status"])
        return

    disbursement.status = DisbursementStatus.SENT
    disbursement.mpesa_conversation_id = result.conversation_id
    disbursement.save(update_fields=["status", "mpesa_conversation_id"])
    logger.info("Queued disbursement %s (%s) — conversation_id=%s", disbursement.id, disbursement.amount, result.conversation_id)


def _compute_revenue_share_amount(agreement) -> float:
    # TODO(Phase 4+): real computation — see sweep_investor_payouts note.
    return 0.0


def _check_platform_float(client: DarajaClient):
    # TODO(Phase 4+): query the platform's actual B2C-funding account
    # balance and alert admins if below LOW_FLOAT_ALERT_THRESHOLD before
    # attempting any payout in this sweep. Safaricom's Account Balance
    # API is itself async (result via a callback), same shape as
    # transaction status — worth its own webhook when this is built out.
    pass


@shared_task
def handle_b2c_result(raw_payload: dict):
    """
    B2C payout result callback. Shape:
      {"Result": {"ResultType", "ResultCode", "ResultDesc",
                  "OriginatorConversationID", "ConversationID",
                  "TransactionID", "ResultParameters": {...}}}
    Dedupes/resolves on ConversationID — the value we stored on the
    Disbursement when initiating.
    """
    from partners.models import Disbursement, DisbursementStatus

    result = raw_payload.get("Result", {})
    conversation_id = result.get("ConversationID")
    result_code = result.get("ResultCode")

    if conversation_id is None or result_code is None:
        logger.warning("Malformed B2C result payload: %s", raw_payload)
        return

    try:
        disbursement = Disbursement.objects.get(mpesa_conversation_id=conversation_id)
    except Disbursement.DoesNotExist:
        logger.error("B2C result for unknown ConversationID %s", conversation_id)
        return

    if disbursement.status == DisbursementStatus.CONFIRMED:
        logger.info("Duplicate B2C result for %s — already confirmed, skipping.", conversation_id)
        return

    disbursement.status = DisbursementStatus.CONFIRMED if result_code == 0 else DisbursementStatus.FAILED
    disbursement.save(update_fields=["status"])
    logger.info("B2C result for disbursement %s: %s", disbursement.id, disbursement.status)

    if disbursement.status == DisbursementStatus.CONFIRMED:
        _notify_payout_recipient(disbursement)


def _notify_payout_recipient(disbursement):
    """WhatsApp confirmation to whichever Reseller/Investor was just paid."""
    from messaging.tasks import send_whatsapp_reply

    recipient = disbursement.reseller or disbursement.investor
    if recipient is None:
        return
    phone_number = recipient.user.phone_number
    if not phone_number:
        logger.warning("Payout recipient %s has no phone number on file — cannot notify", recipient.id)
        return

    body = f"Payout confirmed: KES {disbursement.amount:,.2f} has been sent to your M-Pesa number."
    send_whatsapp_reply(
        phone_number, body, related_object_type="Disbursement", related_object_id=str(disbursement.id)
    )


@shared_task
def handle_b2c_timeout(raw_payload: dict):
    """B2C payout timed out without a result — mark FAILED so it surfaces
    for manual retry rather than sitting SENT forever."""
    from partners.models import Disbursement, DisbursementStatus

    result = raw_payload.get("Result", {})
    conversation_id = result.get("ConversationID")
    if not conversation_id:
        logger.warning("Malformed B2C timeout payload: %s", raw_payload)
        return

    updated = Disbursement.objects.filter(
        mpesa_conversation_id=conversation_id, status=DisbursementStatus.SENT
    ).update(status=DisbursementStatus.FAILED)
    if updated:
        logger.error("B2C payout %s timed out — marked FAILED for manual retry.", conversation_id)
    else:
        logger.warning("B2C timeout for %s but no matching SENT disbursement found.", conversation_id)
