# backend/api_auth/external_views.py

"""
Read-only endpoints external integrators reach via the client-credentials
token from POST /api/oauth/token/. Each one is scoped to the calling
client's landlord (client.landlord) — a platform-wide client
(landlord=None) gets an empty result set here rather than everyone's
data; broader platform-wide external endpoints are a deliberate later
addition, not an oversight.

The one exception is /external/disbursements/: payouts are funded from the
platform's own fee revenue and never target a landlord, so it inverts the
rule — platform-wide clients see them, landlord-bound clients get nothing
(a landlord must not read a reseller's commission).

None of these serializers expose a phone number or email: an integrator that
needs to reach a tenant goes through PMS's own messaging, so a leaked API
client cannot become a contact-details dump.
"""

from datetime import timedelta

from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.serializers import ModelSerializer, SerializerMethodField

from billing.models import Invoice, InvoiceStatus
from leasing.models import Lease, LeaseStatus
from maintenance.models import MaintenanceTicket
from partners.models import Disbursement

from .authentication import ClientCredentialsAuthentication
from .permissions import require_scope


class ExternalInvoiceSerializer(ModelSerializer):
    unit_label = SerializerMethodField()
    property_name = SerializerMethodField()
    tenant_name = SerializerMethodField()
    days_overdue = SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "id", "reference", "period_start", "period_end", "amount_due", "status", "due_date",
            "unit_label", "property_name", "tenant_name", "days_overdue",
        ]
        read_only_fields = fields

    def get_unit_label(self, obj):
        return obj.lease.unit.label

    def get_property_name(self, obj):
        return obj.lease.unit.property.name

    def get_tenant_name(self, obj):
        return obj.lease.tenant.full_name

    def get_days_overdue(self, obj):
        if obj.status == InvoiceStatus.PAID:
            return 0
        return max(0, (timezone.localdate() - obj.due_date).days)


class _LandlordScopedListView(ListAPIView):
    authentication_classes = [ClientCredentialsAuthentication]

    def get_client_landlord_id(self):
        return self.request.user.client.landlord_id


class ExternalInvoiceListView(_LandlordScopedListView):
    """GET /api/external/invoices/ — requires the 'invoices:read' scope."""

    permission_classes = [require_scope("invoices:read")]
    serializer_class = ExternalInvoiceSerializer

    def get_queryset(self):
        client = self.request.user.client
        if client.landlord_id is None:
            return Invoice.objects.none()
        return Invoice.objects.filter(lease__unit__property__landlord=client.landlord).select_related(
            "lease__unit__property", "lease__tenant"
        )


class ExternalTicketSerializer(ModelSerializer):
    unit_label = SerializerMethodField()
    assigned_caretaker = SerializerMethodField()
    age_hours = SerializerMethodField()

    class Meta:
        model = MaintenanceTicket
        fields = [
            "id", "unit_label", "category", "description", "status",
            "assigned_caretaker", "created_at", "resolved_at", "age_hours",
        ]
        read_only_fields = fields

    def get_unit_label(self, obj):
        return obj.unit.label

    def get_assigned_caretaker(self, obj):
        return obj.assigned_caretaker.full_name if obj.assigned_caretaker_id else None

    def get_age_hours(self, obj):
        end = obj.resolved_at or timezone.now()
        return round((end - obj.created_at).total_seconds() / 3600, 1)


class ExternalTicketListView(_LandlordScopedListView):
    """GET /api/external/tickets/[?status=open] — 'tickets:read'. Oldest first."""

    permission_classes = [require_scope("tickets:read")]
    serializer_class = ExternalTicketSerializer

    def get_queryset(self):
        landlord_id = self.get_client_landlord_id()
        if landlord_id is None:
            return MaintenanceTicket.objects.none()
        qs = MaintenanceTicket.objects.filter(unit__property__landlord_id=landlord_id).select_related(
            "unit", "assigned_caretaker"
        )
        status = self.request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs.order_by("created_at")


class ExternalDisbursementSerializer(ModelSerializer):
    recipient_name = SerializerMethodField()

    class Meta:
        model = Disbursement
        fields = ["id", "recipient_type", "recipient_name", "amount", "status", "created_at"]
        read_only_fields = fields

    def get_recipient_name(self, obj):
        recipient = obj.reseller or obj.investor
        return recipient.full_name if recipient else None


class ExternalDisbursementListView(ListAPIView):
    """GET /api/external/disbursements/[?status=failed] — 'disbursements:read',
    platform-wide clients only (see module docstring)."""

    authentication_classes = [ClientCredentialsAuthentication]
    permission_classes = [require_scope("disbursements:read")]
    serializer_class = ExternalDisbursementSerializer

    def get_queryset(self):
        if self.request.user.client.landlord_id is not None:
            return Disbursement.objects.none()
        qs = Disbursement.objects.select_related("reseller", "investor")
        status = self.request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs.order_by("-created_at")


class ExternalLeaseSerializer(ModelSerializer):
    unit_label = SerializerMethodField()
    tenant_name = SerializerMethodField()
    days_to_end = SerializerMethodField()

    class Meta:
        model = Lease
        fields = ["id", "unit_label", "tenant_name", "status", "rent_amount", "end_date", "days_to_end"]
        read_only_fields = fields

    def get_unit_label(self, obj):
        return obj.unit.label

    def get_tenant_name(self, obj):
        return obj.tenant.full_name

    def get_days_to_end(self, obj):
        if obj.end_date is None:
            return None
        return (obj.end_date - timezone.localdate()).days


class ExternalLeaseListView(_LandlordScopedListView):
    """GET /api/external/leases/[?ending_within=60] — 'leases:read'.

    ``ending_within=N`` keeps live leases whose end_date falls between today
    and N days out, so open-ended, already-ended and terminated leases drop out.
    """

    permission_classes = [require_scope("leases:read")]
    serializer_class = ExternalLeaseSerializer

    def get_queryset(self):
        landlord_id = self.get_client_landlord_id()
        if landlord_id is None:
            return Lease.objects.none()
        qs = Lease.objects.filter(unit__property__landlord_id=landlord_id).select_related("unit", "tenant")
        window = self.request.query_params.get("ending_within")
        if window:
            try:
                days = int(window)
            except ValueError:
                raise ValidationError({"ending_within": "Must be a whole number of days."})
            today = timezone.localdate()
            qs = qs.filter(
                end_date__gte=today, end_date__lte=today + timedelta(days=days)
            ).exclude(status=LeaseStatus.TERMINATED)
        return qs.order_by(F("end_date").asc(nulls_last=True))
