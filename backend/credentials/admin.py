# backend/credentials/admin.py

from django.contrib import admin
from unfold.admin import ModelAdmin

from .admin_utils import SecretWidgetMixin, mask_secret
from .models import PlatformCredential


@admin.register(PlatformCredential)
class PlatformCredentialAdmin(SecretWidgetMixin, ModelAdmin):
    secret_fields = ("value",)

    list_display = ("key", "environment", "masked_value", "updated_at", "updated_by")
    list_filter = ("environment",)
    readonly_fields = ("updated_at", "updated_by")
    search_fields = ("key",)

    def masked_value(self, obj):
        return mask_secret(obj.value)
    masked_value.short_description = "Value"

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
