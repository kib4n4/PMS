# backend/partners/api_views.py

"""
The partners app's first HTTP surface — previously Celery-task/admin-only
(see billing/tasks.py-adjacent partners/tasks.py). Self-service "my
dashboard" views for Reseller/Investor, plus admin-scoped equivalents so
Dime staff can look up any reseller's/investor's dashboard, not just
their own.
"""

from django.http import Http404
from rest_framework import generics, permissions, viewsets

from accounts.permissions import IsPlatformStaff

from .models import Investor, Reseller
from .serializers import InvestorDashboardSerializer, ResellerDashboardSerializer

_RESELLER_PREFETCH = ("referred_landlords", "commission_rules", "disbursements")
_INVESTOR_PREFETCH = ("agreements", "disbursements")


class ResellerDashboardView(generics.RetrieveAPIView):
    """GET /api/partners/resellers/me/ — the authenticated reseller's own
    referred landlords, commission rules, and disbursement history."""

    serializer_class = ResellerDashboardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        reseller = getattr(self.request.user, "reseller_profile", None)
        if reseller is None:
            raise Http404
        return Reseller.objects.prefetch_related(*_RESELLER_PREFETCH).get(pk=reseller.pk)


class InvestorDashboardView(generics.RetrieveAPIView):
    """GET /api/partners/investors/me/ — the authenticated investor's own
    revenue-share agreements and disbursement history."""

    serializer_class = InvestorDashboardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        investor = getattr(self.request.user, "investor_profile", None)
        if investor is None:
            raise Http404
        return Investor.objects.prefetch_related(*_INVESTOR_PREFETCH).get(pk=investor.pk)


class ResellerAdminViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/partners/resellers/ , /api/partners/resellers/{id}/ —
    Dime-staff-only equivalent of ResellerDashboardView for any reseller."""

    serializer_class = ResellerDashboardSerializer
    permission_classes = [permissions.IsAuthenticated, IsPlatformStaff]
    queryset = Reseller.objects.prefetch_related(*_RESELLER_PREFETCH).order_by("full_name")


class InvestorAdminViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/partners/investors/ , /api/partners/investors/{id}/ —
    Dime-staff-only equivalent of InvestorDashboardView for any investor."""

    serializer_class = InvestorDashboardSerializer
    permission_classes = [permissions.IsAuthenticated, IsPlatformStaff]
    queryset = Investor.objects.prefetch_related(*_INVESTOR_PREFETCH).order_by("full_name")
