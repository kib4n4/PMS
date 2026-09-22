# backend/credentials/admin_utils.py

"""
Shared Unfold-admin helpers for EncryptedSecretField columns — used by
every app with a model holding one (credentials, landlords, taxes).
"""

from django import forms


def mask_secret(value: str) -> str:
    if not value:
        return "—"
    return f"••••{value[-4:]}" if len(value) > 4 else "••••"


class SecretWidgetMixin:
    """
    Mix into a ModelAdmin (before the ModelAdmin base class) and set
    `secret_fields`: swaps those fields to a password-style widget that
    never pre-fills the decrypted current value, so opening a change form
    can't leak it over someone's shoulder or into a screenshot. These
    fields stay genuinely editable (blank=True) — EncryptedSecretField
    exists specifically so credentials are DB-editable from admin without
    a redeploy — so on the change form a blank submission means "keep the
    current value," not "erase it."
    """

    secret_fields: tuple = ()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        for field_name in self.secret_fields:
            field = form.base_fields.get(field_name)
            if field is None:
                continue
            field.widget = forms.PasswordInput(render_value=False)
            if obj is not None:
                field.required = False
                keep_current = "Leave blank to keep the current value."
                field.help_text = f"{field.help_text} {keep_current}" if field.help_text else keep_current
        return form

    def save_model(self, request, obj, form, change):
        if change:
            existing = self.model.objects.get(pk=obj.pk)
            for field_name in self.secret_fields:
                if field_name in form.cleaned_data and not form.cleaned_data[field_name]:
                    setattr(obj, field_name, getattr(existing, field_name))
        super().save_model(request, obj, form, change)
