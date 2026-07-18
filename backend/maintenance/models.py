# backend/maintenance/models.py

import uuid

from django.db import models


class TicketStatus(models.TextChoices):
    OPEN = "open", "Open"
    ASSIGNED = "assigned", "Assigned"
    IN_PROGRESS = "in_progress", "In Progress"
    RESOLVED = "resolved", "Resolved"
    REOPENED = "reopened", "Reopened"


class MaintenanceTicket(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit = models.ForeignKey("properties.Unit", on_delete=models.CASCADE, related_name="tickets")
    tenant = models.ForeignKey("leasing.Tenant", on_delete=models.PROTECT, related_name="tickets")
    assigned_caretaker = models.ForeignKey(
        "caretakers.Caretaker", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="tickets",
    )
    category = models.CharField(max_length=100, blank=True)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=TicketStatus.choices, default=TicketStatus.OPEN)
    whatsapp_thread_ref = models.CharField(
        max_length=255, blank=True, help_text="Reference to the originating WhatsApp thread"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Ticket {self.id} — {self.unit} — {self.status}"