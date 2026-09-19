# backend/landlords/models.py

import uuid

from django.conf import settings
from django.db import models


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
    Each landlord's own Paybill/Till and Daraja app credentials (Option B).
    Secrets fields below are placeholders for values that MUST live in a
    real secrets manager (Vault / cloud secrets manager) in production —
    this model stores only references/metadata, never raw secrets, once
    wired to the real secrets backend. Until then, do not populate the
    *_secret_ref fields with anything but a secrets-manager key path.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    landlord = models.OneToOneField(
        Landlord, on_delete=models.CASCADE, related_name="daraja_credential"
    )
    shortcode = models.CharField(max_length=20, unique=True)
    environment = models.CharField(
        max_length=10, choices=[("sandbox", "Sandbox"), ("live", "Live")], default="sandbox"
    )
    consumer_key_secret_ref = models.CharField(
        max_length=255, help_text="Secrets-manager key path, not the raw value"
    )
    consumer_secret_secret_ref = models.CharField(max_length=255)
    initiator_credential_secret_ref = models.CharField(max_length=255)
    security_credential_secret_ref = models.CharField(max_length=255)
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
