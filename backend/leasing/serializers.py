# backend/leasing/serializers.py

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from accounts.models import Role
from properties.models import Unit, UnitStatus

from .models import Lease, LeaseStatus, Tenant

User = get_user_model()


class LeaseSerializer(serializers.ModelSerializer):
    tenant_full_name = serializers.CharField(source="tenant.full_name", read_only=True)
    tenant_phone_number = serializers.CharField(source="tenant.user.phone_number", read_only=True)
    unit_label = serializers.CharField(source="unit.label", read_only=True)
    property_name = serializers.CharField(source="unit.property.name", read_only=True)

    class Meta:
        model = Lease
        fields = [
            "id", "unit", "unit_label", "property_name", "tenant",
            "tenant_full_name", "tenant_phone_number", "rent_amount",
            "billing_day", "deposit_amount", "status", "start_date",
            "end_date", "created_at",
        ]
        read_only_fields = ["id", "tenant", "status", "created_at"]


class TenantOnboardSerializer(serializers.Serializer):
    """
    Landlord-facing onboarding input: creates (or reuses) the tenant's
    User account and Tenant profile, then opens a new Lease on the given
    Unit. Only units belonging to the requesting landlord are accepted.
    """

    phone_number = serializers.CharField(max_length=20)
    full_name = serializers.CharField(max_length=255)
    unit = serializers.PrimaryKeyRelatedField(queryset=Unit.objects.all())
    rent_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    billing_day = serializers.IntegerField(min_value=1, max_value=28)
    deposit_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=0
    )
    start_date = serializers.DateField(required=False, default=timezone.localdate)

    def validate_unit(self, unit):
        landlord = self.context["request"].user.landlord_profile
        if unit.property.landlord_id != landlord.id:
            raise serializers.ValidationError("This unit does not belong to one of your properties.")
        if Lease.objects.filter(unit=unit, status=LeaseStatus.ACTIVE).exists():
            raise serializers.ValidationError("This unit already has an active lease.")
        return unit

    def create(self, validated_data):
        phone_number = validated_data["phone_number"]
        full_name = validated_data["full_name"]

        # Reuse the User if this phone number is already known to the
        # platform (e.g. a returning tenant) — never create a duplicate
        # identity for the same phone number.
        user, created_user = User.objects.get_or_create(
            phone_number=phone_number,
            defaults={"username": phone_number, "role": Role.TENANT},
        )
        if not created_user and user.role != Role.TENANT:
            raise serializers.ValidationError(
                {"phone_number": "This phone number is already registered under a different role."}
            )

        tenant, _ = Tenant.objects.get_or_create(user=user, defaults={"full_name": full_name})

        unit = validated_data["unit"]
        lease = Lease.objects.create(
            unit=unit,
            tenant=tenant,
            rent_amount=validated_data["rent_amount"],
            billing_day=validated_data["billing_day"],
            deposit_amount=validated_data.get("deposit_amount", 0),
            start_date=validated_data.get("start_date"),
            status=LeaseStatus.ACTIVE,
        )
        unit.status = UnitStatus.OCCUPIED
        unit.save(update_fields=["status"])
        return lease


class LeaseOffboardSerializer(serializers.Serializer):
    """
    Ends a Lease when a tenant vacates. Deliberately does NOT touch the
    Tenant or User rows — those persist as the historical record of who
    lived there. Only the Lease is terminated and the Unit freed up.
    """

    end_date = serializers.DateField(required=False, default=timezone.localdate)

    def save(self, lease):
        lease.status = LeaseStatus.TERMINATED
        lease.end_date = self.validated_data.get("end_date")
        lease.save(update_fields=["status", "end_date"])
        lease.unit.status = UnitStatus.VACANT
        lease.unit.save(update_fields=["status"])
        return lease