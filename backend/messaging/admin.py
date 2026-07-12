from django.contrib import admin

from .models import NotificationTemplate, WhatsAppMessage


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "approval_status", "meta_template_id")
    list_filter = ("approval_status",)


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = ("phone_number", "direction", "template_used", "delivery_status", "created_at")
    list_filter = ("direction", "delivery_status")
    search_fields = ("phone_number",)
