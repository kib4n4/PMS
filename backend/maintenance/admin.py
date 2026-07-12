from django.contrib import admin

from .models import MaintenanceTicket


@admin.register(MaintenanceTicket)
class MaintenanceTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "unit", "tenant", "assigned_caretaker", "status", "created_at")
    list_filter = ("status",)
