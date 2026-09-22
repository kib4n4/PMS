# backend/billing/services.py

"""
Shared payment-initiation logic — the single place that calls
DarajaClient.initiate_stk_push AND records the matching STKPushRequest.
Both the authenticated API (billing/api_views.py) and the WhatsApp "Pay
Rent" flow (messaging/services.py) must go through here: skipping the
STKPushRequest write means /webhooks/mpesa/stk/callback/ has no way to
resolve the eventual result back to an Invoice (see
billing/tasks.py::ingest_stk_callback) and the payment would silently
vanish.
"""

from landlords.models import OnboardingStatus
from integrations.daraja import DarajaClient

from .models import FeeInvoiceStatus, STKPushRequest


class NoDarajaCredentialError(Exception):
    """Landlord has no LandlordDarajaCredential configured at all."""


class LandlordNotReadyError(Exception):
    """Landlord has a credential, but it isn't onboarded far enough to accept payments yet."""


class InvoiceAlreadyPaidError(Exception):
    pass


class NoPhoneNumberError(Exception):
    """No phone number available to send the STK Push to."""


def initiate_invoice_payment(invoice, phone_number: str) -> STKPushRequest:
    """
    Triggers an STK Push for `invoice`'s remaining balance to
    `phone_number` and persists the STKPushRequest correlation record.
    Raises DarajaError (from the HTTP call itself) or one of the
    exceptions above — never returns a "partial" state.
    """
    landlord = invoice.lease.unit.property.landlord
    credential = getattr(landlord, "daraja_credential", None)
    if credential is None:
        raise NoDarajaCredentialError(f"Landlord {landlord.id} has no Daraja credentials configured.")
    if credential.status not in (OnboardingStatus.LIVE, OnboardingStatus.SANDBOX_TESTING):
        raise LandlordNotReadyError(f"Landlord {landlord.id} Daraja credential is not ready: {credential.status}")

    remaining = invoice.amount_due - invoice.amount_paid
    if remaining <= 0:
        raise InvoiceAlreadyPaidError(f"Invoice {invoice.reference} is already fully paid.")

    client = DarajaClient.for_landlord(credential)
    result = client.initiate_stk_push(
        phone_number=phone_number, amount=str(remaining), account_reference=invoice.reference
    )

    return STKPushRequest.objects.create(
        invoice=invoice,
        landlord_credential=credential,
        checkout_request_id=result.checkout_request_id,
        merchant_request_id=result.merchant_request_id,
        phone_number=phone_number,
        amount=remaining,
    )


def initiate_fee_invoice_payment(fee_invoice, phone_number: str = "") -> STKPushRequest:
    """
    Triggers an STK Push against the PLATFORM's own shortcode (not the
    landlord's) to collect an accumulated FeeInvoice — the reverse money
    direction from initiate_invoice_payment (landlord -> platform, not
    tenant -> landlord). Persists the same STKPushRequest correlation
    record so /webhooks/mpesa/stk/callback/ (billing/tasks.py::
    ingest_stk_callback) can resolve the eventual result back to this
    FeeInvoice.
    """
    if fee_invoice.status == FeeInvoiceStatus.PAID:
        raise InvoiceAlreadyPaidError(f"FeeInvoice {fee_invoice.reference} is already paid.")

    phone_number = phone_number or fee_invoice.landlord.user.phone_number
    if not phone_number:
        raise NoPhoneNumberError(f"Landlord {fee_invoice.landlord_id} has no phone number on file.")

    client = DarajaClient.for_platform()
    result = client.initiate_stk_push(
        phone_number=phone_number, amount=str(fee_invoice.total_amount), account_reference=fee_invoice.reference
    )

    return STKPushRequest.objects.create(
        fee_invoice=fee_invoice,
        checkout_request_id=result.checkout_request_id,
        merchant_request_id=result.merchant_request_id,
        phone_number=phone_number,
        amount=fee_invoice.total_amount,
    )
