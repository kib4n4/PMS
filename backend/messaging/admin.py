from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import EmailMessage, NotificationTemplate, TemplateApprovalStatus, WhatsAppMessage


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(ModelAdmin):
    list_display = ("name", "version", "approval_status", "meta_template_id")
    list_filter = ("approval_status",)
    search_fields = ("name", "meta_template_id")
    actions = ["approve_template", "reject_template"]

    @admin.action(description="Approve selected templates")
    def approve_template(self, request, queryset):
        updated = queryset.update(approval_status=TemplateApprovalStatus.APPROVED)
        self.message_user(request, f"Approved {updated} template(s).")

    @admin.action(description="Reject selected templates")
    def reject_template(self, request, queryset):
        updated = queryset.update(approval_status=TemplateApprovalStatus.REJECTED)
        self.message_user(request, f"Rejected {updated} template(s).")


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(ModelAdmin):
    list_display = ("phone_number", "direction", "template_used", "delivery_status", "created_at")
    list_filter = ("direction", "delivery_status")
    search_fields = ("phone_number",)
    autocomplete_fields = ("template_used",)


@admin.register(EmailMessage)
class EmailMessageAdmin(ModelAdmin):
    list_display = ("to_email", "subject", "delivery_status", "created_at")
    list_filter = ("delivery_status",)
    search_fields = ("to_email", "subject")