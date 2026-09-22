# backend/taxes/tasks.py

import logging

from celery import shared_task
from django.utils import timezone

from integrations.kra import KRAClient

logger = logging.getLogger(__name__)


@shared_task
def generate_rental_income_return(landlord_id: str, period_start=None, period_end=None):
    """
    Aggregates a landlord's confirmed rent Payments for the period into
    a RentalIncomeReturn (idempotent per landlord+period via the model's
    unique_together) and attempts submission to KRA. Submission is
    expected to raise NotImplementedError until real KRA API access
    exists (see integrations/kra.py) — that leaves the return recorded
    and PENDING rather than failing the whole pipeline, same pattern as
    the WhatsApp Pay Rent flow before real Daraja access existed.
    """
    from billing.models import Payment
    from landlords.models import Landlord

    from .models import MRI_TAX_RATE, RentalIncomeReturn, RentalIncomeReturnStatus

    period_start = period_start or timezone.now().replace(day=1).date()
    period_end = period_end or timezone.now().date()

    try:
        landlord = Landlord.objects.get(id=landlord_id)
    except Landlord.DoesNotExist:
        logger.error("generate_rental_income_return: no landlord %s", landlord_id)
        return None

    payments = Payment.objects.filter(
        landlord_credential__landlord=landlord,
        received_at__date__gte=period_start,
        received_at__date__lte=period_end,
    )
    gross_rental_income = sum((p.amount for p in payments), 0)
    if gross_rental_income <= 0:
        logger.info("No rental income for landlord %s in %s–%s — skipping return.", landlord, period_start, period_end)
        return None

    tax_due = round(float(gross_rental_income) * MRI_TAX_RATE, 2)

    # PENDING and NOT_CONFIGURED are the only "not yet filed" states — a
    # return that's already SUBMITTED/ACCEPTED/REJECTED must never be
    # touched again by a later re-run for the same period.
    mutable_statuses = {RentalIncomeReturnStatus.PENDING, RentalIncomeReturnStatus.NOT_CONFIGURED}

    tax_return, created = RentalIncomeReturn.objects.get_or_create(
        landlord=landlord,
        period_start=period_start,
        period_end=period_end,
        defaults={"gross_rental_income": gross_rental_income, "tax_due": tax_due},
    )
    if not created:
        if tax_return.status not in mutable_statuses:
            logger.info("Return for landlord %s period %s–%s already %s — leaving as-is.", landlord, period_start, period_end, tax_return.status)
            return tax_return
        if tax_return.gross_rental_income != gross_rental_income:
            # Re-running for the same period (e.g. a late payment landed)
            # — keep figures current as long as it hasn't been filed yet.
            tax_return.gross_rental_income = gross_rental_income
            tax_return.tax_due = tax_due
            tax_return.save(update_fields=["gross_rental_income", "tax_due"])

    credential = getattr(landlord, "kra_credential", None)
    if credential is None:
        if tax_return.status != RentalIncomeReturnStatus.NOT_CONFIGURED:
            tax_return.status = RentalIncomeReturnStatus.NOT_CONFIGURED
            tax_return.save(update_fields=["status"])
        logger.info("Landlord %s has no KRA credential configured — return left unfiled.", landlord)
        return tax_return

    client = KRAClient.for_landlord(credential)
    try:
        result = client.submit_rental_income_return(
            period_start=str(period_start),
            period_end=str(period_end),
            gross_rental_income=str(gross_rental_income),
            tax_due=str(tax_due),
        )
    except NotImplementedError:
        logger.info(
            "KRA filing stubbed (pending real KRA API access) — landlord=%s period=%s–%s tax_due=%s",
            landlord, period_start, period_end, tax_due,
        )
        return tax_return

    tax_return.status = RentalIncomeReturnStatus.SUBMITTED
    tax_return.kra_reference = result.kra_reference
    tax_return.submitted_at = timezone.now()
    tax_return.save(update_fields=["status", "kra_reference", "submitted_at"])
    return tax_return


@shared_task
def generate_all_landlord_rental_income_returns():
    """Celery Beat entry point — fans out per landlord, monthly."""
    from landlords.models import Landlord

    for landlord in Landlord.objects.all():
        generate_rental_income_return.delay(str(landlord.id))
