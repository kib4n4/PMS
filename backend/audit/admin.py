# backend/audit/admin.py

from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(ModelAdmin):
    list_display = ("action", "actor", "target_object_type", "target_object_id", "created_at")
    list_filter = ("action",)
    search_fields = ("target_object_id", "action")
    readonly_fields = ("actor", "action", "target_object_type", "target_object_id", "reason", "metadata", "created_at")

    def has_add_permission(self, request):
        # Every row here is written by application code (webhook handlers,
        # reconciliation tasks) — there is no legitimate "manually create
        # an audit entry" workflow, and allowing it would undermine the
        # log's value as a record of what the system actually did.
        return False

    def has_change_permission(self, request, obj=None):
        return False