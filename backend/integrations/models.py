# backend/integrations/models.py
"""DB-driven credentials for external integration providers.

Replaces the old TODO(M3)-style stubs that referenced a not-yet-built
secrets manager. Credentials live in Postgres, encrypted at rest with
Fernet (see settings.FIELD_ENCRYPTION_KEY), and are scoped per-landlord
when the integration is per-landlord (each landlord's own Twilio WhatsApp
sender), or left platform-wide (landlord=None) for account-level
integrations like Resend/OTP.
"""

import json
import uuid

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


class Provider(models.TextChoices):
    TWILIO = "twilio", "Twilio (WhatsApp)"
    RESEND = "resend", "Resend (Email/OTP)"
    DARAJA = "daraja", "Safaricom Daraja (M-Pesa)"


class AuthType(models.TextChoices):
    JSON = "json", "JSON blob (legacy)"
    OAUTH2 = "oauth2", "OAuth2 (Client ID & Secret)"
    BEARER = "bearer", "Bearer token"


class ProviderCredential(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    landlord = models.ForeignKey(
        "landlords.Landlord",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="provider_credentials",
        help_text="Null for platform-level credentials (e.g. the shared Resend account).",
    )
    provider = models.CharField(max_length=20, choices=Provider.choices)
    label = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional human label, e.g. 'primary WhatsApp number'.",
    )

    # Select how credentials are stored/entered in the UI
    auth_type = models.CharField(
        max_length=20,
        choices=AuthType.choices,
        default=AuthType.JSON,
        help_text="Choose how this provider's credentials are stored (JSON legacy, OAuth2 fields, or Bearer token).",
    )

    # Per-field encrypted storage for structured auth types
    encrypted_client_id = models.TextField(null=True, blank=True, help_text="Fernet-encrypted client_id for OAuth2.")
    encrypted_client_secret = models.TextField(null=True, blank=True, help_text="Fernet-encrypted client_secret for OAuth2.")
    encrypted_bearer_token = models.TextField(null=True, blank=True, help_text="Fernet-encrypted bearer token.")

    # Legacy/other providers: encrypted JSON blob
    ciphertext = models.TextField(
        null=True,
        blank=True,
        help_text="Fernet-encrypted JSON blob — use set_credentials()/get_credentials(), never edit directly.",
    )

    # Provider-specific metadata (encrypted JSON), e.g. whatsapp_number for Twilio
    encrypted_metadata = models.TextField(
        null=True,
        blank=True,
        help_text="Fernet-encrypted JSON blob for provider metadata (e.g. whatsapp_number)",
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["provider", "landlord", "is_active", "auth_type"]) ]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "landlord"],
                condition=models.Q(is_active=True),
                name="unique_active_credential_per_provider_landlord",
            )
        ]

    def __str__(self):
        scope = self.landlord_id or "platform"
        return f"{self.get_provider_display()} ({scope})"

    # -- encryption helpers -------------------------------------------------

    @staticmethod
    def _fernet() -> Fernet:
        key = settings.FIELD_ENCRYPTION_KEY
        return Fernet(key.encode() if isinstance(key, str) else key)

    def _encrypt(self, plaintext: str) -> str:
        return self._fernet().encrypt(plaintext.encode()).decode()

    def _decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet().decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise ValueError(
                f"Could not decrypt credentials for {self} — has FIELD_ENCRYPTION_KEY changed since this row was written?"
            ) from exc

    # -- setters for different UI modes -------------------------------------

    def set_credentials(self, data: dict) -> None:
        """Legacy: store an arbitrary JSON blob. Caller must call .save()."""
        payload = json.dumps(data).encode()
        self.ciphertext = self._fernet().encrypt(payload).decode()
        self.auth_type = AuthType.JSON
        # clear structured fields
        self.encrypted_client_id = None
        self.encrypted_client_secret = None
        self.encrypted_bearer_token = None

    def set_oauth2_credentials(self, client_id: str, client_secret: str) -> None:
        """Store OAuth2 client id/secret in dedicated DB columns.
        Caller still needs to call .save()."""
        self.encrypted_client_id = self._encrypt(client_id)
        self.encrypted_client_secret = self._encrypt(client_secret)
        self.encrypted_bearer_token = None
        self.ciphertext = None
        self.auth_type = AuthType.OAUTH2

    def set_bearer_token(self, token: str) -> None:
        """Store a bearer/auth token in a dedicated DB column. Caller must call .save()."""
        self.encrypted_bearer_token = self._encrypt(token)
        self.encrypted_client_id = None
        self.encrypted_client_secret = None
        self.ciphertext = None
        self.auth_type = AuthType.BEARER

    # -- metadata helpers ---------------------------------------------------

    def set_metadata(self, data: dict) -> None:
        """Store provider-specific metadata as encrypted JSON. Caller should .save()."""
        payload = json.dumps(data).encode()
        self.encrypted_metadata = self._fernet().encrypt(payload).decode()

    def get_metadata(self) -> dict:
        """Return provider metadata dict (may be empty)."""
        if not self.encrypted_metadata:
            return {}
        try:
            payload = self._fernet().decrypt(self.encrypted_metadata.encode())
        except InvalidToken as exc:
            raise ValueError(
                f"Could not decrypt metadata for {self} — has FIELD_ENCRYPTION_KEY changed since this row was written?"
            ) from exc
        return json.loads(payload)

    # -- getters ------------------------------------------------------------

    def get_credentials(self) -> dict:
        """Return credentials as a dict appropriate to auth_type.

        - JSON: returns the stored dict from ciphertext (legacy)
        - OAUTH2: returns {"client_id": ..., "client_secret": ...}
        - BEARER: returns {"token": ...}
        """
        if self.auth_type == AuthType.JSON:
            if not self.ciphertext:
                return {}
            try:
                payload = self._fernet().decrypt(self.ciphertext.encode())
            except InvalidToken as exc:
                raise ValueError(
                    f"Could not decrypt credentials for {self} — has FIELD_ENCRYPTION_KEY changed since this row was written?"
                ) from exc
            return json.loads(payload)

        if self.auth_type == AuthType.OAUTH2:
            if not (self.encrypted_client_id and self.encrypted_client_secret):
                raise ValueError(f"OAuth2 credentials missing for {self}")
            return {
                "client_id": self._decrypt(self.encrypted_client_id),
                "client_secret": self._decrypt(self.encrypted_client_secret),
            }

        if self.auth_type == AuthType.BEARER:
            if not self.encrypted_bearer_token:
                raise ValueError(f"Bearer token missing for {self}")
            return {"token": self._decrypt(self.encrypted_bearer_token)}

        # Fallback: return empty
        return {}

    # -- lookup helper --------------------------------------------------------

    @classmethod
    def get_active(cls, provider: str, landlord=None) -> "ProviderCredential":
        """Raises ProviderCredential.DoesNotExist if no active row is found —
        callers decide whether to fall back to a platform-level default."""
        return cls.objects.get(provider=provider, landlord=landlord, is_active=True)
