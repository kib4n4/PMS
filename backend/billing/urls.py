# backend/billing/urls.py

from django.urls import path
from rest_framework.routers import DefaultRouter

from .api_views import (
    FeeInvoiceViewSet,
    FeeLedgerEntryViewSet,
    InvoiceInitiatePaymentView,
    InvoicePDFView,
    InvoiceViewSet,
    PaymentReceiptView,
    PaymentViewSet,
)

router = DefaultRouter()
router.register("billing/invoices", InvoiceViewSet, basename="billing-invoice")
router.register("billing/payments", PaymentViewSet, basename="billing-payment")
router.register("billing/fee-invoices", FeeInvoiceViewSet, basename="billing-fee-invoice")
router.register("billing/fee-ledger-entries", FeeLedgerEntryViewSet, basename="billing-fee-ledger-entry")

urlpatterns = [
    path("billing/invoices/<uuid:pk>/pdf/", InvoicePDFView.as_view(), name="invoice-pdf"),
    path("billing/invoices/<uuid:pk>/pay/", InvoiceInitiatePaymentView.as_view(), name="invoice-pay"),
    path("billing/payments/<uuid:pk>/receipt/", PaymentReceiptView.as_view(), name="payment-receipt"),
] + router.urls
