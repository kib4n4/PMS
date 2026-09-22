# backend/maintenance/serializers.py

from rest_framework import serializers

from .models import MaintenanceTicket


class MaintenanceTicketSerializer(serializers.ModelSerializer):
    unit_label = serializers.CharField(source="unit.label", read_only=True)
    property_name = serializers.CharField(source="unit.property.name", read_only=True)
    tenant_name = serializers.CharField(source="tenant.full_name", read_only=True)
    caretaker_name = serializers.CharField(source="assigned_caretaker.full_name", read_only=True, default=None)

    class Meta:
        model = MaintenanceTicket
        fields = [
            "id", "unit", "unit_label", "property_name", "tenant", "tenant_name",
            "assigned_caretaker", "caretaker_name", "category", "description",
            "status", "created_at", "resolved_at",
        ]
        read_only_fields = fields
