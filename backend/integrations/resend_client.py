# backend/integrations/resend_client.py

"""
Resend (https://resend.com) email client — real HTTP calls against
Resend's REST API. Credentials are DB-driven (credentials app), same
pattern as Daraja/WhatsApp: rotating the API key is an admin-panel edit,
not a redeploy.
"""

import base64
import logging
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
REQUEST_TIMEOUT_SECONDS = 15


class ResendError(Exception):
    """Raised when Resend returns a non-success response, or no API key is configured."""


@dataclass
class EmailAttachment:
    filename: str
    content: bytes


@dataclass
class SendEmailResult:
    id: str


class ResendClient:
    def __init__(self, api_key: str, from_email: str):
        self.api_key = api_key
        self.from_email = from_email

    @classmethod
    def default(cls) -> "ResendClient":
        from credentials.models import PlatformCredentialKey
        from credentials.services import get_platform_credential

        return cls(
            api_key=get_platform_credential(PlatformCredentialKey.RESEND_API_KEY, default=""),
            from_email=get_platform_credential(
                PlatformCredentialKey.RESEND_FROM_EMAIL, default="Dime PMS <notifications@dime-pms.example>"
            ),
        )

    def send_email(
        self,
        to: str,
        subject: str,
        html: str,
        text: Optional[str] = None,
        attachments: Optional[list] = None,
    ) -> SendEmailResult:
        if not self.api_key:
            raise ResendError("Cannot send email: no Resend API key configured.")

        payload = {"from": self.from_email, "to": [to], "subject": subject, "html": html}
        if text:
            payload["text"] = text
        if attachments:
            payload["attachments"] = [
                {"filename": a.filename, "content": base64.b64encode(a.content).decode()} for a in attachments
            ]

        try:
            response = requests.post(
                RESEND_API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise ResendError(f"Resend request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError:
            data = {}

        if not response.ok:
            raise ResendError(f"Resend send failed ({response.status_code}): {data or response.text[:200]}")

        return SendEmailResult(id=data.get("id", ""))
