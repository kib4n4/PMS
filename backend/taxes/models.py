# backend/taxes/models.py

import uuid

from django.db import models

from credentials.fields import EncryptedSecretField


class KRACredentialStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"


class LandlordKRACredential(models.Model):
    """
    Each landlord's own KRA identity + API credentials for filing their
    Monthly Rental Income (MRI) return — DB-driven and encrypted at rest
    (EncryptedSecretField, credentials app), same pattern as
    LandlordDarajaCredential. The PIN itself is a public-ish tax
    identifier (shown on filings/receipts), not a secret, so it's a
    plain field; the API client id/secret are.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    landlord = models.OneToOneField(
        "landlords.Landlord", on_delete=models.CASCADE, related_name="kra_credential"
    )
    kra_pin = models.CharField(max_length=20, unique=True, help_text="e.g. A123456789Z")
    environment = models.CharField(
        max_length=10, choices=[("sandbox", "Sandbox"), ("production", "Production")], default="sandbox"
    )
    client_id = EncryptedSecretField(blank=True, help_text="KRA API client ID — encrypted at rest.")
    client_secret = EncryptedSecretField(blank=True, help_text="KRA API client secret — encrypted at rest.")
    status = models.CharField(max_length=20, choices=KRACredentialStatus.choices, default=KRACredentialStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.landlord.full_name} — {self.kra_pin} ({self.status})"


class RentalIncomeReturnStatus(models.TextChoices):
    PENDING = "pending", "Pending Submission"
    SUBMITTED = "submitted", "Submitted"
    ACCEPTED = "accepted", "Accepted by KRA"
    REJECTED = "rejected", "Rejected by KRA"
    NOT_CONFIGURED = "not_configured", "Landlord Has No KRA Credential"


# Kenya's Monthly Rental Income tax: a flat 7.5% of GROSS rent received
# (Finance Act 2020, effective Jan 2021) — a final withholding-style tax
# for individual landlords, not net-of-expenses. TODO(future phase): real
# per-landlord bracket/regime handling (the flat rate assumes every
# landlord is in the standard MRI regime, which isn't universally true).
MRI_TAX_RATE = 0.075


class RentalIncomeReturn(models.Model):
    """
    One row per landlord per filing period — the MRI return itself.
    gross_rental_income is summed from confirmed billing.Payment records
    for the period; tax_due is computed, never entered by hand.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    landlord = models.ForeignKey(
        "landlords.Landlord", on_delete=models.PROTECT, related_name="rental_income_returns"
    )
    period_start = models.DateField()
    period_end = models.DateField()
    gross_rental_income = models.DecimalField(max_digits=12, decimal_places=2)
    tax_due = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=RentalIncomeReturnStatus.choices, default=RentalIncomeReturnStatus.PENDING
    )
    kra_reference = models.CharField(max_length=100, blank=True, help_text="Acknowledgement/reference number from KRA, once filed")
    failure_reason = models.CharField(max_length=255, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("landlord", "period_start", "period_end")
        ordering = ["-period_start"]

    def __str__(self):
        return f"MRI return {self.landlord.full_name} {self.period_start}–{self.period_end} ({self.status})"
