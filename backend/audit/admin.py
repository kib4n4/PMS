# backend/audit/admin.py

from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "target_object_type", "target_object_id", "created_at")
    list_filter = ("action",)
    search_fields = ("target_object_id",)