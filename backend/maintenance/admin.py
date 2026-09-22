# backend/maintenance/admin.py

from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import MaintenanceTicket


@admin.register(MaintenanceTicket)
class MaintenanceTicketAdmin(ModelAdmin):
    list_display = ("id", "unit", "tenant", "assigned_caretaker", "status", "created_at", "resolved_at")
    list_filter = ("status",)
    autocomplete_fields = ("unit", "tenant", "assigned_caretaker")
    readonly_fields = ("resolved_at",)