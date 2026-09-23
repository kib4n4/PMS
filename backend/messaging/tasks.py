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
BALANCE_TRIGGERS = {"balance", "my balance", "3"}
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

_MENU_REPLY = (
    "Sorry, I didn't understand that. Reply with one of: "
    "'Pay Rent', 'Balance', 'Caretaker', or 'Report issue: <description>'."
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


@shared_task
def handle_inbound_whatsapp_message(phone_number: str, body: str, message_id: str = ""):
    """
    Entry point for every inbound WhatsApp message. Logs it for the audit
    trail, classifies intent, and dispatches to the matching flow:
    Pay Rent, Report Issue, My Balance, or Talk to Caretaker. Anything
    unclassified is logged for human follow-up rather than silently
    dropped or auto-replied to with a guess.
    """
    WhatsAppMessage.objects.create(
        direction=MessageDirection.INBOUND,
        phone_number=phone_number,
        body=body,
        related_object_id=message_id,
    )

    normalized = body.strip().lower()

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

    logger.info("Unclassified WhatsApp message from %s: %r", phone_number, body)
    send_whatsapp_reply(phone_number, _MENU_REPLY)
    return {"ok": False, "reason": "unclassified_intent"}


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
