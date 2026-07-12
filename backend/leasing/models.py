import uuid

from django.conf import settings
from django.db import models


class Tenant(models.Model):
    """Phone-number-first identity for tenants."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tenant_profile"
    )
    full_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


class LeaseStatus(models.TextChoices):
    APPLICATION = "application", "Application"
    ACTIVE = "active", "Active"
    RENEWAL_PENDING = "renewal_pending", "Renewal Pending"
    TERMINATED = "terminated", "Terminated"


class Lease(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit = models.ForeignKey("properties.Unit", on_delete=models.PROTECT, related_name="leases")
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="leases")
    rent_amount = models.DecimalField(max_digits=12, decimal_places=2)
    billing_day = models.PositiveSmallIntegerField(help_text="Day of month rent is due (1-28)")
    deposit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20, choices=LeaseStatus.choices, default=LeaseStatus.APPLICATION
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tenant.full_name} @ {self.unit} ({self.status})"
