# backend/caretakers/admin.py

from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Caretaker, CaretakerAssignment


@admin.register(Caretaker)
class CaretakerAdmin(ModelAdmin):
    list_display = ("full_name", "created_at")
    search_fields = ("full_name",)


@admin.register(CaretakerAssignment)
class CaretakerAssignmentAdmin(ModelAdmin):
    list_display = ("caretaker", "property", "effective_start", "effective_end")
    list_filter = ("property",)
    autocomplete_fields = ("caretaker", "property")