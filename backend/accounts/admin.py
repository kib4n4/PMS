from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from unfold.admin import ModelAdmin

from .models import OTPRequest, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin, ModelAdmin):
    list_display = ("username", "phone_number", "role", "is_phone_verified", "is_staff")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("PMS role", {"fields": ("phone_number", "role", "is_phone_verified")}),
    )


@admin.register(OTPRequest)
class OTPRequestAdmin(ModelAdmin):
    list_display = ("phone_number", "channel", "expires_at", "consumed_at", "attempt_count")
    list_filter = ("channel",)