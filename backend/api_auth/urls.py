# backend/api_auth/urls.py

from django.urls import path

from .api_views import TokenView
from .external_views import (
    ExternalDisbursementListView,
    ExternalInvoiceListView,
    ExternalLeaseListView,
    ExternalTicketListView,
)

urlpatterns = [
    path("oauth/token/", TokenView.as_view(), name="oauth-token"),
    path("external/invoices/", ExternalInvoiceListView.as_view(), name="external-invoices"),
    path("external/tickets/", ExternalTicketListView.as_view(), name="external-tickets"),
    path("external/disbursements/", ExternalDisbursementListView.as_view(), name="external-disbursements"),
    path("external/leases/", ExternalLeaseListView.as_view(), name="external-leases"),
]
