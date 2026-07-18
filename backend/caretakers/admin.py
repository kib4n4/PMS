# backend/caretakers/admin.py

from django.contrib import admin

from .models import Caretaker, CaretakerAssignment


@admin.register(Caretaker)
class CaretakerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "created_at")


@admin.register(CaretakerAssignment)
class CaretakerAssignmentAdmin(admin.ModelAdmin):
    list_display = ("caretaker", "property", "effective_start", "effective_end")
    list_filter = ("property",)