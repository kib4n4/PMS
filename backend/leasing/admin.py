# backend/leasing/admin.py

from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Lease, Tenant


@admin.register(Tenant)
class TenantAdmin(ModelAdmin):
    list_display = ("full_name", "created_at")
    search_fields = ("full_name", "user__phone_number")


@admin.register(Lease)
class LeaseAdmin(ModelAdmin):
    list_display = ("tenant", "unit", "rent_amount", "status", "start_date")
    list_filter = ("status",)
    autocomplete_fields = ("tenant", "unit")
    search_fields = ("tenant__full_name", "unit__label")