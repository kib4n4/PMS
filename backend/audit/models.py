import uuid

from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Every manual admin override (adjusting a fee ledger entry, forcing
    a payout, marking a payment resolved manually) writes here — who,
    when, why, and what changed."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="audit_entries"
    )
    action = models.CharField(max_length=255, help_text="e.g. 'force_disbursement', 'adjust_fee_ledger_entry'")
    target_object_type = models.CharField(max_length=100)
    target_object_id = models.CharField(max_length=100)
    reason = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["target_object_type", "target_object_id"])]

    def __str__(self):
        return f"{self.action} by {self.actor} on {self.target_object_type}:{self.target_object_id}"
