# backend/accounts/models.py

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

    NOTE: identity lookup (who you're logging in as) stays phone-first —
    only the OTP *delivery channel* is now email via Resend (see
    OTPRequest below and accounts/services/otp.py), so a user needs a
    verified email on file to complete OTP login.
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
    One-time-password requests for phone-first login. The code is now
    delivered via Resend to the user's email (see accounts/services/otp.py)
    rather than WhatsApp/SMS — `phone_number` remains the identity lookup
    key, `email` is where the code actually gets sent.
    """

    class Channel(models.TextChoices):
        EMAIL = "email", "Email (Resend)"
        WHATSAPP = "whatsapp", "WhatsApp (legacy, unused)"
        SMS = "sms", "SMS (legacy, unused)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True, default="")
    code_hash = models.CharField(max_length=128)
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.EMAIL)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["phone_number", "expires_at"])]

    def __str__(self):
        return f"OTP for {self.phone_number} ({'used' if self.consumed_at else 'pending'})"