# backend/billing/serializers.py

"""
JSON serializers for the internal, JWT-authenticated billing API
(billing/api_views.py's ViewSets). Before this existed, billing had only
PDF downloads and pay-initiation — no way for the frontend (or any JSON
client) to list/inspect invoices, payments, or fee invoices directly. The
external (OAuth2 client-credentials) API has its own separate, narrower
serializer — see api_auth/external_views.py::ExternalInvoiceSerializer —
this is not that.
"""

from rest_framework import serializers

from .models import FeeInvoice, FeeLedgerEntry, Invoice, Payment


class InvoiceSerializer(serializers.ModelSerializer):
    amount_paid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id", "reference", "period_start", "period_end",
            "amount_due", "amount_paid", "status", "due_date", "created_at",
        ]
        read_only_fields = fields


class PaymentSerializer(serializers.ModelSerializer):
    invoice_reference = serializers.CharField(source="invoice.reference", read_only=True)
    tenant_name = serializers.CharField(source="invoice.lease.tenant.full_name", read_only=True)
    unit_label = serializers.CharField(source="invoice.lease.unit.label", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "invoice", "invoice_reference", "tenant_name", "unit_label",
            "amount", "mpesa_transaction_id", "received_at",
        ]
        read_only_fields = fields


class FeeInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeInvoice
        fields = [
            "id", "reference", "landlord", "period_start", "period_end",
            "total_amount", "status", "mpesa_transaction_id", "created_at",
        ]
        read_only_fields = fields


class FeeLedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeLedgerEntry
        fields = ["id", "payment", "platform_fee_amount", "reseller_commission_amount", "invoiced", "created_at"]
        read_only_fields = fields
