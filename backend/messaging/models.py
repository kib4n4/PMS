# backend/messaging/models.py

import uuid

from django.db import models


class TemplateApprovalStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PENDING_META_APPROVAL = "pending_meta_approval", "Pending Meta Approval"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class NotificationTemplate(models.Model):
    """
    Versioned WhatsApp template registry. Meta requires pre-approved
    templates for any message sent outside a 24-hour customer-initiated
    session window — this is config, never inline strings in code, so a
    template change doesn't require a deploy.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="Internal name, e.g. 'rent_reminder_v2'")
    meta_template_id = models.CharField(max_length=100, blank=True)
    body = models.TextField(help_text="Template body with {{variable}} placeholders")
    variables = models.JSONField(default=list, blank=True)
    approval_status = models.CharField(
        max_length=30, choices=TemplateApprovalStatus.choices, default=TemplateApprovalStatus.DRAFT
    )
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("name", "version")

    def __str__(self):
        return f"{self.name} v{self.version} ({self.approval_status})"


class MessageDirection(models.TextChoices):
    INBOUND = "inbound", "Inbound"
    OUTBOUND = "outbound", "Outbound"


class WhatsAppMessage(models.Model):
    """Inbound/outbound log — the audit + debugging trail for every
    WhatsApp interaction, linked to whichever entity triggered it."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    direction = models.CharField(max_length=10, choices=MessageDirection.choices)
    phone_number = models.CharField(max_length=20)
    template_used = models.ForeignKey(
        NotificationTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name="messages"
    )
    body = models.TextField()
    delivery_status = models.CharField(max_length=30, blank=True)
    related_object_type = models.CharField(
        max_length=100, blank=True, help_text="e.g. 'Invoice', 'MaintenanceTicket'"
    )
    related_object_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["related_object_type", "related_object_id"])]

    def __str__(self):
        return f"{self.direction} — {self.phone_number} — {self.created_at:%Y-%m-%d %H:%M}"


class EmailMessage(models.Model):
    """
    Outbound-only email log (audit + debugging trail), mirroring
    WhatsAppMessage's shape. There's no inbound email channel on this
    platform — email is a delivery channel for OTPs and notifications,
    never a conversation surface.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    to_email = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    delivery_status = models.CharField(max_length=30, blank=True)
    resend_message_id = models.CharField(max_length=100, blank=True)
    related_object_type = models.CharField(
        max_length=100, blank=True, help_text="e.g. 'Payment', 'FeeInvoice', 'OTPRequest'"
    )
    related_object_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["related_object_type", "related_object_id"])]

    def __str__(self):
        return f"{self.to_email} — {self.subject} — {self.created_at:%Y-%m-%d %H:%M}"