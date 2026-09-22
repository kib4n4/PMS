from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from integrations.daraja import DarajaError

from .models import FeeInvoice, FeeInvoiceStatus, FeeLedgerEntry, Invoice, Payment, STKPushRequest
from .services import NoPhoneNumberError, initiate_fee_invoice_payment


class PaymentInline(TabularInline):
    """Read-only — Payment rows are created exclusively by
    billing/tasks.py::_record_payment (webhook-driven), never hand-entered."""

    model = Payment
    fields = ("mpesa_transaction_id", "amount", "landlord_credential", "received_at")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Invoice)
class InvoiceAdmin(ModelAdmin):
    list_display = ("reference", "lease", "amount_due", "status", "due_date")
    list_filter = ("status",)
    search_fields = ("reference",)
    autocomplete_fields = ("lease",)
    inlines = [PaymentInline]


@admin.register(STKPushRequest)
class STKPushRequestAdmin(ModelAdmin):
    list_display = ("checkout_request_id", "invoice", "fee_invoice", "phone_number", "amount", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("checkout_request_id", "phone_number")
    autocomplete_fields = ("invoice", "fee_invoice", "landlord_credential")


@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    list_display = ("mpesa_transaction_id", "invoice", "landlord_credential", "amount", "received_at")
    search_fields = ("mpesa_transaction_id",)
    autocomplete_fields = ("invoice", "landlord_credential")
    actions = ["resend_payment_receipt"]

    @admin.action(description="Resend payment receipt email")
    def resend_payment_receipt(self, request, queryset):
        from .tasks import send_payment_receipt_email

        for payment in queryset:
            send_payment_receipt_email.delay(str(payment.id))
        self.message_user(request, f"Queued {queryset.count()} receipt email(s).")


@admin.register(FeeLedgerEntry)
class FeeLedgerEntryAdmin(ModelAdmin):
    list_display = ("payment", "platform_fee_amount", "reseller_commission_amount", "reseller", "invoiced")
    list_filter = ("invoiced",)
    autocomplete_fields = ("payment", "reseller")


@admin.register(FeeInvoice)
class FeeInvoiceAdmin(ModelAdmin):
    list_display = ("reference", "landlord", "period_start", "period_end", "total_amount", "status")
    list_filter = ("status",)
    search_fields = ("reference",)
    autocomplete_fields = ("landlord",)
    actions = ["initiate_stk_push_action", "mark_fee_invoice_paid"]

    @admin.action(description="Initiate STK push to collect selected fee invoices")
    def initiate_stk_push_action(self, request, queryset):
        sent, failed = 0, 0
        for fee_invoice in queryset.exclude(status=FeeInvoiceStatus.PAID):
            try:
                initiate_fee_invoice_payment(fee_invoice)
                sent += 1
            except (NoPhoneNumberError, DarajaError) as exc:
                failed += 1
                self.message_user(request, f"{fee_invoice.reference}: {exc}", level="error")
        self.message_user(request, f"STK push sent for {sent} fee invoice(s); {failed} failed.")

    @admin.action(description="Mark selected fee invoices as paid (manual reconciliation)")
    def mark_fee_invoice_paid(self, request, queryset):
        count = 0
        for fee_invoice in queryset.exclude(status=FeeInvoiceStatus.PAID):
            fee_invoice.mark_paid()
            count += 1
        self.message_user(request, f"Marked {count} fee invoice(s) as paid.")
