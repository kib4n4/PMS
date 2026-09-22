# backend/api_auth/admin.py

from django.contrib import admin

from .models import PlatformApiClient


@admin.register(PlatformApiClient)
class PlatformApiClientAdmin(admin.ModelAdmin):
    """
    Secrets are never entered or shown here — use
    `python manage.py create_api_client` to issue a new client_id/secret
    pair (the plaintext secret is only ever shown once, at creation).
    This admin page is for viewing/managing existing clients: scope,
    landlord, active status.
    """

    list_display = ("name", "client_id", "landlord", "scopes", "is_active", "last_used_at")
    list_filter = ("is_active",)
    readonly_fields = ("client_id", "client_secret_hash", "last_used_at", "created_at")
    search_fields = ("name", "client_id")
