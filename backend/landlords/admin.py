# backend/landlords/admin.py

from django.contrib import admin

from .models import Landlord, LandlordDarajaCredential, Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")


@admin.register(Landlord)
class LandlordAdmin(admin.ModelAdmin):
    list_display = ("full_name", "organization", "referred_by", "created_at")
    list_filter = ("organization",)


@admin.register(LandlordDarajaCredential)
class LandlordDarajaCredentialAdmin(admin.ModelAdmin):
    list_display = ("landlord", "shortcode", "environment", "status", "c2b_urls_registered")
    list_filter = ("environment", "status", "c2b_urls_registered")