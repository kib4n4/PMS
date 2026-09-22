# backend/integrations/whatsapp.py

"""
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


@dataclass
class StatusUpdate:
    message_id: str
    status: str  # Meta's own vocabulary: "sent" | "delivered" | "read" | "failed"
    recipient_phone: str = ""


class WhatsAppClient:
    def __init__(self, access_token: str, phone_number_id: str):
        self.access_token = access_token
        self.phone_number_id = phone_number_id

    @classmethod
    def default(cls) -> "WhatsAppClient":
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

    def parse_status_updates(self, payload: dict) -> list:
        """
        Extract delivery-status callbacks (Meta's `value.statuses` array —
        sent/delivered/read/failed for a message THIS platform sent)
        from the same webhook payload shape parse_inbound_webhook reads.
        Kept as a separate method rather than folded into
        parse_inbound_webhook so that method's return shape (a list of
        InboundMessage) stays unchanged for existing callers/tests.
        """
        updates = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for status_entry in value.get("statuses", []):
                    message_id = status_entry.get("id", "")
                    status_value = status_entry.get("status", "")
                    if message_id and status_value:
                        updates.append(
                            StatusUpdate(
                                message_id=message_id,
                                status=status_value,
                                recipient_phone=status_entry.get("recipient_id", ""),
                            )
                        )
        return updates
