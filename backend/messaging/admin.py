from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import EmailMessage, NotificationTemplate, WhatsAppMessage


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(ModelAdmin):
    list_display = ("name", "version", "approval_status", "meta_template_id")
    list_filter = ("approval_status",)


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(ModelAdmin):
    list_display = ("phone_number", "direction", "template_used", "delivery_status", "created_at")
    list_filter = ("direction", "delivery_status")
    search_fields = ("phone_number",)


@admin.register(EmailMessage)
class EmailMessageAdmin(admin.ModelAdmin):
    list_display = ("to_email", "subject", "delivery_status", "created_at")
    list_filter = ("delivery_status",)
    search_fields = ("to_email", "subject")