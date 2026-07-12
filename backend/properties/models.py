import uuid

from django.db import models


class Property(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    landlord = models.ForeignKey(
        "landlords.Landlord", on_delete=models.CASCADE, related_name="properties"
    )
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class UnitStatus(models.TextChoices):
    VACANT = "vacant", "Vacant"
    OCCUPIED = "occupied", "Occupied"
    MAINTENANCE = "maintenance", "Under Maintenance"


class Unit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="units")
    label = models.CharField(max_length=50, help_text="e.g. 'A3', 'House 12'")
    status = models.CharField(max_length=20, choices=UnitStatus.choices, default=UnitStatus.VACANT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("property", "label")

    def __str__(self):
        return f"{self.property.name} — {self.label}"
