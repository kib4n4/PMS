# backend/landlords/models.py

import uuid

from django.conf import settings
from django.db import models

from credentials.fields import EncryptedSecretField


class Organization(models.Model):
    """Top-level tenant. The management company (e.g. Dime Consultants)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Landlord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="landlords"
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="landlord_profile"
    )
    full_name = models.CharField(max_length=255)
    # Option B: each landlord may be referred by a Reseller. Nullable —
    # not every landlord comes through a referral.
    referred_by = models.ForeignKey(
        "partners.Reseller",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referred_landlords",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


class OnboardingStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SANDBOX_TESTING = "sandbox_testing", "Sandbox Testing"
    AWAITING_C2B_URL_REGISTRATION = (
        "awaiting_c2b_url_registration",
        "Awaiting C2B URL Registration on Safaricom Portal",
    )
    LIVE = "live", "Live"
    SUSPENDED = "suspended", "Suspended"


class LandlordDarajaCredential(models.Model):
    """
    Each landlord's own Paybill/Till and Daraja app credentials (Option B)
    — this is also the canonical landlord↔payment-info link: a landlord's
    payment identity IS their shortcode + these credentials, looked up as
    `landlord.daraja_credential`. Secret fields are encrypted at rest in
    Postgres (EncryptedSecretField, backed by CREDENTIAL_ENCRYPTION_KEY)
    rather than routed through an external secrets manager — DB-driven by
    design, editable from admin without a redeploy.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    landlord = models.OneToOneField(
        Landlord, on_delete=models.CASCADE, related_name="daraja_credential"
    )
    shortcode = models.CharField(max_length=20, unique=True)
    environment = models.CharField(
        max_length=10, choices=[("sandbox", "Sandbox"), ("live", "Live")], default="sandbox"
    )
    consumer_key = EncryptedSecretField(help_text="Daraja app Consumer Key for this shortcode — encrypted at rest.")
    consumer_secret = EncryptedSecretField(help_text="Daraja app Consumer Secret — encrypted at rest.")
    passkey = EncryptedSecretField(
        blank=True, help_text="Lipa Na M-Pesa Online Passkey — required to initiate STK Push. Encrypted at rest."
    )
    initiator_credential = EncryptedSecretField(
        blank=True, help_text="B2C initiator username, if this landlord ever originates payouts — encrypted at rest."
    )
    security_credential = EncryptedSecretField(
        blank=True, help_text="B2C initiator password (Safaricom-cert-encrypted, then encrypted again at rest)."
    )
    status = models.CharField(
        max_length=40, choices=OnboardingStatus.choices, default=OnboardingStatus.PENDING
    )
    c2b_urls_registered = models.BooleanField(
        default=False,
        help_text="Manual step: landlord/admin must register C2B validation/"
        "confirmation URLs for this shortcode on Safaricom's portal.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.landlord.full_name} — {self.shortcode} ({self.status})"
class LandlordWhatsAppCredential(models.Model):
    """Per-landlord WhatsApp Cloud API credential references.

    Stores secret references (secrets-manager key paths) for the access token
    and phone_number_id. The real secrets must be resolved via a secrets
    manager in production; this model only stores the reference paths.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    landlord = models.OneToOneField(
        Landlord, on_delete=models.CASCADE, related_name="whatsapp_credential"
    )
    environment = models.CharField(
        max_length=10, choices=[("sandbox", "Sandbox"), ("live", "Live")], default="sandbox"
    )
    access_token_secret_ref = models.CharField(
        max_length=255, help_text="Secrets-manager key path for the WhatsApp access token"
    )
    phone_number_id_secret_ref = models.CharField(
        max_length=255, help_text="Secrets-manager key path for the phone number id"
    )
    status = models.CharField(max_length=40, choices=OnboardingStatus.choices, default=OnboardingStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.landlord.full_name} — WhatsApp ({self.status})"
