# backend/api_auth/admin.py

from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import PlatformApiClient


@admin.register(PlatformApiClient)
class PlatformApiClientAdmin(ModelAdmin):
    """
    Secrets are never entered or shown here — use
    `python manage.py create_api_client` / `rotate_api_client_secret` to
    issue or rotate a client_id/secret pair (the plaintext secret is only
    ever shown once, at creation/rotation). This admin page is for
    viewing/managing existing clients: scope, landlord, active status.
    Superuser-only — see accounts.management.commands.sync_role_permissions
    (secret-bearing models grant zero permissions to role=admin staff).
    """

    list_display = ("name", "client_id", "landlord", "scopes", "is_active", "last_used_at")
    list_filter = ("is_active",)
    readonly_fields = ("client_id", "client_secret_hash", "last_used_at", "created_at")
    search_fields = ("name", "client_id")
    autocomplete_fields = ("landlord",)
