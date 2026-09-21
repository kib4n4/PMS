# backend/integrations/whatsapp.py
"""Twilio WhatsApp client.

Credentials are DB-driven: each landlord's own Twilio subaccount/sender is
looked up via ProviderCredential at call time, falling back to the
platform-level account in settings.py for landlords who haven't onboarded
their own number yet. No more NotImplementedError stubs — every method
here makes a real Twilio API call.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from django.conf import settings
from twilio.base.exceptions import TwilioRestException
from twilio.request_validator import RequestValidator
from twilio.rest import Client

from .models import Provider, ProviderCredential

logger = logging.getLogger(__name__)


class WhatsAppSendError(Exception):
    """Raised when Twilio rejects or fails to deliver a WhatsApp message."""


class WhatsAppClient:
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        if not (account_sid and auth_token and from_number):
            raise ValueError(
                "Twilio account_sid, auth_token and from_number are all required "
                "— check ProviderCredential or the TWILIO_* settings."
            )
        self.from_number = self._to_whatsapp(from_number)
        self._client = Client(account_sid, auth_token)

    # -- construction ---------------------------------------------------------

    @classmethod
    def for_landlord(cls, landlord) -> "WhatsAppClient":
        """Client scoped to a landlord's own Twilio WhatsApp sender, falling
        back to the platform default if the landlord has none configured."""
        try:
            cred = ProviderCredential.get_active(Provider.TWILIO, landlord=landlord)
        except ProviderCredential.DoesNotExist:
            logger.info(
                "No Twilio credential for landlord %s — using platform default.",
                getattr(landlord, "id", None),
            )
            return cls.default()

        # Support legacy JSON storage and the new structured fields.
        if getattr(cred, 'auth_type', None) == cred.AuthType.OAUTH2 if hasattr(cred, 'auth_type') else False:
            # client_id/client_secret stored in structured columns; metadata may contain whatsapp_number
            creds = cred.get_credentials()
            meta = cred.get_metadata() if hasattr(cred, 'get_metadata') else {}
            account_sid = creds.get('client_id')
            auth_token = creds.get('client_secret')
            from_number = meta.get('whatsapp_number')
        else:
            data = cred.get_credentials()
            # legacy JSON expected to contain account_sid/auth_token/whatsapp_number
            account_sid = data.get('account_sid')
            auth_token = data.get('auth_token')
            from_number = data.get('whatsapp_number')

        return cls(
            account_sid=account_sid,
            auth_token=auth_token,
            from_number=from_number,
        )

    @classmethod
    def default(cls) -> "WhatsAppClient":
        return cls(
            account_sid=settings.TWILIO_ACCOUNT_SID,
            auth_token=settings.TWILIO_AUTH_TOKEN,
            from_number=settings.TWILIO_WHATSAPP_FROM,
        )

    # -- sending ---------------------------------------------------------------

    @staticmethod
    def _to_whatsapp(number: str) -> str:
        return number if number.startswith("whatsapp:") else f"whatsapp:{number}"

    def send_template_message(self, to_phone_number: str, template_name: str, variables: dict) -> dict:
        """Send a pre-approved WhatsApp template via Twilio's Content API —
        required outside the 24h customer-service window. `template_name`
        is the Twilio Content SID (HXxxxxxxxx...) registered for that
        template in the Twilio console.
        """
        content_variables = json.dumps({str(k): str(v) for k, v in (variables or {}).items()})
        try:
            message = self._client.messages.create(
                from_=self.from_number,
                to=self._to_whatsapp(to_phone_number),
                content_sid=template_name,
                content_variables=content_variables,
            )
        except TwilioRestException as exc:
            raise WhatsAppSendError(
                f"Twilio rejected template '{template_name}' to {to_phone_number}: {exc}"
            ) from exc
        return {"sid": message.sid, "status": message.status}

    def send_session_message(self, to_phone_number: str, body: str) -> dict:
        """Free-form reply within a 24h customer-initiated session."""
        try:
            message = self._client.messages.create(
                from_=self.from_number,
                to=self._to_whatsapp(to_phone_number),
                body=body,
            )
        except TwilioRestException as exc:
            raise WhatsAppSendError(f"Twilio rejected session send to {to_phone_number}: {exc}") from exc
        return {"sid": message.sid, "status": message.status}

    # -- inbound -----------------------------------------------------------------

    @staticmethod
    def parse_inbound_webhook(payload: dict) -> Optional[dict]:
        """Parse a Twilio WhatsApp inbound webhook. Twilio posts
        form-encoded data (your view should convert request.POST to a dict
        before calling this) with `From`/`To` as `whatsapp:+2547...`,
        `Body` for free text, and `ButtonText`/`ButtonPayload` for
        quick-reply button taps.
        """
        from_number = payload.get("From", "")
        if not from_number:
            return None
        return {
            "from_phone_number": from_number.removeprefix("whatsapp:"),
            "message_id": payload.get("MessageSid"),
            "body": payload.get("Body", ""),
            "button_payload": payload.get("ButtonPayload"),
            "button_text": payload.get("ButtonText"),
            "num_media": int(payload.get("NumMedia", 0) or 0),
        }

    @staticmethod
    def verify_webhook_signature(url: str, post_params: dict, signature_header: str, auth_token: Optional[str] = None) -> bool:
        """Validate an inbound webhook actually came from Twilio, per
        https://www.twilio.com/docs/usage/webhooks/webhooks-security. Call
        this in the webhook view before trusting the payload; reject with
        403 on False. Pass the same auth_token used to send from that
        number (per-landlord credential, or the platform default)."""
        token = auth_token or settings.TWILIO_AUTH_TOKEN
        validator = RequestValidator(token)
        return validator.validate(url, post_params, signature_header)