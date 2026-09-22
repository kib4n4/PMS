# backend/maintenance/api_views.py

from rest_framework import permissions, viewsets

from accounts.rbac import resolve_actor_scope

from .models import MaintenanceTicket
from .serializers import MaintenanceTicketSerializer


class MaintenanceTicketViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/maintenance/tickets/ , /api/maintenance/tickets/{id}/ —
    scoped three ways: a landlord sees tickets on their own properties, a
    caretaker sees tickets assigned to them, admin/superuser sees all.
    Feeds the landlord/caretaker dashboards' ticket queues.
    """

    serializer_class = MaintenanceTicketSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        scope = resolve_actor_scope(self.request.user)
        qs = MaintenanceTicket.objects.select_related(
            "unit", "unit__property", "tenant", "assigned_caretaker"
        ).order_by("-created_at")
        if scope.is_admin:
            return qs
        if scope.landlord_id:
            return qs.filter(unit__property__landlord_id=scope.landlord_id)
        if scope.caretaker_id:
            return qs.filter(assigned_caretaker_id=scope.caretaker_id)
        return qs.none()
