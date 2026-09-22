# backend/taxes/api_views.py

from rest_framework import permissions
from rest_framework.generics import ListAPIView
from rest_framework.serializers import ModelSerializer

from accounts.models import Role

from .models import RentalIncomeReturn


class RentalIncomeReturnSerializer(ModelSerializer):
    class Meta:
        model = RentalIncomeReturn
        fields = [
            "id", "period_start", "period_end", "gross_rental_income",
            "tax_due", "status", "kra_reference", "submitted_at", "created_at",
        ]
        read_only_fields = fields


class RentalIncomeReturnListView(ListAPIView):
    """
    GET /api/taxes/returns/ — a landlord sees only their own MRI returns;
    super admin sees every landlord's. Mirrors the scoping pattern in
    leasing/api_views.py::LandlordTenantViewSet.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = RentalIncomeReturnSerializer

    def get_queryset(self):
        user = self.request.user
        qs = RentalIncomeReturn.objects.select_related("landlord")
        if user.is_superuser:
            return qs
        if user.role == Role.LANDLORD and hasattr(user, "landlord_profile"):
            return qs.filter(landlord=user.landlord_profile)
        return qs.none()
