# backend/properties/admin.py

from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import Property, Unit


class UnitInline(TabularInline):
    model = Unit
    extra = 0


@admin.register(Property)
class PropertyAdmin(ModelAdmin):
    list_display = ("name", "landlord", "created_at")
    list_filter = ("landlord",)
    inlines = [UnitInline]
    autocomplete_fields = ("landlord",)
    search_fields = ("name",)


@admin.register(Unit)
class UnitAdmin(ModelAdmin):
    list_display = ("label", "property", "status")
    list_filter = ("status",)
    autocomplete_fields = ("property",)
    search_fields = ("label", "property__name")