# backend/messaging/webhook_views.py

import hashlib
import hmac
import json
import logging
from time import time

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from credentials.models import PlatformCredentialKey
from credentials.services import get_platform_credential
from integrations.twilio import TwilioClient
from integrations.whatsapp import WhatsAppClient

from .tasks import handle_inbound_whatsapp_message, handle_whatsapp_status_update

logger = logging.getLogger(__name__)

_TWILIO_RATE_LIMIT_WINDOW_SECONDS = 60
_TWILIO_RATE_LIMIT_MAX_REQUESTS = 60
_TWILIO_BACKOFF_KEY_PREFIX = "twilio-backoff:"
_TWILIO_BACKOFF_SECONDS = 30


def _friendly_service_error_response(service: str, *, retry_after_seconds: int | None = None):
    response = JsonResponse({
        "status": "service_unavailable",
        "message": f"{service} is temporarily unavailable. Please try again in a moment.",
    }, status=503)
    if retry_after_seconds is not None:
        response["Retry-After"] = str(retry_after_seconds)
    return response


@csrf_exempt
def whatsapp_webhook(request):
    if request.method == "GET":
        return _handle_verification(request)
    if request.method == "POST":
        return _handle_inbound(request)
    return HttpResponse(status=405)


@csrf_exempt
def twilio_webhook(request):
    if request.method == "POST":
        return _handle_twilio_inbound(request)
    if request.method == "GET":
        return HttpResponse(status=405)
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


def _rate_limit_key_for_request(request, prefix: str) -> str:
    return f"{prefix}:{request.META.get('REMOTE_ADDR', 'unknown')}"


def _is_rate_limited(request, *, prefix: str, window_seconds: int, max_requests: int) -> bool:
    key = _rate_limit_key_for_request(request, prefix)
    bucket = cache.get(key)
    now = int(time())

    if bucket is None:
        cache.set(key, [(now, 1)], timeout=window_seconds)
        return False

    if not isinstance(bucket, list):
        cache.delete(key)
        return False

    recent = [item for item in bucket if now - item[0] < window_seconds]
    if len(recent) >= max_requests:
        return True

    recent.append((now, 1))
    cache.set(key, recent, timeout=window_seconds)
    return False


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

    client = WhatsAppClient.default()

    for message in client.parse_inbound_webhook(payload):
        handle_inbound_whatsapp_message.delay(message.phone_number, message.body, message.message_id)

    for status_update in client.parse_status_updates(payload):
        handle_whatsapp_status_update.delay(status_update.message_id, status_update.status)

    return JsonResponse({"status": "received"})


def _handle_twilio_inbound(request):
    if _is_rate_limited(
        request,
        prefix="messaging:twilio:webhook",
        window_seconds=_TWILIO_RATE_LIMIT_WINDOW_SECONDS,
        max_requests=_TWILIO_RATE_LIMIT_MAX_REQUESTS,
    ):
        logger.warning("Twilio webhook rate limit hit for %s", request.META.get("REMOTE_ADDR"))
        return _friendly_service_error_response("Twilio", retry_after_seconds=_TWILIO_RATE_LIMIT_WINDOW_SECONDS)

    twilio_auth_token = get_platform_credential(PlatformCredentialKey.TWILIO_AUTH_TOKEN, default="")
    if not twilio_auth_token:
        logger.warning("TWILIO_AUTH_TOKEN not configured; rejecting inbound Twilio webhook.")
        return HttpResponse(status=403)

    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature:
        logger.warning("Missing Twilio request signature.")
        return HttpResponse(status=403)

    params = request.POST.copy()
    full_url = request.build_absolute_uri()
    logger.debug("Validating Twilio webhook signature for %s", request.META.get("REMOTE_ADDR"))
    if not TwilioClient.validate_signature(full_url, params, signature, twilio_auth_token):
        logger.warning("Twilio webhook signature mismatch for %s", request.META.get("REMOTE_ADDR"))
        return HttpResponse(status=403)

    client = TwilioClient.default()
    messages = client.parse_inbound_webhook({}, request=request)
    if not messages:
        return JsonResponse({"status": "ignored"})

    for message in messages:
        handle_inbound_whatsapp_message.delay(message.phone_number, message.body, message.sid)

    return JsonResponse({"status": "received"})