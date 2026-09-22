# backend/accounts/services/otp.py
"""Email-delivered OTP flow via Resend.

Login stays phone-number-first for identity (User.phone_number is the
lookup key), but the OTP *code* is now emailed via Resend rather than sent
over WhatsApp/SMS. Callers must have a verified email on file for the user
before calling request_otp() — there's no fallback channel.
"""

from __future__ import annotations

import hashlib
import logging
import random
from datetime import timedelta

import resend
from django.conf import settings
from django.utils import timezone

from accounts.models import OTPRequest
from integrations.models import Provider, ProviderCredential

logger = logging.getLogger(__name__)

OTP_LENGTH = 6
OTP_TTL_MINUTES = 10
MAX_ATTEMPTS = 5

# Prefer platform-level ProviderCredential for Resend if present
try:
    try:
        cred = ProviderCredential.get_active(Provider.RESEND, landlord=None)
    except ProviderCredential.DoesNotExist:
        cred = None
    if cred:
        # auth_type should be BEARER and token available
        try:
            resend_key = cred.get_credentials().get('token') if cred.auth_type == cred.AuthType.BEARER else cred.get_credentials().get('api_key')
            if not resend_key:
                raise ValueError('No API key present in ProviderCredential')
            resend.api_key = resend_key
        except Exception:
            # fallback to settings
            resend.api_key = settings.RESEND_API_KEY
    else:
        resend.api_key = settings.RESEND_API_KEY
except Exception:
    # If anything goes wrong doing a DB lookup at import time, fall back to settings
    resend.api_key = settings.RESEND_API_KEY


class OTPError(Exception):
    """Raised when Resend fails to accept/send the OTP email."""


def _generate_code() -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(OTP_LENGTH))


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def request_otp(phone_number: str, email: str) -> OTPRequest:
    """Create an OTP, email it via Resend, and return the OTPRequest row.
    Raises OTPError (and rolls back the row) if Resend rejects the send."""
    code = _generate_code()
    otp = OTPRequest.objects.create(
        phone_number=phone_number,
        email=email,
        code_hash=_hash_code(code),
        channel=OTPRequest.Channel.EMAIL,
        expires_at=timezone.now() + timedelta(minutes=OTP_TTL_MINUTES),
    )

    try:
        resend.Emails.send({
            "from": settings.RESEND_OTP_FROM_EMAIL,
            "to": [email],
            "subject": "Your PMS login code",
            "text": f"Your login code is {code}. It expires in {OTP_TTL_MINUTES} minutes.",
        })
    except Exception as exc:  # resend's SDK exception surface isn't a single class — stay defensive
        logger.exception("Resend OTP send failed for %s", phone_number)
        otp.delete()
        raise OTPError(f"Could not send OTP email: {exc}") from exc

    return otp


def verify_otp(phone_number: str, code: str) -> bool:
    """Validate the most recent unexpired, unconsumed OTP for this phone
    number. Increments attempt_count on a wrong code and locks out once
    MAX_ATTEMPTS is hit."""
    otp = (
        OTPRequest.objects.filter(
            phone_number=phone_number,
            consumed_at__isnull=True,
            expires_at__gte=timezone.now(),
        )
        .order_by("-created_at")
        .first()
    )
    if otp is None:
        return False
    if otp.attempt_count >= MAX_ATTEMPTS:
        return False
    if otp.code_hash != _hash_code(code):
        otp.attempt_count += 1
        otp.save(update_fields=["attempt_count"])
        return False

    otp.consumed_at = timezone.now()
    otp.save(update_fields=["consumed_at"])
    return True