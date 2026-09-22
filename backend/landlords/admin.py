from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Landlord, LandlordDarajaCredential, LandlordWhatsAppCredential, Organization


@admin.register(Organization)
class OrganizationAdmin(ModelAdmin):
    list_display = ("name", "created_at")


@admin.register(Landlord)
class LandlordAdmin(ModelAdmin):
    list_display = ("full_name", "organization", "referred_by", "created_at")
    list_filter = ("organization",)


@admin.register(LandlordDarajaCredential)
class LandlordDarajaCredentialAdmin(ModelAdmin):
    list_display = ("landlord", "shortcode", "environment", "status", "c2b_urls_registered")
    list_filter = ("environment", "status", "c2b_urls_registered")


@admin.register(LandlordWhatsAppCredential)
class LandlordWhatsAppCredentialAdmin(ModelAdmin):
    list_display = ("landlord", "environment", "status")
    list_filter = ("environment", "status")