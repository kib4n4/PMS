# backend/accounts/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from .models import OTPRequest, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin, ModelAdmin):
    # Unfold's form classes give the add/change/password-change pages its
    # styled widgets — DjangoUserAdmin's own forms render as plain
    # unstyled inputs under the Unfold theme otherwise.
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm

    list_display = ("username", "phone_number", "role", "is_phone_verified", "is_staff")
    list_filter = DjangoUserAdmin.list_filter + ("role",)
    search_fields = ("username", "phone_number", "email", "first_name", "last_name")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("PMS role", {"fields": ("phone_number", "role", "is_phone_verified")}),
    )


@admin.register(OTPRequest)
class OTPRequestAdmin(ModelAdmin):
    list_display = ("phone_number", "channel", "expires_at", "consumed_at", "attempt_count")
    list_filter = ("channel",)
    search_fields = ("phone_number",)
    readonly_fields = ("code_hash", "created_at")