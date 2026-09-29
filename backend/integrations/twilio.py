import base64
import hashlib
import hmac
import logging
from dataclasses import dataclass
from typing import Any

import requests



logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 15


class TwilioError(Exception):
    """Raised for Twilio API failures or missing credentials."""


@dataclass
class TwilioMessage:
    sid: str
    phone_number: str
    body: str
    provider: str = "sms"


class TwilioClient:
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number

    @classmethod
    def default(cls) -> "TwilioClient":
        from credentials.models import PlatformCredentialKey
        from credentials.services import get_platform_credential

        from_number = get_platform_credential(PlatformCredentialKey.TWILIO_FROM_NUMBER, default="")

        return cls(
            account_sid=get_platform_credential(PlatformCredentialKey.TWILIO_ACCOUNT_SID, default=""),
            auth_token=get_platform_credential(PlatformCredentialKey.TWILIO_AUTH_TOKEN, default=""),
            from_number=get_platform_credential(PlatformCredentialKey.TWILIO_FROM_NUMBER, default=""),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token)

    def send_sms(self, to_phone_number: str, body: str) -> str:
        if not self.is_configured:
            raise TwilioError("Cannot send Twilio SMS: credentials are not configured.")

        try:
            response = requests.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json",
                data={"To": to_phone_number, "From": self.from_number, "Body": body},
                auth=(self.account_sid, self.auth_token),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise TwilioError(f"Twilio send failed: {exc}") from exc

        try:
            payload = response.json()
        except ValueError:
            payload = {}

        if not response.ok:
            detail = payload.get("message") or payload.get("error_message") or response.text[:200]
            raise TwilioError(f"Twilio send failed ({response.status_code}): {detail}")

        return str(payload.get("sid") or "")

    @staticmethod
    def validate_signature(url: str, params: Any, signature: str, auth_token: str) -> bool:
        if not auth_token or not signature:
            return False

        if hasattr(params, "lists"):
            parameter_items = params.lists()
        else:
            parameter_items = ((key, [value]) for key, value in params.items())

        signed_data = url
        for key, values in sorted(parameter_items):
            for value in sorted(values):
                signed_data += f"{key}{value}"

        digest = hmac.new(auth_token.encode("utf-8"), signed_data.encode("utf-8"), hashlib.sha1).digest()
        expected = base64.b64encode(digest).decode("ascii")
        return hmac.compare_digest(expected, signature)

    def parse_inbound_webhook(self, payload: dict, request=None) -> list:
        raw_messages = []
        if request is not None:
            form = request.POST or {}
            if form.get("Body"):
                raw_messages.append(form)
        elif isinstance(payload, dict):
            for key in ("Body", "From"):
                if payload.get(key):
                    raw_messages.append(payload)
                    break

        messages: list[TwilioMessage] = []
        for item in raw_messages:
            from_number = (item.get("From") or "").strip()
            body = (item.get("Body") or "").strip()
            sid = (item.get("MessageSid") or item.get("SmsMessageSid") or "").strip()
            if from_number and body:
                messages.append(
                    TwilioMessage(
                        sid=sid,
                        phone_number=from_number,
                        body=body,
                        provider="sms",
                    )
                )
        return messages
