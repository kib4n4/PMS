# backend/credentials/admin.py

from django.contrib import admin

from .models import PlatformCredential


@admin.register(PlatformCredential)
class PlatformCredentialAdmin(admin.ModelAdmin):
    list_display = ("key", "environment", "updated_at", "updated_by")
    list_filter = ("environment",)
    readonly_fields = ("updated_at", "updated_by")

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
