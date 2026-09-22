# backend/maintenance/urls.py

from rest_framework.routers import DefaultRouter

from .api_views import MaintenanceTicketViewSet

router = DefaultRouter()
router.register("maintenance/tickets", MaintenanceTicketViewSet, basename="maintenance-ticket")

urlpatterns = router.urls
