# backend/taxes/admin.py

from django.contrib import admin
from unfold.admin import ModelAdmin

from credentials.admin_utils import SecretWidgetMixin

from .models import LandlordKRACredential, RentalIncomeReturn


@admin.register(LandlordKRACredential)
class LandlordKRACredentialAdmin(SecretWidgetMixin, ModelAdmin):
    secret_fields = ("client_id", "client_secret")

    list_display = ("landlord", "kra_pin", "environment", "status")
    list_filter = ("environment", "status")
    search_fields = ("kra_pin", "landlord__full_name")
    autocomplete_fields = ("landlord",)


@admin.register(RentalIncomeReturn)
class RentalIncomeReturnAdmin(ModelAdmin):
    list_display = ("landlord", "period_start", "period_end", "gross_rental_income", "tax_due", "status", "kra_reference")
    list_filter = ("status",)
    autocomplete_fields = ("landlord",)
    search_fields = ("kra_reference", "landlord__full_name")
