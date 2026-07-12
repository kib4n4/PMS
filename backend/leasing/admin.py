from django.contrib import admin

from .models import Lease, Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("full_name", "created_at")


@admin.register(Lease)
class LeaseAdmin(admin.ModelAdmin):
    list_display = ("tenant", "unit", "rent_amount", "status", "start_date")
    list_filter = ("status",)
