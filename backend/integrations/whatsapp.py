# backend/integrations/whatsapp.py

"""
Meta WhatsApp Cloud API client — STUBBED, same reasoning as daraja.py:
no network path to graph.facebook.com from this sandbox, and no real
access token/phone-number-ID exists yet. Wire the real HTTP calls in M3.
"""

from typing import Optional


class WhatsAppClient:
    def __init__(self, access_token: str, phone_number_id: str):
        self.access_token = access_token
        self.phone_number_id = phone_number_id

    @classmethod
    def default(cls) -> "WhatsAppClient":
        # TODO(M3): resolve access_token/phone_number_id via secrets manager.
        return cls(access_token="STUB", phone_number_id="STUB")

    def send_template_message(self, to_phone_number: str, template_name: str, variables: dict) -> dict:
        """Send a pre-approved template message (outside the 24h window).
        TODO(M3): real Graph API call to /messages."""
        raise NotImplementedError(
            "WhatsAppClient.send_template_message is a stub — wire real "
            "Meta Cloud API credentials and HTTP call in M3 before use."
        )

    def send_session_message(self, to_phone_number: str, body: str) -> dict:
        """Free-form reply within a 24h customer-initiated session.
        TODO(M3): real Graph API call to /messages."""
        raise NotImplementedError(
            "WhatsAppClient.send_session_message is a stub — wire real "
            "Meta Cloud API credentials and HTTP call in M3 before use."
        )

    def parse_inbound_webhook(self, payload: dict) -> Optional[dict]:
        """Extract sender phone number, message body/button reply, and
        message ID from a raw Cloud API webhook payload.
        TODO(M3): real payload parsing per Meta's webhook schema."""
        raise NotImplementedError(
            "WhatsAppClient.parse_inbound_webhook is a stub — implement "
            "against a real captured webhook payload in M3."
        )