# backend/api_auth/external_views.py

"""
Read-only endpoints external integrators reach via the client-credentials
token from POST /api/oauth/token/. Each one is scoped to the calling
client's landlord (client.landlord) — a platform-wide client
(landlord=None) gets an empty result set here rather than everyone's
data; broader platform-wide external endpoints are a deliberate later
addition, not an oversight.
"""

from rest_framework.generics import ListAPIView
from rest_framework.serializers import ModelSerializer

from billing.models import Invoice

from .authentication import ClientCredentialsAuthentication
from .permissions import require_scope


class ExternalInvoiceSerializer(ModelSerializer):
    class Meta:
        model = Invoice
        fields = ["id", "reference", "period_start", "period_end", "amount_due", "status", "due_date"]
        read_only_fields = fields


class ExternalInvoiceListView(ListAPIView):
    """GET /api/external/invoices/ — requires the 'invoices:read' scope."""

    authentication_classes = [ClientCredentialsAuthentication]
    permission_classes = [require_scope("invoices:read")]
    serializer_class = ExternalInvoiceSerializer

    def get_queryset(self):
        client = self.request.user.client
        if client.landlord_id is None:
            return Invoice.objects.none()
        return Invoice.objects.filter(lease__unit__property__landlord=client.landlord).select_related(
            "lease__unit__property", "lease__tenant"
        )
