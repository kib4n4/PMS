# backend/landlords/api_views.py

from django.contrib.auth import get_user_model
from django.db.models import Count
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsPlatformStaff
from audit.models import AuditLog
from maintenance.models import MaintenanceTicket, TicketStatus

from .models import LandlordDarajaCredential, OnboardingStatus

User = get_user_model()


class _OnboardingQueueItemSerializer(serializers.Serializer):
    landlord_id = serializers.UUIDField()
    landlord_name = serializers.CharField()
    shortcode = serializers.CharField()
    status = serializers.CharField()
    updated_at = serializers.DateTimeField()


class _AuditLogEntrySerializer(serializers.Serializer):
    action = serializers.CharField()
    actor = serializers.CharField(allow_null=True)
    target_object_type = serializers.CharField()
    target_object_id = serializers.CharField()
    reason = serializers.CharField()
    created_at = serializers.DateTimeField()


_AdminOverviewResponseSerializer = inline_serializer(
    "AdminOverviewResponse",
    {
        "total_users": serializers.IntegerField(),
        "active_landlords": serializers.IntegerField(),
        "pending_onboarding": serializers.IntegerField(),
        "open_maintenance_tickets": serializers.IntegerField(),
        "users_by_role": serializers.DictField(child=serializers.IntegerField()),
        "landlords_by_onboarding_status": serializers.DictField(child=serializers.IntegerField()),
        "onboarding_queue": _OnboardingQueueItemSerializer(many=True),
        "recent_audit_log": _AuditLogEntrySerializer(many=True),
    },
)


def _group_counts(queryset, field: str) -> dict:
    rows = queryset.exclude(**{field: ""}).values(field).annotate(count=Count("id")).order_by()
    return {row[field]: row["count"] for row in rows}


class AdminOverviewView(APIView):
    """
    GET /api/admin/overview/ — real platform-wide figures for the admin
    dashboard: every field here maps directly to a queryset, nothing is a
    placeholder/synthetic metric. Dime-staff-only.
    """

    permission_classes = [IsAuthenticated, IsPlatformStaff]

    @extend_schema(summary="Admin platform overview", responses={200: _AdminOverviewResponseSerializer})
    def get(self, request):
        onboarding_queue = (
            LandlordDarajaCredential.objects.exclude(status=OnboardingStatus.LIVE)
            .select_related("landlord")
            .order_by("-updated_at")[:20]
        )
        recent_audit_log = AuditLog.objects.select_related("actor").order_by("-created_at")[:10]

        return Response(
            {
                "total_users": User.objects.count(),
                "active_landlords": LandlordDarajaCredential.objects.filter(
                    status=OnboardingStatus.LIVE
                ).count(),
                "pending_onboarding": LandlordDarajaCredential.objects.exclude(
                    status=OnboardingStatus.LIVE
                ).count(),
                "open_maintenance_tickets": MaintenanceTicket.objects.exclude(
                    status=TicketStatus.RESOLVED
                ).count(),
                "users_by_role": _group_counts(User.objects.all(), "role"),
                "landlords_by_onboarding_status": _group_counts(
                    LandlordDarajaCredential.objects.all(), "status"
                ),
                "onboarding_queue": [
                    {
                        "landlord_id": c.landlord_id,
                        "landlord_name": c.landlord.full_name,
                        "shortcode": c.shortcode,
                        "status": c.status,
                        "updated_at": c.updated_at,
                    }
                    for c in onboarding_queue
                ],
                "recent_audit_log": [
                    {
                        "action": a.action,
                        "actor": str(a.actor) if a.actor else None,
                        "target_object_type": a.target_object_type,
                        "target_object_id": a.target_object_id,
                        "reason": a.reason,
                        "created_at": a.created_at,
                    }
                    for a in recent_audit_log
                ],
            }
        )
