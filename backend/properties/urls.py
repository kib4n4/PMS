# backend/properties/urls.py

from rest_framework.routers import DefaultRouter

from .api_views import PropertyViewSet

router = DefaultRouter()
router.register("properties", PropertyViewSet, basename="property")

urlpatterns = router.urls
