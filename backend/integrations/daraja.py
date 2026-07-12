"""
Safaricom Daraja API client — STUBBED.

This module deliberately does not make real HTTP calls yet: this sandbox
has no network path to Safaricom's API, and no real Consumer Key/Secret
or initiator credentials exist for any landlord. Every method below is a
clearly-marked stub returning realistic shapes so the rest of the codebase
(models, Celery tasks, views) can be built and tested against it now.

WHEN REAL CREDENTIALS EXIST (M2 sign-off), replace the body of each method
with the real Daraja call. Nothing else in the codebase should need to
change — callers only depend on these method signatures.

Two distinct credential contexts, per the design doc:
  - Per-landlord: STK Push / C2B, using that landlord's own shortcode
    (LandlordDarajaCredential).
  - Platform-owned: STK Push/paybill for FeeInvoice collection, and B2C
    for Reseller/Investor payouts — a single, separate Daraja app.
"""

from dataclasses import dataclass
from typing import Optional


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
    def __init__(self, consumer_key: str, consumer_secret: str, shortcode: str, environment: str = "sandbox"):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.shortcode = shortcode
        self.environment = environment

    @classmethod
    def for_landlord(cls, landlord_credential) -> "DarajaClient":
        """
        Build a client scoped to a specific landlord's own paybill.
        `landlord_credential` is a landlords.models.LandlordDarajaCredential.
        Real implementation resolves consumer_key_secret_ref /
        consumer_secret_secret_ref via the secrets manager — never reads
        raw secrets from the DB.
        """
        # TODO(M2): resolve landlord_credential.consumer_key_secret_ref
        # and .consumer_secret_secret_ref via the secrets manager client.
        return cls(
            consumer_key="STUB",
            consumer_secret="STUB",
            shortcode=landlord_credential.shortcode,
            environment=landlord_credential.environment,
        )

    @classmethod
    def for_platform(cls) -> "DarajaClient":
        """Build a client for the platform's OWN Daraja app — used for
        FeeInvoice collection and Reseller/Investor B2C payouts only."""
        # TODO(M2): resolve platform Daraja credentials via secrets manager.
        return cls(consumer_key="STUB", consumer_secret="STUB", shortcode="STUB")

    def initiate_stk_push(self, phone_number: str, amount: str, account_reference: str) -> STKPushResult:
        """STK Push to collect rent (landlord-scoped) or a fee payment
        (platform-scoped). TODO(M2): real Daraja STK Push call."""
        raise NotImplementedError(
            "DarajaClient.initiate_stk_push is a stub — wire real Daraja "
            "credentials and HTTP call in M2 before use."
        )

    def initiate_b2c_payment(
        self, phone_number: str, amount: str, remarks: str, occasion: Optional[str] = None
    ) -> B2CResult:
        """B2C payout — only ever platform-scoped (Reseller/Investor
        payouts). TODO(M2): real Daraja B2C call."""
        raise NotImplementedError(
            "DarajaClient.initiate_b2c_payment is a stub — wire real "
            "Daraja credentials and HTTP call in M2 before use."
        )

    def query_transaction_status(self, transaction_id: str) -> dict:
        """Used by the nightly reconciliation job. TODO(M2): real call."""
        raise NotImplementedError(
            "DarajaClient.query_transaction_status is a stub — wire real "
            "Daraja credentials and HTTP call in M2 before use."
        )
