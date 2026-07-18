# backend/messaging/services.py

import logging

from billing.models import Invoice, InvoiceStatus
from integrations.daraja import DarajaClient
from landlords.models import LandlordDarajaCredential, OnboardingStatus
from leasing.models import Lease, LeaseStatus, Tenant

logger = logging.getLogger(__name__)

# Numbered-menu / interactive-button triggers for the "Pay Rent" intent.
# Kept as plain string matching for now — swap for a real NLU classifier
# only once there's enough real conversation data to justify it (see the
# design doc's anti-patterns note).
PAY_RENT_TRIGGERS = {"pay rent", "1", "pay_rent"}


class NoActiveLeaseError(Exception):
    pass


class NoOpenInvoiceError(Exception):
    pass


class LandlordNotReadyError(Exception):
    pass


def find_tenant_by_phone(phone_number: str):
    return Tenant.objects.select_related("user").filter(user__phone_number=phone_number).first()


def find_open_invoice_for_tenant(tenant: Tenant) -> Invoice:
    lease = (
        Lease.objects.filter(tenant=tenant, status=LeaseStatus.ACTIVE)
        .select_related("unit", "unit__property", "unit__property__landlord")
        .first()
    )
    if lease is None:
        raise NoActiveLeaseError(f"No active lease for tenant {tenant.id}")

    invoice = (
        Invoice.objects.filter(
            lease=lease,
            status__in=[InvoiceStatus.OPEN, InvoiceStatus.PARTIAL, InvoiceStatus.OVERDUE],
        )
        .order_by("due_date")
        .first()
    )
    if invoice is None:
        raise NoOpenInvoiceError(f"No open invoice for lease {lease.id}")
    return invoice


def resolve_landlord_credential(invoice: Invoice) -> LandlordDarajaCredential:
    """
    Option B: STK Push always goes through the LANDLORD's own shortcode,
    never a platform paybill. If the landlord hasn't completed onboarding
    (LandlordDarajaCredential missing or not yet live/sandbox-ready),
    that's a real, expected state — not an error to raise past this
    function.
    """
    landlord = invoice.lease.unit.property.landlord
    try:
        credential = landlord.daraja_credential
    except LandlordDarajaCredential.DoesNotExist:
        raise LandlordNotReadyError(f"Landlord {landlord.id} has no Daraja credential configured")

    if credential.status not in (OnboardingStatus.LIVE, OnboardingStatus.SANDBOX_TESTING):
        raise LandlordNotReadyError(f"Landlord {landlord.id} Daraja credential is not ready: {credential.status}")

    return credential


def trigger_stk_push_for_tenant(phone_number: str) -> dict:
    """
    Core of the WhatsApp 'Pay Rent' flow. Resolves the tenant's active
    lease and open invoice, resolves the landlord's own paybill
    credential, and triggers STK Push against it.

    Returns a plain dict describing the outcome — never raises on the
    expected "not ready yet" paths (unknown tenant / no lease / no
    invoice / landlord not onboarded / Daraja not yet wired) since those
    are user-facing states the caller needs to message back, not bugs.
    """
    tenant = find_tenant_by_phone(phone_number)
    if tenant is None:
        return {"ok": False, "reason": "unknown_tenant"}

    try:
        invoice = find_open_invoice_for_tenant(tenant)
    except NoActiveLeaseError:
        return {"ok": False, "reason": "no_active_lease"}
    except NoOpenInvoiceError:
        return {"ok": False, "reason": "no_open_invoice"}

    try:
        credential = resolve_landlord_credential(invoice)
    except LandlordNotReadyError:
        return {"ok": False, "reason": "landlord_not_onboarded"}

    client = DarajaClient.for_landlord(credential)
    try:
        result = client.initiate_stk_push(
            phone_number=phone_number,
            amount=str(invoice.amount_due),
            account_reference=str(invoice.id),
        )
    except NotImplementedError:
        # Expected until M2: real Daraja credentials/HTTP call aren't
        # wired yet. This is the intended state for a sandbox/dev
        # deployment right now, not a bug — log it plainly.
        logger.info(
            "STK Push stubbed (pending M2 live Daraja wiring) — tenant=%s invoice=%s shortcode=%s",
            tenant.id, invoice.id, credential.shortcode,
        )
        return {"ok": False, "reason": "stk_push_not_yet_live", "invoice_id": str(invoice.id)}

    return {
        "ok": True,
        "invoice_id": str(invoice.id),
        "checkout_request_id": result.checkout_request_id,
    }