# backend/billing/urls.py

from django.urls import path

from .api_views import InvoiceInitiatePaymentView, InvoicePDFView, PaymentReceiptView

urlpatterns = [
    path("billing/invoices/<uuid:pk>/pdf/", InvoicePDFView.as_view(), name="invoice-pdf"),
    path("billing/invoices/<uuid:pk>/pay/", InvoiceInitiatePaymentView.as_view(), name="invoice-pay"),
    path("billing/payments/<uuid:pk>/receipt/", PaymentReceiptView.as_view(), name="payment-receipt"),
]
