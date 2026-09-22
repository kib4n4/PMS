# backend/billing/api_views.py

import logging

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Role
from integrations.daraja import DarajaError

from .models import Invoice, Payment
from .pdf import render_invoice_pdf, render_receipt_pdf
from .services import (
    InvoiceAlreadyPaidError,
    LandlordNotReadyError,
    NoDarajaCredentialError,
    initiate_invoice_payment,
)

logger = logging.getLogger(__name__)

_InitiatePaymentRequestSerializer = inline_serializer(
    "InitiatePaymentRequest", {"phone_number": serializers.CharField(required=False)}
)
_InitiatePaymentResponseSerializer = inline_serializer(
    "InitiatePaymentResponse", {"detail": serializers.CharField(), "checkout_request_id": serializers.CharField()}
)


def _can_access_invoice(user, invoice: Invoice) -> bool:
    """Scoping rule for every billing endpoint below: super admin sees
    everything; a landlord only their own properties' invoices; a tenant
    only their own lease's invoices. Mirrors the pattern in
    leasing/api_views.py::LandlordTenantViewSet.get_queryset()."""
    if user.is_superuser:
        return True
    if user.role == Role.LANDLORD and hasattr(user, "landlord_profile"):
        return invoice.lease.unit.property.landlord_id == user.landlord_profile.id
    if user.role == Role.TENANT and hasattr(user, "tenant_profile"):
        return invoice.lease.tenant_id == user.tenant_profile.id
    return False


class InvoicePDFView(APIView):
    """GET /api/billing/invoices/<id>/pdf/ — downloadable invoice PDF."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="Download invoice PDF", responses={200: OpenApiTypes.BINARY})
    def get(self, request, pk):
        invoice = get_object_or_404(
            Invoice.objects.select_related("lease__unit__property__landlord", "lease__tenant"), pk=pk
        )
        if not _can_access_invoice(request.user, invoice):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        response = HttpResponse(render_invoice_pdf(invoice), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="invoice-{invoice.reference}.pdf"'
        return response


class PaymentReceiptView(APIView):
    """GET /api/billing/payments/<id>/receipt/ — downloadable payment receipt PDF."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="Download payment receipt PDF", responses={200: OpenApiTypes.BINARY})
    def get(self, request, pk):
        payment = get_object_or_404(
            Payment.objects.select_related("invoice__lease__unit__property__landlord", "invoice__lease__tenant"),
            pk=pk,
        )
        if not _can_access_invoice(request.user, payment.invoice):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        response = HttpResponse(render_receipt_pdf(payment), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="receipt-{payment.mpesa_transaction_id}.pdf"'
        return response


class InvoiceInitiatePaymentView(APIView):
    """
    POST /api/billing/invoices/<id>/pay/ {"phone_number"?} — triggers an
    STK Push for this invoice's remaining balance. Returns immediately
    with Safaricom's acknowledgment; the actual payment is recorded once
    /webhooks/mpesa/stk/callback/ lands
    (billing/tasks.py::ingest_stk_callback). Callers should treat a 202
    here as "push sent," not "payment received."
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Initiate M-Pesa STK Push for an invoice",
        request=_InitiatePaymentRequestSerializer,
        responses={202: _InitiatePaymentResponseSerializer},
    )
    def post(self, request, pk):
        invoice = get_object_or_404(
            Invoice.objects.select_related("lease__unit__property__landlord", "lease__tenant__user"), pk=pk
        )
        if not _can_access_invoice(request.user, invoice):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        phone_number = request.data.get("phone_number") or invoice.lease.tenant.user.phone_number
        if not phone_number:
            return Response({"detail": "phone_number is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            stk_request = initiate_invoice_payment(invoice, phone_number)
        except (NoDarajaCredentialError, LandlordNotReadyError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except InvoiceAlreadyPaidError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except DarajaError:
            logger.exception("STK push initiation failed for invoice %s", invoice.reference)
            return Response(
                {"detail": "Could not initiate payment. Try again shortly."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "detail": "STK push sent — enter your M-Pesa PIN to complete payment.",
                "checkout_request_id": stk_request.checkout_request_id,
            },
            status=status.HTTP_202_ACCEPTED,
        )
