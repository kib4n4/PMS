import json

from django import forms
from django.contrib import admin
from django.db import OperationalError
from django.http import HttpResponse
from unfold.admin import ModelAdmin

from .models import AuthType, ProviderCredential


class ProviderCredentialForm(forms.ModelForm):
    credentials_json = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 6}),
        required=False,
        help_text=(
            'Plain JSON, e.g. {"account_sid": "AC...", "auth_token": "...", "whatsapp_number": "+1415..."}. '
            "Encrypted on save — never stored or shown in plaintext."
        ),
    )
    client_id = forms.CharField(
        required=False,
        help_text="OAuth2 client_id / Account SID (Twilio) or Consumer Key (Daraja). Stored encrypted.",
    )
    client_secret = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=True),
        help_text="OAuth2 client_secret / Auth Token (Twilio) or Consumer Secret (Daraja). Stored encrypted.",
    )
    bearer_token = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=True),
        help_text="Bearer token / API key stored encrypted.",
    )
    whatsapp_number = forms.CharField(
        required=False,
        help_text="WhatsApp sender number (e.g. +1415...) — shown for the Twilio provider.",
    )

    class Meta:
        model = ProviderCredential
        fields = [
            "landlord",
            "provider",
            "label",
            "auth_type",
            "client_id",
            "client_secret",
            "bearer_token",
            "credentials_json",
            "whatsapp_number",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get("instance")
        if instance:
            try:
                if instance.auth_type == AuthType.OAUTH2:
                    creds = instance.get_credentials()
                    self.fields["client_id"].initial = creds.get("client_id")
                    self.fields["client_secret"].initial = creds.get("client_secret")
                elif instance.auth_type == AuthType.BEARER:
                    creds = instance.get_credentials()
                    self.fields["bearer_token"].initial = creds.get("token")
                else:
                    self.fields["credentials_json"].initial = json.dumps(instance.get_credentials(), indent=2)

                meta = instance.get_metadata()
                if meta and meta.get("whatsapp_number"):
                    self.fields["whatsapp_number"].initial = meta.get("whatsapp_number")
            except Exception:
                pass

    def clean(self):
        cleaned = super().clean()
        auth_type = cleaned.get("auth_type")
        if auth_type == AuthType.OAUTH2:
            if not (cleaned.get("client_id") and cleaned.get("client_secret")):
                raise forms.ValidationError("OAuth2 requires both client_id and client_secret.")
        if auth_type == AuthType.BEARER:
            if not cleaned.get("bearer_token"):
                raise forms.ValidationError("Bearer auth requires a token.")
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        auth_type = self.cleaned_data.get("auth_type")

        instance.encrypted_client_id = None
        instance.encrypted_client_secret = None
        instance.encrypted_bearer_token = None
        instance.ciphertext = None

        if auth_type == AuthType.JSON:
            raw = self.cleaned_data.get("credentials_json")
            if raw:
                instance.set_credentials(json.loads(raw))
        elif auth_type == AuthType.OAUTH2:
            instance.set_oauth2_credentials(
                self.cleaned_data.get("client_id"),
                self.cleaned_data.get("client_secret"),
            )
        elif auth_type == AuthType.BEARER:
            instance.set_bearer_token(self.cleaned_data.get("bearer_token"))

        provider = self.cleaned_data.get("provider")
        if provider == "twilio":
            whatsapp = self.cleaned_data.get("whatsapp_number")
            if whatsapp:
                instance.set_metadata({"whatsapp_number": whatsapp})
            else:
                instance.encrypted_metadata = None

        if commit:
            instance.save()
        return instance


@admin.register(ProviderCredential)
class ProviderCredentialAdmin(ModelAdmin):
    form = ProviderCredentialForm
    list_display = ("provider", "landlord", "label", "auth_type", "is_active", "updated_at")
    list_filter = ("provider", "auth_type", "is_active")
    search_fields = ("label",)

    class Media:
        css = {"all": ("integrations/provider_credential_admin.css",)}
        js = ("admin/js/jquery.init.js", "integrations/provider_credential_admin.js")

    def changelist_view(self, request, extra_context=None):
        try:
            return super().changelist_view(request, extra_context=extra_context)
        except OperationalError as exc:
            msg = (
                "Database schema for ProviderCredential looks out-of-date: "
                f"{exc}.<br><br>Run <code>python manage.py migrate integrations</code> "
                "in your virtualenv to apply pending migrations, then reload this page."
            )
            return HttpResponse(msg, status=503)