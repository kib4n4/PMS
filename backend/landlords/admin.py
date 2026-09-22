from django.contrib import admin
from unfold.admin import ModelAdmin

from credentials.admin_utils import SecretWidgetMixin

from .models import Landlord, LandlordDarajaCredential, LandlordWhatsAppCredential, Organization


@admin.register(Organization)
class OrganizationAdmin(ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)


@admin.register(Landlord)
class LandlordAdmin(ModelAdmin):
    list_display = ("full_name", "organization", "referred_by", "created_at")
    list_filter = ("organization",)
    autocomplete_fields = ("organization", "user", "referred_by")
    search_fields = ("full_name",)


@admin.register(LandlordDarajaCredential)
class LandlordDarajaCredentialAdmin(SecretWidgetMixin, ModelAdmin):
    secret_fields = ("consumer_key", "consumer_secret", "passkey", "initiator_credential", "security_credential")

    list_display = ("landlord", "shortcode", "environment", "status", "c2b_urls_registered")
    list_filter = ("environment", "status", "c2b_urls_registered")
    autocomplete_fields = ("landlord",)
    search_fields = ("shortcode", "landlord__full_name")


@admin.register(LandlordWhatsAppCredential)
class LandlordWhatsAppCredentialAdmin(ModelAdmin):
    list_display = ("landlord", "environment", "status")
    list_filter = ("environment", "status")
    autocomplete_fields = ("landlord",)
