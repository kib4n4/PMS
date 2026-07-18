# backend/properties/admin.py

from django.contrib import admin

from .models import Property, Unit


class UnitInline(admin.TabularInline):
    model = Unit
    extra = 0


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("name", "landlord", "created_at")
    list_filter = ("landlord",)
    inlines = [UnitInline]


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("label", "property", "status")
    list_filter = ("status",)