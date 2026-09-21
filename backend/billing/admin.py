from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import FeeInvoice, FeeLedgerEntry, Invoice, Payment


@admin.register(Invoice)
class InvoiceAdmin(ModelAdmin):
    list_display = ("id", "lease", "amount_due", "status", "due_date")
    list_filter = ("status",)


@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = ("mpesa_transaction_id", "invoice", "landlord_credential", "amount", "received_at")
    search_fields = ("mpesa_transaction_id",)


@admin.register(FeeLedgerEntry)
class FeeLedgerEntryAdmin(ModelAdmin):
    list_display = ("payment", "platform_fee_amount", "reseller_commission_amount", "reseller", "invoiced")
    list_filter = ("invoiced",)


@admin.register(FeeInvoice)
class FeeInvoiceAdmin(ModelAdmin):
    list_display = ("landlord", "period_start", "period_end", "total_amount", "status")
    list_filter = ("status",)