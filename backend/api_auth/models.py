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
from django.db import models


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

    @classmethod
    def generate(cls, name: str, scopes=None, landlord=None):
        """
        Creates a new client and returns (instance, plaintext_secret).
        The plaintext secret is only ever available here, at creation
        time — it's hashed immediately and cannot be recovered later,
        only rotated (delete + regenerate).
        """
        client_id = f"pms_{secrets.token_hex(8)}"
        plaintext_secret = secrets.token_urlsafe(32)
        instance = cls.objects.create(
            name=name,
            client_id=client_id,
            client_secret_hash=make_password(plaintext_secret),
            scopes=scopes or [],
            landlord=landlord,
        )
        return instance, plaintext_secret

    def verify_secret(self, plaintext_secret: str) -> bool:
        return check_password(plaintext_secret, self.client_secret_hash)

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes
