# backend/billing/models.py

import secrets
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class InvoiceStatus(models.TextChoices):
    OPEN = "open", "Open"
    PARTIAL = "partial", "Partially Paid"
    PAID = "paid", "Paid"
    OVERDUE = "overdue", "Overdue"


def _generate_invoice_reference() -> str:
    # Short, M-Pesa AccountReference-safe (max 20 chars) — used both as
    # the STK Push AccountReference and to resolve inbound C2B/Paybill
    # payments back to the right Invoice.
    return f"RENT{secrets.token_hex(4).upper()}"


class Invoice(models.Model):
    """Generated per billing cycle per Lease. Rent is paid into the
    landlord's OWN paybill, never into a platform-held account."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lease = models.ForeignKey("leasing.Lease", on_delete=models.PROTECT, related_name="invoices")
    reference = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        help_text="M-Pesa AccountReference for this invoice — resolves inbound payments back to it.",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.OPEN, db_index=True
    )
    due_date = models.DateField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invoice {self.reference} — {self.lease} — {self.status}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = _generate_invoice_reference()
        super().save(*args, **kwargs)

    @property
    def amount_paid(self):
        return self.payments.aggregate(total=models.Sum("amount"))["total"] or 0

    def refresh_status(self):
        """Recompute status from actual recorded Payments — called after
        every Payment against this invoice rather than trusted to be set
        manually anywhere."""
        paid = self.amount_paid
        if paid >= self.amount_due:
            new_status = InvoiceStatus.PAID
        elif paid > 0:
            new_status = InvoiceStatus.PARTIAL
        elif self.due_date < timezone.now().date():
            new_status = InvoiceStatus.OVERDUE
        else:
            new_status = InvoiceStatus.OPEN
        if new_status != self.status:
            self.status = new_status
            self.save(update_fields=["status"])


class STKPushRequestStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"


class STKPushRequest(models.Model):
    """
    Tracks an in-flight STK Push. Safaricom's CallBackURL result does NOT
    echo back the AccountReference we sent — CheckoutRequestID is the
    only correlation key available, so it has to be persisted at
    initiation time for the callback to resolve back to an Invoice (or a
    FeeInvoice — see below) at all.

    Covers two distinct flows sharing one CallBackURL
    (/webhooks/mpesa/stk/callback/), discriminated by which of
    `invoice`/`fee_invoice` is set:
      - Tenant rent, via the landlord's own shortcode (`invoice` +
        `landlord_credential` set).
      - Platform fee collection, via the platform's own shortcode
        (`fee_invoice` set, `landlord_credential` blank — there is no
        landlord shortcode involved in the platform collecting its own
        fee from a landlord).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="stk_push_requests", null=True, blank=True
    )
    fee_invoice = models.ForeignKey(
        "FeeInvoice", on_delete=models.CASCADE, related_name="stk_push_requests", null=True, blank=True
    )
    landlord_credential = models.ForeignKey(
        "landlords.LandlordDarajaCredential",
        on_delete=models.CASCADE,
        related_name="stk_push_requests",
        null=True,
        blank=True,
        help_text="Set for tenant-rent pushes (landlord's own shortcode). Blank for platform-fee pushes.",
    )
    checkout_request_id = models.CharField(max_length=100, unique=True)
    merchant_request_id = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=10, choices=STKPushRequestStatus.choices, default=STKPushRequestStatus.PENDING
    )
    result_description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["checkout_request_id"])]

    def __str__(self):
        target = self.invoice.reference if self.invoice_id else self.fee_invoice.reference
        return f"STK push {self.checkout_request_id} — {target} ({self.status})"

    def clean(self):
        super().clean()
        if bool(self.invoice_id) == bool(self.fee_invoice_id):
            raise ValidationError("Exactly one of invoice/fee_invoice must be set.")
        if self.invoice_id and not self.landlord_credential_id:
            raise ValidationError("landlord_credential is required for a tenant-rent STK push.")
        if self.fee_invoice_id and self.landlord_credential_id:
            raise ValidationError("landlord_credential must be blank for a platform-fee STK push.")


class Payment(models.Model):
    """
    A single M-Pesa C2B receipt landing on a LANDLORD's own shortcode.
    The platform observes this via a shared webhook discriminated by
    shortcode — it never holds the funds.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    landlord_credential = models.ForeignKey(
        "landlords.LandlordDarajaCredential",
        on_delete=models.PROTECT,
        related_name="payments",
        help_text="Which landlord shortcode this payment arrived through",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    mpesa_transaction_id = models.CharField(
        max_length=100, unique=True,
        help_text="Safaricom TransactionID — dedupe key for idempotent ingestion",
    )
    mpesa_checkout_request_id = models.CharField(max_length=100, blank=True)
    raw_callback_payload = models.JSONField(
        default=dict, blank=True, help_text="Full C2B confirmation payload, for audit/replay"
    )
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["mpesa_transaction_id"])]

    def __str__(self):
        return f"Payment {self.mpesa_transaction_id} — {self.amount}"

    @property
    def landlord(self):
        """Convenience hop through landlord_credential — call sites were
        doing this two-hop lookup manually; centralized here instead."""
        return self.landlord_credential.landlord


class FeeLedgerEntry(models.Model):
    """
    Replaces the v1 three-way LedgerEntry split. Each confirmed Payment
    creates exactly one entry: the platform fee owed BY the landlord (a
    receivable), plus, if the landlord was referred, the reseller's
    referral commission owed — as an internal split of the platform's OWN
    fee, never billed separately to the landlord.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.OneToOneField(Payment, on_delete=models.PROTECT, related_name="fee_ledger_entry")
    platform_fee_amount = models.DecimalField(max_digits=12, decimal_places=2)
    reseller_commission_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Portion of platform_fee_amount owed to the referring Reseller, if any",
    )
    reseller = models.ForeignKey(
        "partners.Reseller", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="ledger_entries",
    )
    invoiced = models.BooleanField(
        default=False, db_index=True, help_text="Whether this has been rolled into a FeeInvoice"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"FeeLedgerEntry for {self.payment.mpesa_transaction_id} — fee {self.platform_fee_amount}"


class FeeInvoiceStatus(models.TextChoices):
    OPEN = "open", "Open"
    PAID = "paid", "Paid"
    OVERDUE = "overdue", "Overdue"


def _generate_fee_invoice_reference() -> str:
    # Distinct prefix from Invoice's RENT<hex> — this is a landlord paying
    # the PLATFORM its fee, not a tenant paying a landlord rent, and the
    # two must never be confused on a Safaricom statement or in logs.
    return f"FEE{secrets.token_hex(4).upper()}"


class FeeInvoice(models.Model):
    """
    Periodic bill the platform sends a landlord for accumulated platform
    fee. Collected via STK Push to the landlord (billing/services.py::
    initiate_fee_invoice_payment, using DarajaClient.for_platform()) or a
    manual admin mark-paid fallback — into the PLATFORM's own (separate,
    single) paybill, never a landlord's own shortcode.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    landlord = models.ForeignKey(
        "landlords.Landlord", on_delete=models.PROTECT, related_name="fee_invoices"
    )
    reference = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        help_text="M-Pesa AccountReference for this fee invoice on the platform's own shortcode.",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    ledger_entries = models.ManyToManyField(FeeLedgerEntry, related_name="fee_invoices")
    status = models.CharField(max_length=20, choices=FeeInvoiceStatus.choices, default=FeeInvoiceStatus.OPEN)
    mpesa_transaction_id = models.CharField(
        max_length=100, blank=True, help_text="Set once the landlord pays this invoice"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"FeeInvoice {self.id} — {self.landlord.full_name} — {self.total_amount} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = _generate_fee_invoice_reference()
        super().save(*args, **kwargs)

    def mark_paid(self, mpesa_transaction_id: str = ""):
        """Idempotent — safe to call again with the same transaction id
        (duplicate STK callback) or from the admin's manual fallback
        action (no transaction id, reconciled some other way)."""
        if self.status == FeeInvoiceStatus.PAID:
            return
        self.status = FeeInvoiceStatus.PAID
        update_fields = ["status"]
        if mpesa_transaction_id:
            self.mpesa_transaction_id = mpesa_transaction_id
            update_fields.append("mpesa_transaction_id")
        self.save(update_fields=update_fields)