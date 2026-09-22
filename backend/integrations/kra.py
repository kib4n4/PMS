# backend/integrations/kra.py

"""
Kenya Revenue Authority (KRA) client — STUBBED.

Unlike Safaricom Daraja, KRA has no self-serve public sandbox: real
access to file Monthly Rental Income (MRI) returns programmatically
requires KRA-issued API credentials via their iTax / Tax Invoice
Management System (eTIMS) onboarding process, which is an external
approval/registration step, not something this codebase can wire up on
its own. Every method below is a clearly-marked stub returning realistic
shapes so the rest of the codebase (models, Celery tasks) can be built
and tested against it now — mirrors how integrations/daraja.py and
integrations/whatsapp.py were built before real Safaricom/Meta access
existed.

WHEN REAL KRA API ACCESS EXISTS, replace the body of each method with
the real call. Nothing else in the codebase should need to change —
callers only depend on these method signatures.
"""

from dataclasses import dataclass


@dataclass
class ReturnSubmissionResult:
    kra_reference: str
    status: str
    message: str


class KRAClient:
    def __init__(self, client_id: str, client_secret: str, kra_pin: str, environment: str = "sandbox"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.kra_pin = kra_pin
        self.environment = environment

    @classmethod
    def for_landlord(cls, kra_credential) -> "KRAClient":
        """
        `kra_credential` is a taxes.models.LandlordKRACredential — its
        client_id/client_secret are EncryptedSecretFields, so reading
        them here already returns the decrypted value (DB-driven, same
        pattern as DarajaClient.for_landlord).
        """
        return cls(
            client_id=kra_credential.client_id,
            client_secret=kra_credential.client_secret,
            kra_pin=kra_credential.kra_pin,
            environment=kra_credential.environment,
        )

    def submit_rental_income_return(
        self, period_start: str, period_end: str, gross_rental_income: str, tax_due: str
    ) -> ReturnSubmissionResult:
        """File a Monthly Rental Income return for this landlord's KRA PIN.
        TODO(KRA): real iTax/eTIMS call once KRA API access is granted."""
        raise NotImplementedError(
            "KRAClient.submit_rental_income_return is a stub — wire real KRA "
            "API credentials and HTTP call once KRA grants API access for this PIN."
        )

    def check_pin_status(self) -> dict:
        """Validate the configured KRA PIN is active/in good standing
        before attempting a filing. TODO(KRA): real PIN Checker API call."""
        raise NotImplementedError(
            "KRAClient.check_pin_status is a stub — wire real KRA API "
            "credentials and HTTP call once KRA grants API access."
        )
