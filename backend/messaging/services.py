# backend/messaging/services.py

import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from accounts.models import Role, User
from accounts.phone import normalize_msisdn
from billing.models import Invoice, InvoiceStatus
from billing.services import (
    InvoiceAlreadyPaidError,
    LandlordNotReadyError,
    NoDarajaCredentialError,
    initiate_invoice_payment,
)
from integrations.daraja import DarajaError
from landlords.models import Landlord
from leasing.models import Lease, LeaseStatus, Tenant
from properties.models import Property, Unit

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


class TemplateNotApprovedError(Exception):
    """No APPROVED NotificationTemplate exists for the requested name."""


class InvalidOnboardingPayloadError(ValueError):
    """Raised when a landlord onboarding payload is malformed."""


def resolve_approved_template(name: str):
    from .models import NotificationTemplate, TemplateApprovalStatus

    template = (
        NotificationTemplate.objects.filter(name=name, approval_status=TemplateApprovalStatus.APPROVED)
        .order_by("-version")
        .first()
    )
    if template is None:
        raise TemplateNotApprovedError(f"No approved NotificationTemplate named '{name}'.")
    return template


def find_tenant_by_phone(phone_number: str):
    # Meta's webhook sends bare-digit MSISDNs ("254711...", no "+"), but
    # User.phone_number is stored E.164 ("+254711...") — without this,
    # every inbound WhatsApp message from a real tenant fails to match.
    return Tenant.objects.select_related("user").filter(user__phone_number=normalize_msisdn(phone_number)).first()


def find_landlord_by_phone(phone_number: str):
    normalized = normalize_msisdn(phone_number)
    return (Landlord.objects.select_related("user", "organization").filter(user__phone_number=normalized).first())


def find_role_by_phone(phone_number: str):
    normalized = normalize_msisdn(phone_number)
    tenant = Tenant.objects.select_related("user").filter(user__phone_number=normalized).first()
    if tenant is not None:
        return "tenant", tenant

    landlord = Landlord.objects.select_related("user", "organization").filter(user__phone_number=normalized).first()
    if landlord is not None:
        return "landlord", landlord

    return "unknown", None


def _split_onboarding_payload(payload: str) -> list[str]:
    candidate = payload.strip()
    if candidate.lower().startswith("onboard tenant:"):
        candidate = candidate.split(":", 1)[1].strip()
    elif candidate.lower().startswith("add tenant:"):
        candidate = candidate.split(":", 1)[1].strip()

    if not candidate:
        raise InvalidOnboardingPayloadError("Missing onboarding details.")

    pieces = [part.strip() for part in re.split(r"\|\s*|\n\s*|\s*,\s*", candidate) if part and part.strip()]
    if len(pieces) < 6:
        raise InvalidOnboardingPayloadError(
            "Expected format: Name | Phone | Property | Unit | Rent | Start Date | End Date"
        )
    return pieces


def onboard_tenant_for_landlord(landlord: Landlord, payload: str) -> dict:
    """Create a tenant + lease for a landlord from a WhatsApp message.

    Supported format:
      onboard tenant: Jane Doe | +254712345678 | Blue House | A1 | 25000 | 2026-11-01 | 2027-11-01
    """
    chunks = _split_onboarding_payload(payload)
    if len(chunks) < 6:
        raise InvalidOnboardingPayloadError(
            "Expected format: Name | Phone | Property | Unit | Rent | Start Date | End Date"
        )

    name = chunks[0]
    phone_number = normalize_msisdn(chunks[1])
    property_name = chunks[2]
    unit_label = chunks[3]
    try:
        rent_amount = Decimal(chunks[4])
    except InvalidOperation as exc:
        raise InvalidOnboardingPayloadError("Rent must be a valid number.") from exc

    try:
        start_date = date.fromisoformat(chunks[5])
    except ValueError as exc:
        raise InvalidOnboardingPayloadError("Start date must be in YYYY-MM-DD format.") from exc

    end_date = None
    if len(chunks) >= 7:
        try:
            end_date = date.fromisoformat(chunks[6])
        except ValueError as exc:
            raise InvalidOnboardingPayloadError("End date must be in YYYY-MM-DD format.") from exc

    property_obj = landlord.properties.filter(name__iexact=property_name).first()
    if property_obj is None:
        raise InvalidOnboardingPayloadError(f"No property named '{property_name}' was found for this landlord.")

    unit = property_obj.units.filter(label__iexact=unit_label).first()
    if unit is None:
        unit = Unit.objects.create(property=property_obj, label=unit_label, status="vacant")

    user, _ = User.objects.get_or_create(
        username=f"tenant-{phone_number.replace('+', '').replace(' ', '')}",
        defaults={
            "phone_number": phone_number,
            "role": Role.TENANT,
            "is_phone_verified": True,
        },
    )
    if not user.phone_number:
        user.phone_number = phone_number
        user.role = Role.TENANT
        user.is_phone_verified = True
        user.save(update_fields=["phone_number", "role", "is_phone_verified"])

    tenant, _ = Tenant.objects.get_or_create(
        user=user,
        defaults={"full_name": name},
    )
    tenant.full_name = name
    tenant.save(update_fields=["full_name"])

    active_lease = Lease.objects.filter(tenant=tenant, unit=unit, status=LeaseStatus.ACTIVE).first()
    if active_lease:
        active_lease.rent_amount = rent_amount
        active_lease.billing_day = 1
        active_lease.start_date = start_date
        active_lease.end_date = end_date
        active_lease.save(update_fields=["rent_amount", "billing_day", "start_date", "end_date"])
        lease = active_lease
    else:
        lease = Lease.objects.create(
            unit=unit,
            tenant=tenant,
            rent_amount=rent_amount,
            billing_day=1,
            deposit_amount=0,
            status=LeaseStatus.ACTIVE,
            start_date=start_date,
            end_date=end_date,
        )

    return {
        "ok": True,
        "tenant_id": str(tenant.id),
        "lease_id": str(lease.id),
        "property_name": property_obj.name,
        "unit_label": unit.label,
        "rent_amount": str(rent_amount),
        "tenant_name": tenant.full_name,
    }


def find_active_lease_for_tenant(tenant: Tenant) -> Optional[Lease]:
    return (
        Lease.objects.filter(tenant=tenant, status=LeaseStatus.ACTIVE)
        .select_related("unit", "unit__property")
        .first()
    )


def find_caretaker_for_tenant(tenant: Tenant):
    """The currently-active CaretakerAssignment for the tenant's
    property, if any — 'currently active' means effective_end is null."""
    from caretakers.models import CaretakerAssignment

    lease = find_active_lease_for_tenant(tenant)
    if lease is None:
        return None

    assignment = (
        CaretakerAssignment.objects.filter(property=lease.unit.property, effective_end__isnull=True)
        .select_related("caretaker__user")
        .order_by("-effective_start")
        .first()
    )
    return assignment.caretaker if assignment else None


def create_maintenance_ticket_for_tenant(tenant: Tenant, description: str, whatsapp_thread_ref: str = ""):
    """Reported-via-WhatsApp maintenance tickets start unassigned —
    whoever assigns a caretaker later (admin/landlord) triggers the
    notification in maintenance/signals.py, so this function doesn't
    need to know about notification delivery at all."""
    from maintenance.models import MaintenanceTicket

    lease = find_active_lease_for_tenant(tenant)
    if lease is None:
        raise NoActiveLeaseError(f"No active lease for tenant {tenant.id}")

    return MaintenanceTicket.objects.create(
        unit=lease.unit, tenant=tenant, description=description, whatsapp_thread_ref=whatsapp_thread_ref
    )


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


def trigger_stk_push_for_tenant(phone_number: str) -> dict:
    """
    Core of the WhatsApp 'Pay Rent' flow. Resolves the tenant's active
    lease and open invoice, then delegates to
    billing.services.initiate_invoice_payment — the SAME path the
    authenticated API uses, so the STKPushRequest correlation record
    that /webhooks/mpesa/stk/callback/ depends on always gets written,
    regardless of which entrypoint triggered the push.

    Returns a plain dict describing the outcome — never raises on the
    expected "not ready yet" paths (unknown tenant / no lease / no
    invoice / landlord not onboarded / Daraja request failed) since those
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
        stk_request = initiate_invoice_payment(invoice, phone_number)
    except (NoDarajaCredentialError, LandlordNotReadyError):
        return {"ok": False, "reason": "landlord_not_onboarded", "invoice_id": str(invoice.id)}
    except InvoiceAlreadyPaidError:
        return {"ok": False, "reason": "no_open_invoice", "invoice_id": str(invoice.id)}
    except DarajaError:
        logger.exception("STK Push failed for tenant %s invoice %s", tenant.id, invoice.id)
        return {"ok": False, "reason": "stk_push_failed", "invoice_id": str(invoice.id)}

    return {
        "ok": True,
        "invoice_id": str(invoice.id),
        "checkout_request_id": stk_request.checkout_request_id,
    }
