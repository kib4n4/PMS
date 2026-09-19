# backend/leasing/api_views.py

from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import IsLandlord, HasOAuthScopeOrIsSessionUser

from .models import Lease, LeaseStatus
from .serializers import LeaseOffboardSerializer, LeaseSerializer, TenantOnboardSerializer


class LandlordTenantViewSet(viewsets.GenericViewSet):
    """
    Landlord-facing tenant onboarding/offboarding. A landlord can only
    see and manage leases on units within their own properties — scoping
    is enforced in get_queryset, not just at the permission-class level.
    """

    permission_classes = [HasOAuthScopeOrIsSessionUser, IsLandlord]
    serializer_class = LeaseSerializer

    def get_queryset(self):
        landlord = self.request.user.landlord_profile
        return Lease.objects.filter(unit__property__landlord=landlord).select_related(
            "unit", "unit__property", "tenant", "tenant__user"
        )

    def list(self, request):
        """GET /api/landlord/tenants/?active=true (default) — current
        tenants. Pass ?active=false to include past/terminated leases."""
        active_only = request.query_params.get("active", "true").lower() != "false"
        qs = self.get_queryset()
        if active_only:
            qs = qs.filter(status=LeaseStatus.ACTIVE)
        return Response(LeaseSerializer(qs, many=True).data)

    def create(self, request):
        """POST /api/landlord/tenants/ — onboard a new tenant onto one of
        the landlord's units. Reuses an existing User/Tenant record if
        the phone number is already known to the platform."""
        serializer = TenantOnboardSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        lease = serializer.save()
        return Response(LeaseSerializer(lease).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def offboard(self, request, pk=None):
        """POST /api/landlord/tenants/{lease_id}/offboard/ — tenant has
        vacated. Terminates the Lease and frees the Unit. The Tenant and
        underlying User record are kept intact as platform history."""
        lease = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = LeaseOffboardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lease = serializer.save(lease=lease)
        return Response(LeaseSerializer(lease).data)