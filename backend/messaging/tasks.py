# backend/messaging/tasks.py

import logging

from celery import shared_task

from . import services
from .models import MessageDirection, WhatsAppMessage

logger = logging.getLogger(__name__)

_OUTCOME_MESSAGES = {
    "unknown_tenant": "We couldn't find your tenant record — please contact your caretaker.",
    "no_active_lease": "You don't have an active lease on file — please contact your caretaker.",
    "no_open_invoice": "You're all caught up — no open invoice right now.",
    "landlord_not_onboarded": "Rent payment isn't set up for your property yet — please contact your caretaker.",
    "stk_push_not_yet_live": "Rent payment via WhatsApp isn't live yet — please contact your caretaker.",
    "unclassified_intent": None,  # no auto-reply yet; falls through to human handoff in M3
}


@shared_task
def handle_inbound_whatsapp_message(phone_number: str, body: str, message_id: str = ""):
    """
    Entry point for every inbound WhatsApp message. Logs it for the audit
    trail, classifies intent, and for a 'Pay Rent' intent triggers the
    STK Push flow via messaging.services.

    TODO(M3): classify Report Issue / My Balance / Talk to Caretaker
    intents here too; anything unclassified should open a flagged
    human-handoff thread in the admin console rather than silently
    dropping the message.
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

    logger.info("Unclassified WhatsApp message from %s: %r", phone_number, body)
    return {"ok": False, "reason": "unclassified_intent"}


def _reply_for_pay_rent_outcome(phone_number: str, result: dict):
    if result.get("ok"):
        body = f"STK Push sent for invoice {result['invoice_id']} — check your phone to enter your M-Pesa PIN."
    else:
        body = _OUTCOME_MESSAGES.get(
            result.get("reason"), "Something went wrong triggering your payment — please contact your caretaker."
        )
        if body is None:
            return

    WhatsAppMessage.objects.create(direction=MessageDirection.OUTBOUND, phone_number=phone_number, body=body)
    # TODO(M3): actually deliver this via
    # integrations.whatsapp.WhatsAppClient().send_session_message(...)
    # once real Meta Cloud API credentials exist — for now it's only
    # logged to WhatsAppMessage for the audit trail.