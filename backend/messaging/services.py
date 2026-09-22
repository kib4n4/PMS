# backend/messaging/services.py

import logging
from typing import Optional

from accounts.phone import normalize_msisdn
from billing.models import Invoice, InvoiceStatus
from billing.services import (
    InvoiceAlreadyPaidError,
    LandlordNotReadyError,
    NoDarajaCredentialError,
    initiate_invoice_payment,
)
from integrations.daraja import DarajaError
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


class TemplateNotApprovedError(Exception):
    """No APPROVED NotificationTemplate exists for the requested name."""


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
