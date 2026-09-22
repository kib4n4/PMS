from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Property, Unit


class UnitInline(admin.TabularInline):
    model = Unit
    extra = 0


@admin.register(Property)
class PropertyAdmin(ModelAdmin):
    list_display = ("name", "landlord", "created_at")
    list_filter = ("landlord",)
    inlines = [UnitInline]


@admin.register(Unit)
class UnitAdmin(ModelAdmin):
    list_display = ("label", "property", "status")
    list_filter = ("status",)