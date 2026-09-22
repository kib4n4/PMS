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
Meta WhatsApp Cloud API client — real HTTP calls against the Graph API.
Credentials are DB-driven (credentials app): access token, phone number
ID, webhook verify token, and app secret are all PlatformCredential rows,
editable from admin without a redeploy.
"""

import logging
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v20.0"
GRAPH_API_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
REQUEST_TIMEOUT_SECONDS = 15


class WhatsAppError(Exception):
    """Raised when the Cloud API returns a non-success response, or no credentials are configured."""


@dataclass
class InboundMessage:
    message_id: str
    phone_number: str
    body: str
    message_type: str = "text"


@dataclass
class SendMessageResult:
    message_id: str

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
        from credentials.models import PlatformCredentialKey
        from credentials.services import get_platform_credential

        return cls(
            access_token=get_platform_credential(PlatformCredentialKey.WHATSAPP_ACCESS_TOKEN, default=""),
            phone_number_id=get_platform_credential(PlatformCredentialKey.WHATSAPP_PHONE_NUMBER_ID, default=""),
        )

    def _post(self, payload: dict) -> dict:
        if not (self.access_token and self.phone_number_id):
            raise WhatsAppError("Cannot send WhatsApp message: no access token/phone number ID configured.")

        try:
            response = requests.post(
                f"{GRAPH_API_BASE_URL}/{self.phone_number_id}/messages",
                json=payload,
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise WhatsAppError(f"WhatsApp request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError:
            data = {}

        if not response.ok:
            raise WhatsAppError(f"WhatsApp send failed ({response.status_code}): {data or response.text[:200]}")
        return data

    def send_template_message(self, to_phone_number: str, template_name: str, variables: dict) -> SendMessageResult:
        """Send a pre-approved template message (outside the 24h window)."""
        components = []
        if variables:
            components = [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": str(value)} for value in variables.values()],
                }
            ]
        data = self._post(
            {
                "messaging_product": "whatsapp",
                "to": to_phone_number,
                "type": "template",
                "template": {"name": template_name, "language": {"code": "en"}, "components": components},
            }
        )
        return SendMessageResult(message_id=(data.get("messages") or [{}])[0].get("id", ""))

    def send_session_message(self, to_phone_number: str, body: str) -> SendMessageResult:
        """Free-form reply within a 24h customer-initiated session."""
        data = self._post(
            {
                "messaging_product": "whatsapp",
                "to": to_phone_number,
                "type": "text",
                "text": {"body": body},
            }
        )
        return SendMessageResult(message_id=(data.get("messages") or [{}])[0].get("id", ""))

    def parse_inbound_webhook(self, payload: dict) -> list:
        """
        Extract every inbound text-ish message from a raw Cloud API
        webhook payload. Non-text message types (image, location, ...)
        and delivery-status-only payloads are skipped — this platform
        only acts on text/button/interactive-reply content today.
        """
        messages = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for message in value.get("messages", []):
                    phone_number = message.get("from", "")
                    body = (
                        message.get("text", {}).get("body")
                        or message.get("button", {}).get("text")
                        or message.get("interactive", {}).get("button_reply", {}).get("title")
                        or message.get("interactive", {}).get("list_reply", {}).get("title")
                        or ""
                    )
                    if phone_number and body:
                        messages.append(
                            InboundMessage(
                                message_id=message.get("id", ""),
                                phone_number=phone_number,
                                body=body,
                                message_type=message.get("type", "text"),
                            )
                        )
                    else:
                        logger.warning("Unrecognized WhatsApp message shape: %s", message)
        return messages
