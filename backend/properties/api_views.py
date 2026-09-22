# backend/properties/api_views.py

from rest_framework import permissions, viewsets

from accounts.rbac import resolve_actor_scope

from .models import Property
from .serializers import PropertySerializer


class PropertyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/properties/ , /api/properties/{id}/ — a landlord's own
    properties with their units nested (status: vacant/occupied/
    maintenance). Feeds the landlord dashboard's property count and
    occupancy figures. Admin/superuser sees every property.
    """

    serializer_class = PropertySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        scope = resolve_actor_scope(self.request.user)
        qs = Property.objects.prefetch_related("units").order_by("-created_at")
        if scope.is_admin:
            return qs
        if scope.landlord_id:
            return qs.filter(landlord_id=scope.landlord_id)
        return qs.none()
