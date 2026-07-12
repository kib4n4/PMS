import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    ADMIN = "admin", "Admin / Dime Staff"
    LANDLORD = "landlord", "Landlord"
    TENANT = "tenant", "Tenant"
    RESELLER = "reseller", "Reseller"
    INVESTOR = "investor", "Investor"
    CARETAKER = "caretaker", "Caretaker"


class User(AbstractUser):
    """
    Phone-number-first identity for tenants/caretakers/resellers/investors/
    landlords (OTP login). Admin/staff can still use username+password.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_number = models.CharField(
        max_length=20, unique=True, null=True, blank=True,
        help_text="E.164 format, e.g. +2547XXXXXXXX",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    is_phone_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.phone_number or self.username or str(self.id)


class OTPRequest(models.Model):
    """
    One-time-password requests for phone-first login, delivered via
    WhatsApp (primary) or SMS (fallback). Kept separate from User so OTP
    churn doesn't bloat the auth table.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_number = models.CharField(max_length=20)
    code_hash = models.CharField(max_length=128)
    channel = models.CharField(
        max_length=10, choices=[("whatsapp", "WhatsApp"), ("sms", "SMS")],
        default="whatsapp",
    )
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["phone_number", "expires_at"])]

    def __str__(self):
        return f"OTP for {self.phone_number} ({'used' if self.consumed_at else 'pending'})"
