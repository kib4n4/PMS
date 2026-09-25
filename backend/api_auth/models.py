# backend/api_auth/models.py

"""
External-integrator credentials for the OAuth2 client-credentials grant
(POST /api/oauth/token/). This is the "customer key and customer secret"
mechanism for third parties to integrate with the platform — distinct
from the `credentials` app, which holds secrets THIS platform uses to
call OUT to Daraja/WhatsApp/Resend/KRA. This app is the reverse
direction: secrets external parties use to call INTO this platform.
"""

import secrets
import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.db import models


class Scope(models.TextChoices):
    """
    Fixed registry of scope strings a `PlatformApiClient` may be granted.
    Before this existed, `scopes` was unvalidated free-text JSON — a typo
    here silently produced a client that could never be authorized for
    anything. Extend this list (not the raw string) when a new external
    endpoint needs a new scope.
    """

    INVOICES_READ = "invoices:read", "Read landlord invoices"
    PAYMENTS_READ = "payments:read", "Read landlord payments"
    TICKETS_READ = "tickets:read", "Read landlord maintenance tickets"
    LEASES_READ = "leases:read", "Read landlord leases"
    DISBURSEMENTS_READ = "disbursements:read", "Read platform payouts (platform-wide clients only)"


class PlatformApiClient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, help_text="Human-readable integrator name, e.g. 'Acme Accounting'")
    client_id = models.CharField(max_length=64, unique=True, editable=False)
    client_secret_hash = models.CharField(max_length=255, editable=False)
    landlord = models.ForeignKey(
        "landlords.Landlord",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="api_clients",
        help_text="Scopes this client to one landlord's data. Blank = platform-wide (super-admin-issued only).",
    )
    scopes = models.JSONField(default=list, blank=True, help_text="e.g. ['invoices:read', 'payments:read']")
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.client_id})"

    @staticmethod
    def _validate_scopes(scopes):
        unknown = sorted(set(scopes) - set(Scope.values))
        if unknown:
            raise ValidationError(f"Unknown scope(s): {', '.join(unknown)}. Valid scopes: {', '.join(Scope.values)}.")

    def clean(self):
        super().clean()
        self._validate_scopes(self.scopes or [])

    @classmethod
    def generate(cls, name: str, scopes=None, landlord=None):
        """
        Creates a new client and returns (instance, plaintext_secret).
        The plaintext secret is only ever available here, at creation
        time — it's hashed immediately and cannot be recovered later;
        use `rotate_secret()` to issue a new one for an existing client.
        """
        scopes = scopes or []
        cls._validate_scopes(scopes)
        client_id = f"pms_{secrets.token_hex(8)}"
        plaintext_secret = secrets.token_urlsafe(32)
        instance = cls.objects.create(
            name=name,
            client_id=client_id,
            client_secret_hash=make_password(plaintext_secret),
            scopes=scopes,
            landlord=landlord,
        )
        return instance, plaintext_secret

    def rotate_secret(self) -> str:
        """
        Issues a new plaintext secret for this client without touching its
        client_id/scopes/landlord binding or audit history. The old secret
        stops working immediately. Returns the new plaintext secret — like
        `generate()`, it is only ever available here, at rotation time.
        """
        plaintext_secret = secrets.token_urlsafe(32)
        self.client_secret_hash = make_password(plaintext_secret)
        self.save(update_fields=["client_secret_hash"])
        return plaintext_secret

    def verify_secret(self, plaintext_secret: str) -> bool:
        return check_password(plaintext_secret, self.client_secret_hash)

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes
