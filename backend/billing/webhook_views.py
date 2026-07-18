# backend/billing/webhook_views.py

import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .tasks import ingest_c2b_confirmation

logger = logging.getLogger(__name__)


# NOTE on security: these are public, unauthenticated-by-header endpoints
# by nature (Safaricom calls them directly). Real deployment MUST verify
# the request originates from Safaricom's published IP ranges at the
# Nginx/network layer, and should additionally validate the shortcode in
# the payload against a known LandlordDarajaCredential before any side
# effect runs (ingest_c2b_confirmation already does the latter). Do not
# remove that lookup when wiring real credentials in M2.


@csrf_exempt
@require_POST
def mpesa_c2b_validation(request):
    """
    Safaricom calls this before confirming a payment, to let the platform
    accept/reject the transaction (e.g. unknown account reference). For
    now we accept everything and let ingest_c2b_confirmation resolve the
    invoice — a stricter M2 implementation can reject unknown account
    references here instead.
    """
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        logger.warning("Malformed C2B validation payload")
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Rejected — malformed payload"})

    logger.info("C2B validation received: %s", payload)
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


@csrf_exempt
@require_POST
def mpesa_c2b_confirmation(request):
    """
    Safaricom's confirmation callback — the actual payment record. Fired
    into a Celery task so the HTTP response returns immediately and the
    ingestion (with its idempotency guard) happens durably in the
    background, safe to retry if Safaricom redelivers.
    """
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        logger.warning("Malformed C2B confirmation payload")
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Rejected — malformed payload"})

    ingest_c2b_confirmation.delay(payload)
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


@csrf_exempt
@require_POST
def mpesa_b2c_result(request):
    """B2C payout result callback — updates a Disbursement's status.
    TODO(M4): parse payload, dedupe on ConversationID, update Disbursement."""
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        logger.warning("Malformed B2C result payload")
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Rejected — malformed payload"})

    logger.info("B2C result received (M4 TODO — not yet wired to Disbursement): %s", payload)
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


@csrf_exempt
@require_POST
def mpesa_b2c_timeout(request):
    """B2C payout timeout callback. TODO(M4): mark Disbursement as failed/retry."""
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        logger.warning("Malformed B2C timeout payload")
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Rejected — malformed payload"})

    logger.info("B2C timeout received (M4 TODO — not yet wired to Disbursement): %s", payload)
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})