# backend/billing/webhook_views.py

import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .tasks import ingest_c2b_confirmation, ingest_stk_callback, log_transaction_status_result, log_transaction_status_timeout

logger = logging.getLogger(__name__)


# NOTE on security: these are public, unauthenticated-by-header endpoints
# by nature (Safaricom calls them directly). Real deployment MUST verify
# the request originates from Safaricom's published IP ranges at the
# Nginx/network layer, and should additionally validate the shortcode in
# the payload against a known LandlordDarajaCredential before any side
# effect runs (ingest_c2b_confirmation already does the latter).


def _parse_or_reject(request):
    try:
        return json.loads(request.body or b"{}"), None
    except json.JSONDecodeError:
        logger.warning("Malformed webhook payload on %s", request.path)
        return None, JsonResponse({"ResultCode": 1, "ResultDesc": "Rejected — malformed payload"})


@csrf_exempt
@require_POST
def mpesa_c2b_validation(request):
    """
    Safaricom calls this before confirming a payment, to let the platform
    accept/reject the transaction (e.g. unknown account reference). For
    now we accept everything and let ingest_c2b_confirmation resolve the
    invoice — a stricter implementation can reject unknown account
    references here instead.
    """
    payload, rejection = _parse_or_reject(request)
    if rejection:
        return rejection

    logger.info("C2B validation received: %s", payload)
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


@csrf_exempt
@require_POST
def mpesa_c2b_confirmation(request):
    """
    Safaricom's confirmation callback for manual Paybill-menu payments —
    the actual payment record. Fired into a Celery task so the HTTP
    response returns immediately and the ingestion (with its idempotency
    guard) happens durably in the background, safe to retry if Safaricom
    redelivers.
    """
    payload, rejection = _parse_or_reject(request)
    if rejection:
        return rejection

    ingest_c2b_confirmation.delay(payload)
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


@csrf_exempt
@require_POST
def mpesa_stk_callback(request):
    """
    STK Push result callback — fired after a tenant enters (or cancels/
    times out on) their M-Pesa PIN in response to a push we initiated.
    Correlated back to an Invoice via CheckoutRequestID
    (billing/tasks.py::ingest_stk_callback), not AccountReference.
    """
    payload, rejection = _parse_or_reject(request)
    if rejection:
        return rejection

    ingest_stk_callback.delay(payload)
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


@csrf_exempt
@require_POST
def mpesa_b2c_result(request):
    """B2C payout result callback — updates the matching Disbursement's status."""
    payload, rejection = _parse_or_reject(request)
    if rejection:
        return rejection

    from partners.tasks import handle_b2c_result

    handle_b2c_result.delay(payload)
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


@csrf_exempt
@require_POST
def mpesa_b2c_timeout(request):
    """B2C payout timeout callback — marks the Disbursement FAILED for manual retry."""
    payload, rejection = _parse_or_reject(request)
    if rejection:
        return rejection

    from partners.tasks import handle_b2c_timeout

    handle_b2c_timeout.delay(payload)
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


@csrf_exempt
@require_POST
def mpesa_transaction_status_result(request):
    """Async result of a reconciliation query_transaction_status call."""
    payload, rejection = _parse_or_reject(request)
    if rejection:
        return rejection

    log_transaction_status_result.delay(payload)
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


@csrf_exempt
@require_POST
def mpesa_transaction_status_timeout(request):
    payload, rejection = _parse_or_reject(request)
    if rejection:
        return rejection

    log_transaction_status_timeout.delay(payload)
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})
