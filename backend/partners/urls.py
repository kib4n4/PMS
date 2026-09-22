# backend/partners/urls.py

from django.urls import path
from rest_framework.routers import DefaultRouter

from .api_views import (
    InvestorAdminViewSet,
    InvestorDashboardView,
    ResellerAdminViewSet,
    ResellerDashboardView,
)

router = DefaultRouter()
router.register("partners/resellers", ResellerAdminViewSet, basename="partners-reseller")
router.register("partners/investors", InvestorAdminViewSet, basename="partners-investor")

urlpatterns = [
    # Explicit "me" routes must precede the router's <pk> routes below —
    # both are shaped like partners/resellers/<value>/, and Django resolves
    # urlpatterns in list order, so "me" would otherwise risk being parsed
    # as a pk by the router's detail route.
    path("partners/resellers/me/", ResellerDashboardView.as_view(), name="reseller-dashboard"),
    path("partners/investors/me/", InvestorDashboardView.as_view(), name="investor-dashboard"),
] + router.urls
