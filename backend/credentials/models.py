# backend/credentials/models.py

import uuid

from django.conf import settings
from django.db import models

from .fields import EncryptedSecretField


class PlatformCredentialKey(models.TextChoices):
    """
    Every platform-level (not per-landlord) secret the platform needs.
    Adding a new integration means adding a choice here and reading it
    via credentials.services.get_platform_credential — not a new
    settings.py env var. That's the point of DB-driven platform keys.
    """

    RESEND_API_KEY = "resend_api_key", "Resend API Key"
    RESEND_FROM_EMAIL = "resend_from_email", "Resend \"From\" Address"
    PLATFORM_DARAJA_CONSUMER_KEY = "platform_daraja_consumer_key", "Platform Daraja Consumer Key"
    PLATFORM_DARAJA_CONSUMER_SECRET = "platform_daraja_consumer_secret", "Platform Daraja Consumer Secret"
    PLATFORM_DARAJA_SHORTCODE = "platform_daraja_shortcode", "Platform Daraja Shortcode"
    PLATFORM_DARAJA_INITIATOR_CREDENTIAL = (
        "platform_daraja_initiator_credential", "Platform Daraja Initiator Credential"
    )
    PLATFORM_DARAJA_SECURITY_CREDENTIAL = (
        "platform_daraja_security_credential", "Platform Daraja Security Credential"
    )
    PLATFORM_DARAJA_PASSKEY = "platform_daraja_passkey", "Platform Daraja Lipa Na M-Pesa Passkey"
    WHATSAPP_ACCESS_TOKEN = "whatsapp_access_token", "WhatsApp Cloud API Access Token"
    WHATSAPP_PHONE_NUMBER_ID = "whatsapp_phone_number_id", "WhatsApp Phone Number ID"
    WHATSAPP_VERIFY_TOKEN = "whatsapp_verify_token", "WhatsApp Webhook Verify Token"
    WHATSAPP_APP_SECRET = "whatsapp_app_secret", "WhatsApp App Secret"
    TWILIO_ACCOUNT_SID = "twilio_account_sid", "Twilio Account SID"
    TWILIO_AUTH_TOKEN = "twilio_auth_token", "Twilio Auth Token"
    TWILIO_FROM_NUMBER = "twilio_from_number", "Twilio From Number"
    TWILIO_WEBHOOK_AUTH_TOKEN = "twilio_webhook_auth_token", "Twilio Webhook Auth Token"


class PlatformCredential(models.Model):
    """
    Single source of truth for every platform-level third-party secret —
    one row per key, encrypted at rest via EncryptedSecretField, editable
    from Django admin or the super-admin-only API (credentials/views.py,
    added when a phase actually needs to edit these outside admin).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=64, choices=PlatformCredentialKey.choices, unique=True)
    value = EncryptedSecretField(blank=True)
    environment = models.CharField(
        max_length=10,
        choices=[("sandbox", "Sandbox"), ("live", "Live")],
        default="sandbox",
        help_text="Informational only for keys that aren't environment-specific.",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return f"{self.get_key_display()} ({self.environment})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from .services import invalidate_platform_credential_cache

        invalidate_platform_credential_cache(self.key)

    def delete(self, *args, **kwargs):
        key = self.key
        super().delete(*args, **kwargs)
        from .services import invalidate_platform_credential_cache

        invalidate_platform_credential_cache(key)
