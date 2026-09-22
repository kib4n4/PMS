# backend/messaging/tasks.py

import logging

from celery import shared_task

from integrations.resend_client import ResendClient, ResendError
from integrations.whatsapp import WhatsAppClient, WhatsAppError

from . import services
from .models import EmailMessage, MessageDirection, WhatsAppMessage

logger = logging.getLogger(__name__)

REPORT_ISSUE_TRIGGERS = ("report issue", "report_issue", "issue", "2")
BALANCE_TRIGGERS = {"balance", "my balance", "3"}
CARETAKER_TRIGGERS = {"caretaker", "talk to caretaker", "4"}

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
    record's delivery_status with the outcome.
    """
    message = WhatsAppMessage.objects.create(
        direction=MessageDirection.OUTBOUND,
        phone_number=phone_number,
        body=body,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
    )
    try:
        WhatsAppClient.default().send_session_message(phone_number, body)
    except WhatsAppError:
        logger.exception("Failed to send WhatsApp reply to %s", phone_number)
        message.delivery_status = "failed"
    else:
        message.delivery_status = "sent"
    message.save(update_fields=["delivery_status"])


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
