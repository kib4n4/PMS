# backend/messaging/webhook_views.py

import hashlib
import hmac
import json
import logging

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from credentials.models import PlatformCredentialKey
from credentials.services import get_platform_credential
from integrations.whatsapp import WhatsAppClient

from .tasks import handle_inbound_whatsapp_message

logger = logging.getLogger(__name__)


@csrf_exempt
def whatsapp_webhook(request):
    if request.method == "GET":
        return _handle_verification(request)
    if request.method == "POST":
        return _handle_inbound(request)
    return HttpResponse(status=405)


def _handle_verification(request):
    """Meta's webhook subscription handshake — echoes hub.challenge back
    only if the verify token matches what's configured (DB-driven,
    credentials.PlatformCredential — not an env var)."""
    mode = request.GET.get("hub.mode")
    token = request.GET.get("hub.verify_token")
    challenge = request.GET.get("hub.challenge", "")

    expected_token = get_platform_credential(PlatformCredentialKey.WHATSAPP_VERIFY_TOKEN, default="")
    if mode == "subscribe" and expected_token and token == expected_token:
        return HttpResponse(challenge)

    logger.warning("WhatsApp webhook verification failed (mode=%s)", mode)
    return HttpResponse(status=403)


def _signature_is_valid(request) -> bool:
    """
    Meta signs every webhook POST body with HMAC-SHA256 over the app
    secret, sent as `X-Hub-Signature-256: sha256=<hex>`. If no app secret
    is configured yet (fresh install, before Meta credentials exist),
    this deliberately fails closed rather than silently accepting
    unsigned traffic.
    """
    app_secret = get_platform_credential(PlatformCredentialKey.WHATSAPP_APP_SECRET, default="")
    if not app_secret:
        logger.warning("WHATSAPP_APP_SECRET not configured — rejecting inbound webhook.")
        return False

    signature_header = request.headers.get("X-Hub-Signature-256", "")
    if not signature_header.startswith("sha256="):
        return False

    expected = hmac.new(app_secret.encode(), request.body, hashlib.sha256).hexdigest()
    provided = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)


def _handle_inbound(request):
    """
    Verifies the request is genuinely from Meta, parses every inbound
    message via integrations.whatsapp.WhatsAppClient.parse_inbound_webhook,
    and hands each off to Celery. Always responds 200 once the signature
    checks out, regardless of downstream outcome — same reasoning as the
    M-Pesa webhooks (Meta retries aggressively on non-2xx).
    """
    if not _signature_is_valid(request):
        return HttpResponse(status=403)

    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        logger.warning("whatsapp_webhook: non-JSON body")
        return JsonResponse({"status": "ignored"})

    for message in WhatsAppClient.default().parse_inbound_webhook(payload):
        handle_inbound_whatsapp_message.delay(message.phone_number, message.body, message.message_id)

    return JsonResponse({"status": "received"})
