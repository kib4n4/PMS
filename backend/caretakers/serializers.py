# backend/caretakers/serializers.py

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from properties.serializers import PropertySerializer

from .models import Caretaker, CaretakerAssignment


class CaretakerAssignmentSerializer(serializers.ModelSerializer):
    property = PropertySerializer(read_only=True)

    class Meta:
        model = CaretakerAssignment
        fields = ["id", "property", "effective_start", "effective_end"]
        read_only_fields = fields


class CaretakerMeSerializer(serializers.ModelSerializer):
    assignments = serializers.SerializerMethodField()

    class Meta:
        model = Caretaker
        fields = ["id", "full_name", "assignments"]
        read_only_fields = fields

    @extend_schema_field(CaretakerAssignmentSerializer(many=True))
    def get_assignments(self, caretaker):
        active = caretaker.assignments.filter(effective_end__isnull=True).select_related("property")
        return CaretakerAssignmentSerializer(active, many=True).data
