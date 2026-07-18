# backend/leasing/urls.py

from rest_framework.routers import DefaultRouter

from .api_views import LandlordTenantViewSet

router = DefaultRouter()
router.register("landlord/tenants", LandlordTenantViewSet, basename="landlord-tenant")

urlpatterns = router.urls