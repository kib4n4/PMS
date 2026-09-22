# backend/taxes/admin.py

from django.contrib import admin

from .models import LandlordKRACredential, RentalIncomeReturn


@admin.register(LandlordKRACredential)
class LandlordKRACredentialAdmin(admin.ModelAdmin):
    list_display = ("landlord", "kra_pin", "environment", "status")
    list_filter = ("environment", "status")
    search_fields = ("kra_pin",)


@admin.register(RentalIncomeReturn)
class RentalIncomeReturnAdmin(admin.ModelAdmin):
    list_display = ("landlord", "period_start", "period_end", "gross_rental_income", "tax_due", "status", "kra_reference")
    list_filter = ("status",)
