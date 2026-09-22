# backend/properties/serializers.py

from rest_framework import serializers

from .models import Property, Unit


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ["id", "label", "status"]
        read_only_fields = fields


class PropertySerializer(serializers.ModelSerializer):
    units = UnitSerializer(many=True, read_only=True)

    class Meta:
        model = Property
        fields = ["id", "name", "address", "landlord", "units", "created_at"]
        read_only_fields = fields
