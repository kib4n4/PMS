# backend/integrations/daraja.py

"""
Safaricom Daraja API client — real HTTP calls.

Credential resolution (for_landlord/for_platform) reads real, DB-driven
encrypted credentials (LandlordDarajaCredential fields, PlatformCredential
rows) via the `credentials` app — rotating a key is an admin-panel edit,
not a redeploy.

Every Daraja operation here (STK Push, B2C, transaction status) is
asynchronous by Safaricom's own design: the synchronous HTTP response is
only an acknowledgment that the request was accepted (ResponseCode/
CheckoutRequestID/ConversationID) — the actual outcome always arrives
later on a callback URL. Callers must not treat a successful call to
initiate_stk_push/initiate_b2c_payment/query_transaction_status as
"payment succeeded" — that only happens when the matching webhook lands
(billing/webhook_views.py, billing/tasks.py).

Two distinct credential contexts, per the design doc:
  - Per-landlord: STK Push / C2B, using that landlord's own shortcode
    (LandlordDarajaCredential).
  - Platform-owned: STK Push/paybill for FeeInvoice collection, and B2C
    for Reseller/Investor payouts — a single, separate Daraja app.
"""

import base64
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

SANDBOX_BASE_URL = "https://sandbox.safaricom.co.ke"
LIVE_BASE_URL = "https://api.safaricom.co.ke"
REQUEST_TIMEOUT_SECONDS = 15

# Access tokens are valid ~1hr per Daraja docs. Cached per consumer_key
# (module-level — fine for a single-process worker; each Celery worker
# process gets its own cache, which just means a few extra token fetches,
# not a correctness issue) with a safety margin so we never hand out a
# token that's about to expire mid-request.
_TOKEN_CACHE: dict = {}
_TOKEN_SAFETY_MARGIN_SECONDS = 60


class DarajaError(Exception):
    """Raised when Safaricom returns a non-success response."""


@dataclass
class STKPushResult:
    checkout_request_id: str
    merchant_request_id: str
    response_description: str


@dataclass
class B2CResult:
    conversation_id: str
    originator_conversation_id: str
    response_description: str


class DarajaClient:
    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        shortcode: str,
        environment: str = "sandbox",
        passkey: str = "",
        initiator_name: str = "",
        security_credential: str = "",
    ):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.shortcode = shortcode
        self.environment = environment
        self.passkey = passkey
        self.initiator_name = initiator_name
        self.security_credential = security_credential

    @property
    def base_url(self) -> str:
        return LIVE_BASE_URL if self.environment == "live" else SANDBOX_BASE_URL

    @classmethod
    def for_landlord(cls, landlord_credential) -> "DarajaClient":
        """
        Build a client scoped to a specific landlord's own paybill.
        `landlord_credential` is a landlords.models.LandlordDarajaCredential
        — its secret fields are EncryptedSecretFields, so reading them
        here already returns the decrypted value (credentials/fields.py).
        """
        return cls(
            consumer_key=landlord_credential.consumer_key,
            consumer_secret=landlord_credential.consumer_secret,
            shortcode=landlord_credential.shortcode,
            environment=landlord_credential.environment,
            passkey=landlord_credential.passkey,
            initiator_name=landlord_credential.initiator_credential,
            security_credential=landlord_credential.security_credential,
        )

    @classmethod
    def for_platform(cls) -> "DarajaClient":
        """Platform's OWN Daraja app — FeeInvoice collection and
        Reseller/Investor B2C payouts only. Reads DB-driven
        PlatformCredential rows (credentials app), not environment vars."""
        from credentials.models import PlatformCredentialKey
        from credentials.services import get_platform_credential

        return cls(
            consumer_key=get_platform_credential(PlatformCredentialKey.PLATFORM_DARAJA_CONSUMER_KEY, default=""),
            consumer_secret=get_platform_credential(
                PlatformCredentialKey.PLATFORM_DARAJA_CONSUMER_SECRET, default=""
            ),
            shortcode=get_platform_credential(PlatformCredentialKey.PLATFORM_DARAJA_SHORTCODE, default=""),
            passkey=get_platform_credential(PlatformCredentialKey.PLATFORM_DARAJA_PASSKEY, default=""),
            initiator_name=get_platform_credential(
                PlatformCredentialKey.PLATFORM_DARAJA_INITIATOR_CREDENTIAL, default=""
            ),
            security_credential=get_platform_credential(
                PlatformCredentialKey.PLATFORM_DARAJA_SECURITY_CREDENTIAL, default=""
            ),
        )

    # -- auth -----------------------------------------------------------

    def _get_access_token(self) -> str:
        cached = _TOKEN_CACHE.get(self.consumer_key)
        if cached and cached[1] > time.time():
            return cached[0]

        try:
            response = requests.get(
                f"{self.base_url}/oauth/v1/generate",
                params={"grant_type": "client_credentials"},
                auth=(self.consumer_key, self.consumer_secret),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
            token = data["access_token"]
        except requests.RequestException as exc:
            raise DarajaError(f"Daraja OAuth token request failed: {exc}") from exc
        except (ValueError, KeyError) as exc:
            raise DarajaError(f"Daraja OAuth token response was not valid: {exc}") from exc

        expires_in = int(data.get("expires_in", 3599))
        _TOKEN_CACHE[self.consumer_key] = (token, time.time() + expires_in - _TOKEN_SAFETY_MARGIN_SECONDS)
        return token

    def _post(self, path: str, payload: dict) -> dict:
        # _get_access_token() itself always raises DarajaError, not a raw
        # requests exception (see above) — safe to call outside the
        # try/except below, which only needs to cover the POST itself.
        headers = {"Authorization": f"Bearer {self._get_access_token()}"}
        try:
            response = requests.post(
                f"{self.base_url}{path}", json=payload, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS
            )
        except requests.RequestException as exc:
            raise DarajaError(f"Daraja {path} request failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError:
            if not response.ok:
                raise DarajaError(f"Daraja {path} failed ({response.status_code}): {response.text[:200]}")
            raise DarajaError(f"Non-JSON response from Daraja {path}: {response.text[:200]}")

        if not response.ok:
            raise DarajaError(f"Daraja {path} failed ({response.status_code}): {data}")
        return data

    # -- requests ---------------------------------------------------------

    def initiate_stk_push(self, phone_number: str, amount: str, account_reference: str) -> STKPushResult:
        """
        STK Push to collect rent (landlord-scoped) or a fee payment
        (platform-scoped). Returns an ACKNOWLEDGMENT only — the actual
        result (user entered PIN / cancelled / timed out) arrives later
        on CallBackURL (billing/webhook_views.py::mpesa_stk_callback).
        """
        if not self.passkey:
            raise DarajaError(f"Cannot initiate STK Push for {self.shortcode}: no passkey configured.")

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(f"{self.shortcode}{self.passkey}{timestamp}".encode()).decode()

        data = self._post(
            "/mpesa/stkpush/v1/processrequest",
            {
                "BusinessShortCode": self.shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": str(amount),
                "PartyA": phone_number,
                "PartyB": self.shortcode,
                "PhoneNumber": phone_number,
                "CallBackURL": f"{settings.PUBLIC_BASE_URL}/webhooks/mpesa/stk/callback/",
                "AccountReference": account_reference[:20],
                "TransactionDesc": "Rent payment"[:100],
            },
        )
        return STKPushResult(
            checkout_request_id=data["CheckoutRequestID"],
            merchant_request_id=data["MerchantRequestID"],
            response_description=data.get("ResponseDescription", ""),
        )

    def initiate_b2c_payment(
        self, phone_number: str, amount: str, remarks: str, occasion: Optional[str] = None
    ) -> B2CResult:
        """
        B2C payout — only ever platform-scoped (Reseller/Investor
        payouts). Returns an ACKNOWLEDGMENT only — the actual result
        arrives later on ResultURL
        (billing/webhook_views.py::mpesa_b2c_result / mpesa_b2c_timeout).
        """
        if not (self.initiator_name and self.security_credential):
            raise DarajaError("Cannot initiate B2C payment: initiator credentials not configured.")

        data = self._post(
            "/mpesa/b2c/v1/paymentrequest",
            {
                "InitiatorName": self.initiator_name,
                "SecurityCredential": self.security_credential,
                "CommandID": "BusinessPayment",
                "Amount": str(amount),
                "PartyA": self.shortcode,
                "PartyB": phone_number,
                "Remarks": remarks[:100],
                "QueueTimeOutURL": f"{settings.PUBLIC_BASE_URL}/webhooks/mpesa/b2c/timeout/",
                "ResultURL": f"{settings.PUBLIC_BASE_URL}/webhooks/mpesa/b2c/result/",
                "Occasion": (occasion or "")[:100],
            },
        )
        return B2CResult(
            conversation_id=data["ConversationID"],
            originator_conversation_id=data["OriginatorConversationID"],
            response_description=data.get("ResponseDescription", ""),
        )

    def query_transaction_status(self, transaction_id: str) -> dict:
        """
        Used by the nightly reconciliation job. Returns an ACKNOWLEDGMENT
        only — the actual status arrives later on ResultURL
        (billing/webhook_views.py::mpesa_transaction_status_result).
        """
        if not (self.initiator_name and self.security_credential):
            raise DarajaError("Cannot query transaction status: initiator credentials not configured.")

        return self._post(
            "/mpesa/transactionstatus/v1/query",
            {
                "Initiator": self.initiator_name,
                "SecurityCredential": self.security_credential,
                "CommandID": "TransactionStatusQuery",
                "TransactionID": transaction_id,
                "PartyA": self.shortcode,
                "IdentifierType": "4",
                "ResultURL": f"{settings.PUBLIC_BASE_URL}/webhooks/mpesa/transactionstatus/result/",
                "QueueTimeOutURL": f"{settings.PUBLIC_BASE_URL}/webhooks/mpesa/transactionstatus/timeout/",
                "Remarks": "Reconciliation check",
                "Occasion": "Reconciliation",
            },
        )
