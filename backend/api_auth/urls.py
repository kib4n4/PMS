# backend/api_auth/urls.py

from django.urls import path

from .api_views import TokenView
from .external_views import ExternalInvoiceListView

urlpatterns = [
    path("oauth/token/", TokenView.as_view(), name="oauth-token"),
    path("external/invoices/", ExternalInvoiceListView.as_view(), name="external-invoices"),
]
