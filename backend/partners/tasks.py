# backend/partners/tasks.py

import logging

from celery import shared_task
from django.db import transaction

from integrations.daraja import DarajaClient

logger = logging.getLogger(__name__)

LOW_FLOAT_ALERT_THRESHOLD = 5000  # KES — placeholder, make configurable in M4


@shared_task
def sweep_reseller_payouts():
    """
    Scheduled (default monthly) B2C sweep paying each Reseller their
    accrued referral commission, funded from the PLATFORM's own Daraja
    app — never from a landlord's paybill or tenant rent directly.
    """
    from billing.models import FeeLedgerEntry
    from partners.models import Disbursement, DisbursementRecipientType, Reseller

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

        # TODO(M4): call client.initiate_b2c_payment(...) and update
        # disbursement.status/mpesa_conversation_id from the real result.
        logger.info("Queued reseller disbursement %s for %s (%s)", disbursement.id, reseller, total)


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
            # TODO(M4): compute the real revenue-share amount for this
            # agreement's scope/basis/period from actual fee revenue
            # figures rather than a placeholder.
            amount = _compute_revenue_share_amount(agreement)
            if amount <= 0:
                continue

            disbursement = Disbursement.objects.create(
                recipient_type=DisbursementRecipientType.INVESTOR,
                investor=investor,
                amount=amount,
            )
            # TODO(M4): call client.initiate_b2c_payment(...) and update
            # disbursement.status/mpesa_conversation_id from the real result.
            logger.info("Queued investor disbursement %s for %s (%s)", disbursement.id, investor, amount)


def _compute_revenue_share_amount(agreement) -> float:
    # TODO(M4): real computation against FeeInvoice/FeeLedgerEntry totals
    # scoped to agreement.organization (or portfolio-wide) and
    # agreement.basis (gross fee revenue vs net profit).
    return 0.0


def _check_platform_float(client: DarajaClient):
    # TODO(M4): query the platform's actual B2C-funding account balance
    # and alert admins if below LOW_FLOAT_ALERT_THRESHOLD before
    # attempting any payout in this sweep.
    pass