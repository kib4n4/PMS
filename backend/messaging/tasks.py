# backend/messaging/tasks.py

import logging
from datetime import timedelta

import time

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from integrations.resend_client import ResendClient, ResendError
from integrations.twilio import TwilioClient, TwilioError
from integrations.whatsapp import WhatsAppClient, WhatsAppError

from . import services
from .models import EmailMessage, MessageDirection, WhatsAppDeliveryStatus, WhatsAppMessage

logger = logging.getLogger(__name__)

_MESSAGING_DOWN_BACKOFF_SECONDS = 60

REPORT_ISSUE_TRIGGERS = ("report issue", "report_issue", "issue", "2")
BALANCE_TRIGGERS = {"balance", "my balance", "3", "rent", "invoice"}
CARETAKER_TRIGGERS = {"caretaker", "talk to caretaker", "4"}


def _messaging_is_disabled(provider: str) -> bool:
    if provider == "whatsapp":
        return getattr(settings, "WHATSAPP_ENABLED", True) is False
    if provider == "twilio":
        return getattr(settings, "TWILIO_ENABLED", False) is False
    return False


def _record_provider_backoff(provider: str) -> None:
    cache.set(f"messaging-provider-backoff:{provider}", time.time() + _MESSAGING_DOWN_BACKOFF_SECONDS, timeout=_MESSAGING_DOWN_BACKOFF_SECONDS)


def _provider_is_in_backoff(provider: str) -> bool:
    expiry = cache.get(f"messaging-provider-backoff:{provider}")
    if not expiry:
        return False
    return float(expiry) > time.time()


def _friendly_service_failure_message(provider: str) -> str:
    return getattr(settings, "MESSAGE_SERVICE_DOWN_MESSAGE", "We’re temporarily experiencing delays with our messaging service. Please try again in a few minutes.")


def _resolve_outbound_client(provider: str):
    if provider == "twilio":
        return TwilioClient.default()
    return WhatsAppClient.default()


_TENANT_MENU = (
    "Welcome back. Reply with one of: "
    "'rent', 'invoice', 'lease', 'ticket', 'status', or 'help'."
)

_LANDLORD_MENU = (
    "Welcome landlord. Reply with one of: "
    "'onboard tenant: Name | Phone | Property | Unit | Rent | Start Date | End Date', "
    "'portfolio', 'tenants', 'status', 'help'."
)

_UNKNOWN_USER_MENU = (
    "Welcome to Dime PMS. We couldn't match this WhatsApp number to a registered tenant or landlord. "
    "To onboard a tenant, send: 'onboard tenant: Name | Phone | Property | Unit | Rent | Start Date | End Date'."
)

_PAY_RENT_OUTCOME_MESSAGES = {
    "unknown_tenant": "We couldn't find your tenant record — please contact your caretaker.",
    "no_active_lease": "You don't have an active lease on file — please contact your caretaker.",
    "no_open_invoice": "You're all caught up — no open invoice right now.",
    "landlord_not_onboarded": "Rent payment isn't set up for your property yet — please contact your caretaker.",
    "stk_push_failed": "We couldn't start your payment right now — please try again shortly.",
}


def send_whatsapp_reply(phone_number: str, body: str, related_object_type: str = "", related_object_id: str = ""):
    """
    Every outbound WhatsApp reply goes through here: write the audit
    record first (so we always have a trail even if the send itself
    fails), then attempt real delivery via the Cloud API and update the
    record's delivery_status with the outcome. Free-form session message
    only — works within Meta's 24h customer-initiated window; use
    send_whatsapp_template for anything outside that window.
    """
    message = WhatsAppMessage.objects.create(
        direction=MessageDirection.OUTBOUND,
        phone_number=phone_number,
        body=body,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
    )
    try:
        if _provider_is_in_backoff("whatsapp"):
            raise WhatsAppError("WhatsApp outbound is in temporary backoff.")
        if _messaging_is_disabled("whatsapp"):
            raise WhatsAppError("WhatsApp messaging is disabled.")
        result = WhatsAppClient.default().send_session_message(phone_number, body)
    except (WhatsAppError, TwilioError) as exc:
        logger.exception("Failed to send WhatsApp reply to %s", phone_number)
        _record_provider_backoff("whatsapp")
        message.delivery_status = WhatsAppDeliveryStatus.FAILED
        message.save(update_fields=["delivery_status"])
        return message
    message.delivery_status = WhatsAppDeliveryStatus.SENT
    message.meta_message_id = str(result.message_id)
    message.save(update_fields=["delivery_status", "meta_message_id"])
    return message


def send_whatsapp_template(
    phone_number: str, template_name: str, variables: dict, *, related_object_type: str = "", related_object_id: str = ""
):
    """
    Sends a pre-approved WhatsApp template message — unlike
    send_whatsapp_reply, works outside Meta's 24h session window, and
    (unlike every other send path today) actually sets
    WhatsAppMessage.template_used, which existed from day one but nothing
    ever populated. Raises services.TemplateNotApprovedError if no
    APPROVED version of `template_name` exists — callers decide whether
    that's fatal or skippable (see send_rent_reminders below).
    """
    template = services.resolve_approved_template(template_name)
    rendered_body = template.body
    for key, value in variables.items():
        rendered_body = rendered_body.replace(f"{{{{{key}}}}}", str(value))

    message = WhatsAppMessage.objects.create(
        direction=MessageDirection.OUTBOUND,
        phone_number=phone_number,
        template_used=template,
        body=rendered_body,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
    )
    try:
        if _provider_is_in_backoff("whatsapp"):
            raise WhatsAppError("WhatsApp outbound is in temporary backoff.")
        if _messaging_is_disabled("whatsapp"):
            raise WhatsAppError("WhatsApp messaging is disabled.")
        result = WhatsAppClient.default().send_template_message(phone_number, template.name, variables)
    except (WhatsAppError, TwilioError) as exc:
        logger.exception("Failed to send WhatsApp template %s to %s", template_name, phone_number)
        _record_provider_backoff("whatsapp")
        message.delivery_status = WhatsAppDeliveryStatus.FAILED
        message.save(update_fields=["delivery_status"])
        return message
    message.delivery_status = WhatsAppDeliveryStatus.SENT
    message.meta_message_id = str(result.message_id)
    message.save(update_fields=["delivery_status", "meta_message_id"])
    return message


@shared_task
def handle_whatsapp_status_update(message_id: str, status_value: str):
    """
    Meta's delivery-status webhook callback. Previously delivery_status
    was only ever set locally, once, at send time, based on whether our
    own HTTP call to Meta succeeded — never updated to reflect what
    actually happened on the wire (delivered/read/failed-per-Meta).
    """
    if status_value not in WhatsAppDeliveryStatus.values:
        logger.warning("handle_whatsapp_status_update: unrecognized status %r for %s", status_value, message_id)
        return

    updated = WhatsAppMessage.objects.filter(meta_message_id=message_id).update(delivery_status=status_value)
    if not updated:
        logger.info("handle_whatsapp_status_update: no message found for meta_message_id=%s", message_id)


def _handle_role_unknown(phone_number: str, body: str, normalized: str) -> dict:
    if normalized in {"hi", "hello", "start", "welcome"}:
        send_whatsapp_reply(phone_number, _UNKNOWN_USER_MENU)
        return {"ok": False, "reason": "unknown_role"}

    if normalized.startswith("onboard tenant") or normalized.startswith("add tenant"):
        send_whatsapp_reply(
            phone_number,
            "This WhatsApp number is not registered as a landlord yet. Please register a landlord account in the PMS before onboarding tenants.",
        )
        return {"ok": False, "reason": "missing_landlord_record"}

    if normalized in {"help", "menu"}:
        send_whatsapp_reply(phone_number, _UNKNOWN_USER_MENU)
        return {"ok": False, "reason": "unknown_role"}

    logger.info("Unclassified WhatsApp message from %s: %r", phone_number, body)
    send_whatsapp_reply(phone_number, _UNKNOWN_USER_MENU)
    return {"ok": False, "reason": "unclassified_intent"}


def _handle_tenant_message(phone_number: str, body: str, normalized: str) -> dict:
    if normalized in {"hi", "hello", "start", "menu", "help"}:
        send_whatsapp_reply(phone_number, _TENANT_MENU)
        return {"ok": True, "role": "tenant"}

    if normalized in {"rent", "balance", "my balance", "3"}:
        return _handle_balance_inquiry(phone_number)

    if normalized in {"invoice", "invoices", "last invoice"}:
        tenant = services.find_tenant_by_phone(phone_number)
        if tenant is None:
            send_whatsapp_reply(phone_number, _PAY_RENT_OUTCOME_MESSAGES["unknown_tenant"])
            return {"ok": False, "reason": "unknown_tenant"}
        lease = services.find_active_lease_for_tenant(tenant)
        if lease is None:
            send_whatsapp_reply(phone_number, _PAY_RENT_OUTCOME_MESSAGES["no_active_lease"])
            return {"ok": False, "reason": "no_active_lease"}
        invoices = list(
            services.Invoice.objects.filter(lease=lease).order_by("-due_date")[:5]
        ) if hasattr(services, 'Invoice') else []
        if not invoices:
            send_whatsapp_reply(phone_number, "You have no invoice history yet.")
            return {"ok": False, "reason": "no_invoice_history"}
        lines = [f"Latest invoices for {lease.unit.property.name} / {lease.unit.label}:"]
        for invoice in invoices:
            balance = invoice.amount_due - invoice.amount_paid
            lines.append(f"- Invoice {invoice.reference}: KES {balance:,.2f} due {invoice.due_date}")
        send_whatsapp_reply(phone_number, "\n".join(lines))
        return {"ok": True, "role": "tenant"}

    if normalized in {"lease", "my lease"}:
        tenant = services.find_tenant_by_phone(phone_number)
        if tenant is None:
            send_whatsapp_reply(phone_number, _PAY_RENT_OUTCOME_MESSAGES["unknown_tenant"])
            return {"ok": False, "reason": "unknown_tenant"}
        lease = services.find_active_lease_for_tenant(tenant)
        if lease is None:
            send_whatsapp_reply(phone_number, _PAY_RENT_OUTCOME_MESSAGES["no_active_lease"])
            return {"ok": False, "reason": "no_active_lease"}
        body_text = (
            f"Your active lease is for {lease.unit.property.name} / {lease.unit.label}. "
            f"Rent: KES {lease.rent_amount:,.2f}. Start: {lease.start_date}. End: {lease.end_date or 'Open ended'}."
        )
        send_whatsapp_reply(phone_number, body_text)
        return {"ok": True, "role": "tenant"}

    if normalized in {"ticket", "report issue", "report_issue", "issue"}:
        return _handle_report_issue(phone_number, body, "report issue", "")

    if normalized in {"status", "summary"}:
        tenant = services.find_tenant_by_phone(phone_number)
        if tenant is None:
            send_whatsapp_reply(phone_number, _PAY_RENT_OUTCOME_MESSAGES["unknown_tenant"])
            return {"ok": False, "reason": "unknown_tenant"}
        try:
            invoice = services.find_open_invoice_for_tenant(tenant)
            balance = invoice.amount_due - invoice.amount_paid
            lease = services.find_active_lease_for_tenant(tenant)
            unit_label = lease.unit.label if lease else "N/A"
            send_whatsapp_reply(phone_number, f"Status: active unit {unit_label}. Outstanding balance: KES {balance:,.2f}.")
            return {"ok": True, "role": "tenant"}
        except (services.NoActiveLeaseError, services.NoOpenInvoiceError):
            send_whatsapp_reply(phone_number, "You have no active lease or outstanding invoice on file.")
            return {"ok": False, "reason": "no_status"}

    logger.info("Unclassified tenant WhatsApp message from %s: %r", phone_number, body)
    send_whatsapp_reply(phone_number, _TENANT_MENU)
    return {"ok": False, "reason": "unclassified_intent"}


def _handle_landlord_message(phone_number: str, body: str, normalized: str, landlord) -> dict:
    if normalized in {"hi", "hello", "start", "menu", "help"}:
        send_whatsapp_reply(phone_number, _LANDLORD_MENU)
        return {"ok": True, "role": "landlord"}

    if "onboard tenant" in normalized or "add tenant" in normalized:
        try:
            result = services.onboard_tenant_for_landlord(landlord, body)
        except services.InvalidOnboardingPayloadError as exc:
            send_whatsapp_reply(phone_number, str(exc))
            return {"ok": False, "reason": "invalid_onboarding_payload"}
        send_whatsapp_reply(
            phone_number,
            (
                f"Tenant {result['tenant_name']} has been onboarded to {result['property_name']} / {result['unit_label']}. "
                f"Rent: KES {result['rent_amount']}."
            ),
            related_object_type="Tenant",
            related_object_id=result["tenant_id"],
        )
        return {"ok": True, "role": "landlord", "tenant_id": result["tenant_id"]}

    if normalized in {"portfolio", "tenants", "properties", "status"}:
        properties = landlord.properties.all().prefetch_related("units")
        property_count = properties.count()
        tenant_count = services.Tenant.objects.filter(leases__unit__property__landlord=landlord).distinct().count()
        send_whatsapp_reply(
            phone_number,
            f"Portfolio summary: {property_count} properties, {tenant_count} tenants. Reply 'onboard tenant: Name | Phone | Property | Unit | Rent | Start Date | End Date' to add a new tenant.",
        )
        return {"ok": True, "role": "landlord"}

    if normalized in {"help", "menu"}:
        send_whatsapp_reply(phone_number, _LANDLORD_MENU)
        return {"ok": True, "role": "landlord"}

    logger.info("Unclassified landlord WhatsApp message from %s: %r", phone_number, body)
    send_whatsapp_reply(phone_number, _LANDLORD_MENU)
    return {"ok": False, "reason": "unclassified_intent"}


@shared_task
def handle_inbound_whatsapp_message(phone_number: str, body: str, message_id: str = ""):
    """
    Entry point for every inbound WhatsApp message. Logs it for the audit
    trail, classifies intent, and dispatches to the matching flow:
    tenant, landlord, rent payment, issue reporting, or generic guidance.
    """
    WhatsAppMessage.objects.create(
        direction=MessageDirection.INBOUND,
        phone_number=phone_number,
        body=body,
        related_object_id=message_id,
    )

    normalized = body.strip().lower()

    role, profile = services.find_role_by_phone(phone_number)

    if role == "tenant":
        return _handle_tenant_message(phone_number, body, normalized)

    if role == "landlord":
        return _handle_landlord_message(phone_number, body, normalized, profile)

    if normalized in {"hi", "hello", "start", "welcome", "help", "menu"}:
        send_whatsapp_reply(phone_number, _UNKNOWN_USER_MENU)
        return {"ok": False, "reason": "unknown_role"}

    if normalized.startswith("onboard tenant") or normalized.startswith("add tenant"):
        send_whatsapp_reply(
            phone_number,
            "This WhatsApp number is not registered as a landlord yet. Please contact the platform admin or register a landlord account before onboarding tenants.",
        )
        return {"ok": False, "reason": "missing_landlord_record"}

    if normalized in services.PAY_RENT_TRIGGERS:
        result = services.trigger_stk_push_for_tenant(phone_number)
        _reply_for_pay_rent_outcome(phone_number, result)
        return result

    if normalized in BALANCE_TRIGGERS:
        return _handle_balance_inquiry(phone_number)

    if normalized in CARETAKER_TRIGGERS:
        return _handle_talk_to_caretaker(phone_number)

    for trigger in REPORT_ISSUE_TRIGGERS:
        if normalized == trigger or normalized.startswith(f"{trigger}:") or normalized.startswith(f"{trigger} "):
            return _handle_report_issue(phone_number, body, trigger, message_id)

    return _handle_role_unknown(phone_number, body, normalized)


def _reply_for_pay_rent_outcome(phone_number: str, result: dict):
    if result.get("ok"):
        body = f"STK Push sent for invoice {result['invoice_id']} — check your phone to enter your M-Pesa PIN."
    else:
        body = _PAY_RENT_OUTCOME_MESSAGES.get(
            result.get("reason"), "Something went wrong triggering your payment — please contact your caretaker."
        )
    send_whatsapp_reply(phone_number, body, related_object_type="Invoice", related_object_id=result.get("invoice_id", ""))


def _handle_balance_inquiry(phone_number: str) -> dict:
    tenant = services.find_tenant_by_phone(phone_number)
    if tenant is None:
        send_whatsapp_reply(phone_number, _PAY_RENT_OUTCOME_MESSAGES["unknown_tenant"])
        return {"ok": False, "reason": "unknown_tenant"}

    try:
        invoice = services.find_open_invoice_for_tenant(tenant)
    except services.NoActiveLeaseError:
        send_whatsapp_reply(phone_number, _PAY_RENT_OUTCOME_MESSAGES["no_active_lease"])
        return {"ok": False, "reason": "no_active_lease"}
    except services.NoOpenInvoiceError:
        send_whatsapp_reply(phone_number, "You're all caught up — no outstanding balance.")
        return {"ok": False, "reason": "no_open_invoice"}

    balance = invoice.amount_due - invoice.amount_paid
    body = f"Balance due: KES {balance:,.2f} (invoice {invoice.reference}, due {invoice.due_date}). Reply 'Pay Rent' to pay now."
    send_whatsapp_reply(phone_number, body, related_object_type="Invoice", related_object_id=str(invoice.id))
    return {"ok": True, "invoice_id": str(invoice.id), "balance": str(balance)}


def _handle_talk_to_caretaker(phone_number: str) -> dict:
    tenant = services.find_tenant_by_phone(phone_number)
    if tenant is None:
        send_whatsapp_reply(phone_number, _PAY_RENT_OUTCOME_MESSAGES["unknown_tenant"])
        return {"ok": False, "reason": "unknown_tenant"}

    caretaker = services.find_caretaker_for_tenant(tenant)
    if caretaker is None:
        send_whatsapp_reply(phone_number, "No caretaker is assigned to your property yet — please contact your landlord.")
        return {"ok": False, "reason": "no_caretaker_assigned"}

    contact = caretaker.user.phone_number or "not on file"
    body = f"Your caretaker is {caretaker.full_name} ({contact})."
    send_whatsapp_reply(phone_number, body)
    return {"ok": True, "caretaker_id": str(caretaker.id)}


def _handle_report_issue(phone_number: str, raw_body: str, matched_trigger: str, message_id: str) -> dict:
    tenant = services.find_tenant_by_phone(phone_number)
    if tenant is None:
        send_whatsapp_reply(phone_number, _PAY_RENT_OUTCOME_MESSAGES["unknown_tenant"])
        return {"ok": False, "reason": "unknown_tenant"}

    normalized = raw_body.strip()
    remainder = normalized[len(matched_trigger):].lstrip(" :-–")
    if not remainder:
        send_whatsapp_reply(
            phone_number, "Please describe the issue, e.g. 'Report issue: leaking kitchen tap'."
        )
        return {"ok": False, "reason": "missing_description"}

    try:
        ticket = services.create_maintenance_ticket_for_tenant(tenant, remainder, whatsapp_thread_ref=message_id)
    except services.NoActiveLeaseError:
        send_whatsapp_reply(phone_number, _PAY_RENT_OUTCOME_MESSAGES["no_active_lease"])
        return {"ok": False, "reason": "no_active_lease"}

    send_whatsapp_reply(
        phone_number,
        "Thanks — we've logged your issue and a caretaker will follow up soon.",
        related_object_type="MaintenanceTicket",
        related_object_id=str(ticket.id),
    )
    return {"ok": True, "ticket_id": str(ticket.id)}


@shared_task
def send_rent_reminders(days_before_due: int = 3):
    """
    Proactive outbound flow — previously nothing sent a rent reminder at
    all; NotificationTemplate existed but nothing used it (see
    send_whatsapp_template). Sends one 'rent_reminder' template message
    per still-open invoice due within `days_before_due` days (or already
    overdue), skipping an invoice already reminded today so a retry of
    this task (or a shorter Beat interval) can't spam a tenant.
    """
    from billing.models import Invoice, InvoiceStatus

    today = timezone.now().date()
    cutoff = today + timedelta(days=days_before_due)
    due_invoices = Invoice.objects.filter(
        status__in=[InvoiceStatus.OPEN, InvoiceStatus.PARTIAL, InvoiceStatus.OVERDUE],
        due_date__lte=cutoff,
    ).select_related("lease__tenant__user")

    sent = 0
    for invoice in due_invoices:
        phone_number = invoice.lease.tenant.user.phone_number
        if not phone_number:
            continue

        already_reminded_today = WhatsAppMessage.objects.filter(
            direction=MessageDirection.OUTBOUND,
            related_object_type="Invoice",
            related_object_id=str(invoice.id),
            created_at__date=today,
        ).exists()
        if already_reminded_today:
            continue

        try:
            send_whatsapp_template(
                phone_number,
                "rent_reminder",
                {
                    "tenant_name": invoice.lease.tenant.full_name,
                    "amount_due": str(invoice.amount_due - invoice.amount_paid),
                    "due_date": str(invoice.due_date),
                },
                related_object_type="Invoice",
                related_object_id=str(invoice.id),
            )
            sent += 1
        except services.TemplateNotApprovedError:
            logger.warning("send_rent_reminders: no approved 'rent_reminder' template — skipping this run.")
            break

    logger.info("send_rent_reminders: sent %s reminder(s)", sent)
    return sent


@shared_task
def send_email_notification(
    to_email: str, subject: str, html: str, text: str = "",
    related_object_type: str = "", related_object_id: str = "",
):
    """
    Generic outbound email — logs to EmailMessage regardless of Resend
    outcome, so delivery failures are still auditable, same pattern as
    send_whatsapp_reply above.
    """
    if not to_email:
        logger.warning("send_email_notification: no recipient email for %s %s", related_object_type, related_object_id)
        return

    record = EmailMessage.objects.create(
        to_email=to_email, subject=subject, body=html,
        related_object_type=related_object_type, related_object_id=related_object_id,
    )
    try:
        result = ResendClient.default().send_email(to=to_email, subject=subject, html=html, text=text or None)
    except ResendError:
        logger.exception("Failed to send email to %s (subject=%r)", to_email, subject)
        record.delivery_status = "failed"
        record.save(update_fields=["delivery_status"])
        return

    record.delivery_status = "sent"
    record.resend_message_id = result.id
    record.save(update_fields=["delivery_status", "resend_message_id"])
