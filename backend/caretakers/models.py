import uuid

from django.conf import settings
from django.db import models


class Caretaker(models.Model):
    """On-the-ground ops role. No commission, no PayoutAccount — access
    role only, distinct from Reseller/Investor."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="caretaker_profile"
    )
    full_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


class CaretakerAssignment(models.Model):
    """
    Effective-dated assignment of a Caretaker to a Property. Many-to-many
    with history preserved — caretakers change over time, and past
    assignments must remain queryable for audit/ticket-history purposes.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    caretaker = models.ForeignKey(Caretaker, on_delete=models.CASCADE, related_name="assignments")
    property = models.ForeignKey(
        "properties.Property", on_delete=models.CASCADE, related_name="caretaker_assignments"
    )
    effective_start = models.DateField()
    effective_end = models.DateField(null=True, blank=True, help_text="Null means currently active")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["property", "effective_start", "effective_end"])]

    def __str__(self):
        status = "active" if self.effective_end is None else "ended"
        return f"{self.caretaker.full_name} → {self.property.name} ({status})"
