# backend/messaging/webhook_views.py

import json
import logging
import os

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .tasks import handle_inbound_whatsapp_message

logger = logging.getLogger(__name__)

# TODO(M3): move to settings.py, sourced from the secrets manager — not
# a bare os.environ default, once real Meta app credentials exist.
VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "dev-only-verify-token")


@csrf_exempt
def whatsapp_webhook(request):
    if request.method == "GET":
        return _handle_verification(request)
    if request.method == "POST":
        return _handle_inbound(request)
    return HttpResponse(status=405)


def _handle_verification(request):
    """Meta's webhook subscription handshake — echoes hub.challenge back
    only if the verify token matches what's configured on our side."""
    mode = request.GET.get("hub.mode")
    token = request.GET.get("hub.verify_token")
    challenge = request.GET.get("hub.challenge", "")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return HttpResponse(challenge)

    logger.warning("WhatsApp webhook verification failed (mode=%s)", mode)
    return HttpResponse(status=403)


def _handle_inbound(request):
    """
    Parses inbound WhatsApp Cloud API payloads and hands each message off
    to Celery. Kept as a minimal manual parse for now — TODO(M3): replace
    with integrations.whatsapp.WhatsAppClient().parse_inbound_webhook(...)
    once implemented against a real captured payload shape, and this
    view should always respond 200 immediately regardless of downstream
    outcome, same reasoning as the M-Pesa webhooks.
    """
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        logger.warning("whatsapp_webhook: non-JSON body")
        return JsonResponse({"status": "ignored"})

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for message in value.get("messages", []):
                phone_number = message.get("from", "")
                body = (
                    message.get("text", {}).get("body")
                    or message.get("button", {}).get("text")
                    or message.get("interactive", {}).get("button_reply", {}).get("title")
                    or ""
                )
                message_id = message.get("id", "")
                if phone_number and body:
                    handle_inbound_whatsapp_message.delay(phone_number, body, message_id)
                else:
                    logger.warning("Unrecognized WhatsApp message shape: %s", message)

    return JsonResponse({"status": "received"})