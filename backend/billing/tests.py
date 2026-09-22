# backend/billing/tests.py

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import Role, User
from integrations.daraja import DarajaError, STKPushResult
from landlords.models import Landlord, LandlordDarajaCredential, OnboardingStatus, Organization
from leasing.models import Lease, LeaseStatus, Tenant
from partners.models import ReferralCommissionRule, Reseller, PayoutAccount
from properties.models import Property, Unit

from .models import FeeInvoice, FeeInvoiceStatus, FeeLedgerEntry, Invoice, InvoiceStatus, Payment, STKPushRequest, STKPushRequestStatus
from .services import initiate_fee_invoice_payment
from .tasks import _record_payment, _resolve_invoice, generate_fee_invoices, ingest_c2b_confirmation, ingest_stk_callback


def _build_lease(rent_amount=10000, shortcode="174379", tenant_phone="+254711000001"):
    org = Organization.objects.create(name="Test Org")
    landlord_user = User.objects.create_user(username=f"landlord-{shortcode}", role=Role.LANDLORD)
    landlord = Landlord.objects.create(organization=org, user=landlord_user, full_name="Jane Landlord")
    credential = LandlordDarajaCredential.objects.create(
        landlord=landlord,
        shortcode=shortcode,
        consumer_key="ck",
        consumer_secret="cs",
        passkey="pk",
        initiator_credential="init",
        security_credential="seccred",
        status=OnboardingStatus.SANDBOX_TESTING,
    )
    prop = Property.objects.create(landlord=landlord, name="Sunrise Apartments")
    unit = Unit.objects.create(property=prop, label="A1")
    tenant_user = User.objects.create_user(
        username=f"tenant-{shortcode}", role=Role.TENANT, phone_number=tenant_phone
    )
    tenant = Tenant.objects.create(user=tenant_user, full_name="Tom Tenant")
    lease = Lease.objects.create(
        unit=unit, tenant=tenant, rent_amount=rent_amount, billing_day=1,
        start_date=date.today(), status=LeaseStatus.ACTIVE,
    )
    return credential, lease


def _build_invoice(lease, amount_due=10000, due_date=None):
    return Invoice.objects.create(
        lease=lease, period_start=date.today().replace(day=1), period_end=date.today(),
        amount_due=amount_due, due_date=due_date or (date.today() + timedelta(days=5)),
    )


class InvoiceModelTests(TestCase):
    def test_reference_is_auto_generated_and_unique(self):
        _, lease = _build_lease()
        invoice_a = _build_invoice(lease)
        invoice_b = _build_invoice(lease)
        self.assertTrue(invoice_a.reference)
        self.assertNotEqual(invoice_a.reference, invoice_b.reference)

    def test_refresh_status_transitions_open_partial_paid(self):
        credential, lease = _build_lease(rent_amount=10000)
        invoice = _build_invoice(lease, amount_due=10000)
        self.assertEqual(invoice.status, InvoiceStatus.OPEN)

        Payment.objects.create(
            invoice=invoice, landlord_credential=credential, amount=4000, mpesa_transaction_id="TXN1",
        )
        invoice.refresh_status()
        self.assertEqual(invoice.status, InvoiceStatus.PARTIAL)

        Payment.objects.create(
            invoice=invoice, landlord_credential=credential, amount=6000, mpesa_transaction_id="TXN2",
        )
        invoice.refresh_status()
        self.assertEqual(invoice.status, InvoiceStatus.PAID)

    def test_refresh_status_overdue_when_unpaid_past_due_date(self):
        _, lease = _build_lease()
        invoice = _build_invoice(lease, amount_due=10000, due_date=date.today() - timedelta(days=1))
        invoice.refresh_status()
        self.assertEqual(invoice.status, InvoiceStatus.OVERDUE)


class ResolveInvoiceTests(TestCase):
    def test_resolves_by_reference(self):
        credential, lease = _build_lease()
        invoice = _build_invoice(lease)
        resolved = _resolve_invoice(credential, invoice.reference, msisdn="")
        self.assertEqual(resolved.id, invoice.id)

    def test_resolves_by_msisdn_when_reference_missing(self):
        credential, lease = _build_lease(tenant_phone="+254722000002")
        invoice = _build_invoice(lease)
        resolved = _resolve_invoice(credential, account_reference="", msisdn="254722000002")
        self.assertEqual(resolved.id, invoice.id)

    def test_returns_none_when_nothing_matches(self):
        credential, _lease = _build_lease()
        resolved = _resolve_invoice(credential, account_reference="NOPE", msisdn="254700000000")
        self.assertIsNone(resolved)

    def test_excludes_already_paid_invoices(self):
        credential, lease = _build_lease(rent_amount=5000)
        invoice = _build_invoice(lease, amount_due=5000)
        Payment.objects.create(
            invoice=invoice, landlord_credential=credential, amount=5000, mpesa_transaction_id="TXNPAID"
        )
        invoice.refresh_status()
        self.assertEqual(invoice.status, InvoiceStatus.PAID)
        resolved = _resolve_invoice(credential, invoice.reference, msisdn="")
        self.assertIsNone(resolved)


class RecordPaymentFeeMathTests(TestCase):
    def test_platform_fee_is_five_percent(self):
        credential, lease = _build_lease()
        invoice = _build_invoice(lease, amount_due=10000)
        payment = _record_payment(
            invoice=invoice, credential=credential, amount=10000,
            transaction_id="TXNFEE", raw_payload={},
        )
        entry = FeeLedgerEntry.objects.get(payment=payment)
        self.assertEqual(float(entry.platform_fee_amount), 500.0)
        self.assertEqual(float(entry.reseller_commission_amount), 0.0)

    def test_reseller_commission_is_ten_percent_of_platform_fee(self):
        payout_account = PayoutAccount.objects.create(phone_number="+254700999999")
        reseller_user = User.objects.create_user(username="reseller1", role=Role.RESELLER)
        reseller = Reseller.objects.create(user=reseller_user, full_name="Ray Reseller", payout_account=payout_account)

        credential, lease = _build_lease(rent_amount=10000)
        credential.landlord.referred_by = reseller
        credential.landlord.save(update_fields=["referred_by"])
        ReferralCommissionRule.objects.create(reseller=reseller, landlord=credential.landlord, rate_percent=10)

        invoice = _build_invoice(lease, amount_due=10000)
        payment = _record_payment(
            invoice=invoice, credential=credential, amount=10000,
            transaction_id="TXNCOMM", raw_payload={},
        )
        entry = FeeLedgerEntry.objects.get(payment=payment)
        # platform fee = 500 (5% of 10000); reseller commission = 10% of 500 = 50
        self.assertEqual(float(entry.platform_fee_amount), 500.0)
        self.assertEqual(float(entry.reseller_commission_amount), 50.0)
        self.assertEqual(entry.reseller_id, reseller.id)

    def test_duplicate_transaction_id_is_not_recorded_twice(self):
        credential, lease = _build_lease()
        invoice = _build_invoice(lease, amount_due=10000)
        first = _record_payment(
            invoice=invoice, credential=credential, amount=5000,
            transaction_id="TXNDUPE", raw_payload={},
        )
        second = _record_payment(
            invoice=invoice, credential=credential, amount=5000,
            transaction_id="TXNDUPE", raw_payload={},
        )
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(Payment.objects.filter(mpesa_transaction_id="TXNDUPE").count(), 1)

    def test_fee_rounds_with_decimal_half_up_not_float(self):
        # 246.90 * 0.05 = 12.345 exactly in Decimal (rounds to 12.35 under
        # ROUND_HALF_UP); in binary float, 246.90 * 0.05 == 12.344999999999999,
        # which round()s down to 12.34 — the bug this fix closes.
        credential, lease = _build_lease(rent_amount=Decimal("246.90"), shortcode="600900")
        invoice = _build_invoice(lease, amount_due=Decimal("246.90"))
        payment = _record_payment(
            invoice=invoice, credential=credential, amount=Decimal("246.90"),
            transaction_id="TXNROUND", raw_payload={},
        )
        entry = FeeLedgerEntry.objects.get(payment=payment)
        self.assertEqual(entry.platform_fee_amount, Decimal("12.35"))

    def test_integrity_error_race_is_treated_as_duplicate(self):
        """Simulates two near-simultaneous deliveries of the same callback
        both passing the pre-check before either commits — the DB unique
        constraint's IntegrityError must be caught, not propagated."""
        credential, lease = _build_lease(shortcode="601000")
        invoice = _build_invoice(lease, amount_due=10000)

        with patch("billing.models.Payment.objects.create", side_effect=IntegrityError("duplicate key")):
            result = _record_payment(
                invoice=invoice, credential=credential, amount=10000,
                transaction_id="TXNRACE", raw_payload={},
            )
        self.assertIsNone(result)
        self.assertFalse(Payment.objects.filter(mpesa_transaction_id="TXNRACE").exists())


class IngestC2BConfirmationTests(TestCase):
    def test_unknown_shortcode_creates_no_payment(self):
        ingest_c2b_confirmation({
            "BusinessShortCode": "999999", "TransID": "TXNUNK", "TransAmount": "1000", "BillRefNumber": "X",
        })
        self.assertFalse(Payment.objects.filter(mpesa_transaction_id="TXNUNK").exists())

    def test_missing_required_fields_creates_no_payment(self):
        ingest_c2b_confirmation({"BusinessShortCode": "174379"})
        self.assertEqual(Payment.objects.count(), 0)

    def test_valid_payload_records_payment_and_updates_invoice(self):
        credential, lease = _build_lease(rent_amount=10000, shortcode="500100")
        invoice = _build_invoice(lease, amount_due=10000)

        ingest_c2b_confirmation({
            "BusinessShortCode": "500100",
            "TransID": "TXNC2B1",
            "TransAmount": "10000",
            "BillRefNumber": invoice.reference,
            "MSISDN": "254711000001",
        })

        payment = Payment.objects.get(mpesa_transaction_id="TXNC2B1")
        self.assertEqual(payment.invoice_id, invoice.id)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, InvoiceStatus.PAID)

    def test_no_matching_invoice_creates_no_payment(self):
        credential, _lease = _build_lease(shortcode="500200", tenant_phone="+254700111222")
        ingest_c2b_confirmation({
            "BusinessShortCode": "500200", "TransID": "TXNNOMATCH", "TransAmount": "1000",
            "BillRefNumber": "GARBAGE", "MSISDN": "254799999999",
        })
        self.assertFalse(Payment.objects.filter(mpesa_transaction_id="TXNNOMATCH").exists())


class IngestSTKCallbackTests(TestCase):
    def _make_stk_request(self, credential, invoice, checkout_id="ws_CO_1"):
        return STKPushRequest.objects.create(
            invoice=invoice, landlord_credential=credential, checkout_request_id=checkout_id,
            merchant_request_id="mr_1", phone_number="+254711000001", amount=invoice.amount_due,
        )

    def test_successful_callback_records_payment(self):
        credential, lease = _build_lease(rent_amount=8000, shortcode="500300")
        invoice = _build_invoice(lease, amount_due=8000)
        stk_request = self._make_stk_request(credential, invoice)

        ingest_stk_callback({
            "Body": {"stkCallback": {
                "MerchantRequestID": "mr_1", "CheckoutRequestID": "ws_CO_1",
                "ResultCode": 0, "ResultDesc": "Success",
                "CallbackMetadata": {"Item": [
                    {"Name": "Amount", "Value": 8000},
                    {"Name": "MpesaReceiptNumber", "Value": "TXNSTK1"},
                    {"Name": "PhoneNumber", "Value": 254711000001},
                ]},
            }}
        })

        self.assertTrue(Payment.objects.filter(mpesa_transaction_id="TXNSTK1").exists())
        stk_request.refresh_from_db()
        self.assertEqual(stk_request.status, STKPushRequestStatus.SUCCESS)

    def test_failed_callback_marks_stk_request_failed_without_payment(self):
        credential, lease = _build_lease(shortcode="500400")
        invoice = _build_invoice(lease)
        stk_request = self._make_stk_request(credential, invoice, checkout_id="ws_CO_2")

        ingest_stk_callback({
            "Body": {"stkCallback": {
                "MerchantRequestID": "mr_2", "CheckoutRequestID": "ws_CO_2",
                "ResultCode": 1032, "ResultDesc": "Request cancelled by user",
            }}
        })

        stk_request.refresh_from_db()
        self.assertEqual(stk_request.status, STKPushRequestStatus.FAILED)
        self.assertEqual(Payment.objects.count(), 0)

    def test_unknown_checkout_request_id_does_not_crash(self):
        ingest_stk_callback({
            "Body": {"stkCallback": {"CheckoutRequestID": "ws_CO_UNKNOWN", "ResultCode": 0}}
        })
        self.assertEqual(Payment.objects.count(), 0)

    def test_duplicate_callback_is_ignored(self):
        credential, lease = _build_lease(rent_amount=5000, shortcode="500500")
        invoice = _build_invoice(lease, amount_due=5000)
        self._make_stk_request(credential, invoice, checkout_id="ws_CO_3")

        payload = {
            "Body": {"stkCallback": {
                "MerchantRequestID": "mr_3", "CheckoutRequestID": "ws_CO_3",
                "ResultCode": 0, "ResultDesc": "Success",
                "CallbackMetadata": {"Item": [
                    {"Name": "Amount", "Value": 5000},
                    {"Name": "MpesaReceiptNumber", "Value": "TXNSTK3"},
                ]},
            }}
        }
        ingest_stk_callback(payload)
        ingest_stk_callback(payload)
        self.assertEqual(Payment.objects.filter(mpesa_transaction_id="TXNSTK3").count(), 1)


class GenerateFeeInvoicesTests(TestCase):
    def test_rolls_up_uninvoiced_entries(self):
        credential, lease = _build_lease(rent_amount=10000, shortcode="500600")
        invoice = _build_invoice(lease, amount_due=10000)
        _record_payment(
            invoice=invoice, credential=credential, amount=10000,
            transaction_id="TXNROLLUP", raw_payload={},
        )

        generate_fee_invoices()

        entry = FeeLedgerEntry.objects.get(payment__mpesa_transaction_id="TXNROLLUP")
        self.assertTrue(entry.invoiced)
        fee_invoice = credential.landlord.fee_invoices.get()
        self.assertEqual(float(fee_invoice.total_amount), float(entry.platform_fee_amount))

    def test_aggregates_multiple_entries_correctly(self):
        credential, lease = _build_lease(rent_amount=10000, shortcode="500650")
        for i, amount in enumerate([1000, 2000, 3000]):
            invoice = _build_invoice(lease, amount_due=amount)
            _record_payment(
                invoice=invoice, credential=credential, amount=amount,
                transaction_id=f"TXNAGG{i}", raw_payload={},
            )
        # 5% of (1000+2000+3000) = 300
        generate_fee_invoices()
        fee_invoice = credential.landlord.fee_invoices.get()
        self.assertEqual(fee_invoice.total_amount, Decimal("300.00"))

    def test_entry_outside_period_window_is_not_invoiced(self):
        credential, lease = _build_lease(rent_amount=10000, shortcode="500700")
        invoice = _build_invoice(lease, amount_due=10000)
        payment = _record_payment(
            invoice=invoice, credential=credential, amount=10000,
            transaction_id="TXNOUTOFPERIOD", raw_payload={},
        )
        entry = FeeLedgerEntry.objects.get(payment=payment)

        # A period entirely before the payment's received_at — the entry
        # must stay un-invoiced rather than being swept up regardless of
        # when it actually landed.
        yesterday = timezone.now().date() - timedelta(days=1)
        generate_fee_invoices(period_start=yesterday - timedelta(days=5), period_end=yesterday)

        entry.refresh_from_db()
        self.assertFalse(entry.invoiced)
        self.assertFalse(credential.landlord.fee_invoices.exists())


class FeeInvoicePaymentFlowTests(TestCase):
    """billing/services.py::initiate_fee_invoice_payment + the STK
    callback's fee_invoice branch — previously FeeInvoiceStatus.PAID and
    mpesa_transaction_id were defined but nothing ever set them."""

    def _make_fee_invoice(self, total_amount=1000):
        org = Organization.objects.create(name="Fee Org")
        landlord_user = User.objects.create_user(
            username="fee-landlord", role=Role.LANDLORD, phone_number="+254711555000"
        )
        landlord = Landlord.objects.create(organization=org, user=landlord_user, full_name="Fee Landlord")
        return FeeInvoice.objects.create(
            landlord=landlord,
            period_start=date.today().replace(day=1),
            period_end=date.today(),
            total_amount=total_amount,
        )

    def test_reference_is_auto_generated_with_distinct_prefix(self):
        fee_invoice = self._make_fee_invoice()
        self.assertTrue(fee_invoice.reference.startswith("FEE"))

    def test_mark_paid_is_idempotent(self):
        fee_invoice = self._make_fee_invoice()
        fee_invoice.mark_paid(mpesa_transaction_id="TXNFEEMANUAL")
        self.assertEqual(fee_invoice.status, FeeInvoiceStatus.PAID)
        self.assertEqual(fee_invoice.mpesa_transaction_id, "TXNFEEMANUAL")

        # Calling again (e.g. duplicate webhook) must not error or overwrite.
        fee_invoice.mark_paid(mpesa_transaction_id="TXNFEEMANUAL")
        fee_invoice.refresh_from_db()
        self.assertEqual(fee_invoice.status, FeeInvoiceStatus.PAID)

    @patch("billing.services.DarajaClient.for_platform")
    def test_initiate_fee_invoice_payment_uses_landlord_phone_by_default(self, mock_for_platform):
        mock_client = MagicMock()
        mock_client.initiate_stk_push.return_value = STKPushResult(
            checkout_request_id="ws_CO_FEE1", merchant_request_id="mr_fee1", response_description="Accepted"
        )
        mock_for_platform.return_value = mock_client

        fee_invoice = self._make_fee_invoice(total_amount=500)
        stk_request = initiate_fee_invoice_payment(fee_invoice)

        self.assertEqual(stk_request.fee_invoice_id, fee_invoice.id)
        self.assertIsNone(stk_request.invoice_id)
        self.assertIsNone(stk_request.landlord_credential_id)
        self.assertEqual(stk_request.phone_number, "+254711555000")
        mock_client.initiate_stk_push.assert_called_once_with(
            phone_number="+254711555000", amount="500", account_reference=fee_invoice.reference
        )

    def test_stk_callback_marks_fee_invoice_paid(self):
        fee_invoice = self._make_fee_invoice(total_amount=750)
        STKPushRequest.objects.create(
            fee_invoice=fee_invoice, checkout_request_id="ws_CO_FEE2",
            merchant_request_id="mr_fee2", phone_number="+254711555000", amount=750,
        )

        ingest_stk_callback({
            "Body": {"stkCallback": {
                "MerchantRequestID": "mr_fee2", "CheckoutRequestID": "ws_CO_FEE2",
                "ResultCode": 0, "ResultDesc": "Success",
                "CallbackMetadata": {"Item": [
                    {"Name": "Amount", "Value": 750},
                    {"Name": "MpesaReceiptNumber", "Value": "TXNFEESTK"},
                ]},
            }}
        })

        fee_invoice.refresh_from_db()
        self.assertEqual(fee_invoice.status, FeeInvoiceStatus.PAID)
        self.assertEqual(fee_invoice.mpesa_transaction_id, "TXNFEESTK")
        # No Payment/FeeLedgerEntry is created for a platform-fee collection —
        # those model tenant->landlord rent, not landlord->platform fee.
        self.assertFalse(Payment.objects.filter(mpesa_transaction_id="TXNFEESTK").exists())

    def test_duplicate_fee_invoice_callback_is_idempotent(self):
        fee_invoice = self._make_fee_invoice(total_amount=400)
        STKPushRequest.objects.create(
            fee_invoice=fee_invoice, checkout_request_id="ws_CO_FEE3",
            merchant_request_id="mr_fee3", phone_number="+254711555000", amount=400,
        )
        payload = {
            "Body": {"stkCallback": {
                "MerchantRequestID": "mr_fee3", "CheckoutRequestID": "ws_CO_FEE3",
                "ResultCode": 0, "ResultDesc": "Success",
                "CallbackMetadata": {"Item": [
                    {"Name": "Amount", "Value": 400},
                    {"Name": "MpesaReceiptNumber", "Value": "TXNFEEDUPE"},
                ]},
            }}
        }
        ingest_stk_callback(payload)
        # Second delivery hits the "already resolved" short-circuit (status
        # is no longer PENDING) rather than the fee_invoice branch at all.
        ingest_stk_callback(payload)

        fee_invoice.refresh_from_db()
        self.assertEqual(fee_invoice.status, FeeInvoiceStatus.PAID)
        self.assertEqual(fee_invoice.mpesa_transaction_id, "TXNFEEDUPE")


class STKPushRequestValidationTests(TestCase):
    def test_requires_exactly_one_of_invoice_or_fee_invoice(self):
        credential, lease = _build_lease(shortcode="601100")
        invoice = _build_invoice(lease)
        neither = STKPushRequest(checkout_request_id="x1", phone_number="+254700000000", amount=100)
        with self.assertRaises(ValidationError):
            neither.clean()

        both = STKPushRequest(
            checkout_request_id="x2", phone_number="+254700000000", amount=100,
            invoice=invoice, landlord_credential=credential,
        )
        fee_invoice = FeeInvoice.objects.create(
            landlord=credential.landlord, period_start=date.today(), period_end=date.today(), total_amount=100
        )
        both.fee_invoice = fee_invoice
        with self.assertRaises(ValidationError):
            both.clean()

    def test_invoice_requires_landlord_credential(self):
        credential, lease = _build_lease(shortcode="601200")
        invoice = _build_invoice(lease)
        missing_credential = STKPushRequest(
            checkout_request_id="x3", phone_number="+254700000000", amount=100, invoice=invoice
        )
        with self.assertRaises(ValidationError):
            missing_credential.clean()

    def test_fee_invoice_forbids_landlord_credential(self):
        credential, lease = _build_lease(shortcode="601300")
        fee_invoice = FeeInvoice.objects.create(
            landlord=credential.landlord, period_start=date.today(), period_end=date.today(), total_amount=100
        )
        extra_credential = STKPushRequest(
            checkout_request_id="x4", phone_number="+254700000000", amount=100,
            fee_invoice=fee_invoice, landlord_credential=credential,
        )
        with self.assertRaises(ValidationError):
            extra_credential.clean()


class WebhookViewTests(TestCase):
    def test_c2b_confirmation_rejects_malformed_json(self):
        response = self.client.post(
            "/webhooks/mpesa/c2b/confirmation/", data=b"not-json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ResultCode"], 1)

    @patch("billing.webhook_views.ingest_c2b_confirmation.delay")
    def test_c2b_confirmation_dispatches_task(self, mock_delay):
        payload = {"BusinessShortCode": "174379", "TransID": "T1", "TransAmount": "100"}
        response = self.client.post("/webhooks/mpesa/c2b/confirmation/", data=payload, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ResultCode"], 0)
        mock_delay.assert_called_once_with(payload)

    @patch("billing.webhook_views.ingest_stk_callback.delay")
    def test_stk_callback_dispatches_task(self, mock_delay):
        payload = {"Body": {"stkCallback": {"CheckoutRequestID": "x", "ResultCode": 0}}}
        response = self.client.post("/webhooks/mpesa/stk/callback/", data=payload, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        mock_delay.assert_called_once_with(payload)

    @patch("partners.tasks.handle_b2c_result.delay")
    def test_b2c_result_dispatches_task(self, mock_delay):
        payload = {"Result": {"ConversationID": "c1", "ResultCode": 0}}
        response = self.client.post("/webhooks/mpesa/b2c/result/", data=payload, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        mock_delay.assert_called_once_with(payload)


class BillingAPIAccessControlTests(APITestCase):
    def setUp(self):
        self.credential, self.lease = _build_lease(rent_amount=10000, shortcode="600100")
        self.invoice = _build_invoice(self.lease, amount_due=10000)
        self.super_admin = User.objects.create_superuser(username="root2", password="x", role=Role.ADMIN)

        other_org = Organization.objects.create(name="Other Org")
        other_landlord_user = User.objects.create_user(username="other-landlord", role=Role.LANDLORD)
        self.other_landlord = Landlord.objects.create(
            organization=other_org, user=other_landlord_user, full_name="Other Landlord"
        )

    def test_tenant_can_download_own_invoice_pdf(self):
        client = APIClient()
        client.force_authenticate(user=self.lease.tenant.user)
        response = client.get(f"/api/billing/invoices/{self.invoice.id}/pdf/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_unrelated_landlord_gets_404_not_403(self):
        client = APIClient()
        client.force_authenticate(user=self.other_landlord.user)
        response = client.get(f"/api/billing/invoices/{self.invoice.id}/pdf/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_super_admin_can_access_any_invoice(self):
        client = APIClient()
        client.force_authenticate(user=self.super_admin)
        response = client.get(f"/api/billing/invoices/{self.invoice.id}/pdf/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_request_rejected(self):
        response = self.client.get(f"/api/billing/invoices/{self.invoice.id}/pdf/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("billing.services.DarajaClient.initiate_stk_push")
    def test_initiate_payment_creates_stk_push_request(self, mock_stk):
        mock_stk.return_value = STKPushResult(
            checkout_request_id="ws_CO_TEST", merchant_request_id="mr_test", response_description="Accepted"
        )
        client = APIClient()
        client.force_authenticate(user=self.lease.tenant.user)
        response = client.post(f"/api/billing/invoices/{self.invoice.id}/pay/")
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertTrue(STKPushRequest.objects.filter(checkout_request_id="ws_CO_TEST").exists())

    def test_initiate_payment_rejects_already_paid_invoice(self):
        Payment.objects.create(
            invoice=self.invoice, landlord_credential=self.credential, amount=10000,
            mpesa_transaction_id="TXNPREPAID",
        )
        self.invoice.refresh_status()
        client = APIClient()
        client.force_authenticate(user=self.lease.tenant.user)
        response = client.post(f"/api/billing/invoices/{self.invoice.id}/pay/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("billing.services.DarajaClient.initiate_stk_push")
    def test_initiate_payment_returns_502_on_daraja_error(self, mock_stk):
        mock_stk.side_effect = DarajaError("boom")
        client = APIClient()
        client.force_authenticate(user=self.lease.tenant.user)
        response = client.post(f"/api/billing/invoices/{self.invoice.id}/pay/")
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)


class BillingJSONAPITests(APITestCase):
    """InvoiceViewSet/PaymentViewSet/FeeInvoiceViewSet — the JSON list/
    detail API that didn't exist before (only PDF download + pay-initiation
    did). Scoping reuses accounts.rbac.resolve_actor_scope."""

    def setUp(self):
        self.credential, self.lease = _build_lease(rent_amount=10000, shortcode="700100")
        self.invoice = _build_invoice(self.lease, amount_due=10000)
        self.payment = Payment.objects.create(
            invoice=self.invoice, landlord_credential=self.credential, amount=10000,
            mpesa_transaction_id="TXNJSONAPI",
        )
        self.fee_invoice = FeeInvoice.objects.create(
            landlord=self.credential.landlord, period_start=date.today(), period_end=date.today(), total_amount=500
        )
        self.fee_ledger_entry = FeeLedgerEntry.objects.create(payment=self.payment, platform_fee_amount=500)
        self.admin = User.objects.create_superuser(username="json-admin", password="x", role=Role.ADMIN)

        other_org = Organization.objects.create(name="Other Org JSON")
        other_landlord_user = User.objects.create_user(username="other-landlord-json", role=Role.LANDLORD)
        self.other_landlord = Landlord.objects.create(
            organization=other_org, user=other_landlord_user, full_name="Other Landlord JSON"
        )

    def test_admin_sees_all_invoices(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        response = client.get("/api/billing/invoices/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in response.data}
        self.assertIn(str(self.invoice.id), ids)

    def test_landlord_sees_only_their_own_invoices(self):
        client = APIClient()
        client.force_authenticate(user=self.credential.landlord.user)
        response = client.get("/api/billing/invoices/")
        ids = {row["id"] for row in response.data}
        self.assertEqual(ids, {str(self.invoice.id)})

    def test_unrelated_landlord_sees_no_invoices(self):
        client = APIClient()
        client.force_authenticate(user=self.other_landlord.user)
        response = client.get("/api/billing/invoices/")
        self.assertEqual(response.data, [])

    def test_tenant_sees_only_their_own_payments(self):
        client = APIClient()
        client.force_authenticate(user=self.lease.tenant.user)
        response = client.get("/api/billing/payments/")
        ids = {row["id"] for row in response.data}
        self.assertEqual(ids, {str(self.payment.id)})

    def test_fee_invoices_scoped_to_landlord_not_tenant(self):
        client = APIClient()
        client.force_authenticate(user=self.lease.tenant.user)
        response = client.get("/api/billing/fee-invoices/")
        self.assertEqual(response.data, [])

        client.force_authenticate(user=self.credential.landlord.user)
        response = client.get("/api/billing/fee-invoices/")
        ids = {row["id"] for row in response.data}
        self.assertEqual(ids, {str(self.fee_invoice.id)})

    def test_unauthenticated_request_rejected(self):
        response = self.client.get("/api/billing/invoices/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_fee_ledger_entries_scoped_to_landlord(self):
        client = APIClient()
        client.force_authenticate(user=self.other_landlord.user)
        response = client.get("/api/billing/fee-ledger-entries/")
        self.assertEqual(response.data, [])

        client.force_authenticate(user=self.credential.landlord.user)
        response = client.get("/api/billing/fee-ledger-entries/")
        ids = {row["id"] for row in response.data}
        self.assertEqual(ids, {str(self.fee_ledger_entry.id)})


class ReconciliationTests(TestCase):
    @patch("billing.tasks.DarajaClient.for_landlord")
    def test_reconcile_queries_recent_payments(self, mock_for_landlord):
        mock_client = MagicMock()
        mock_for_landlord.return_value = mock_client

        credential, lease = _build_lease(rent_amount=5000, shortcode="600200")
        invoice = _build_invoice(lease, amount_due=5000)
        _record_payment(
            invoice=invoice, credential=credential, amount=5000,
            transaction_id="TXNRECON", raw_payload={},
        )

        from .tasks import reconcile_landlord_transactions
        reconcile_landlord_transactions(str(credential.id))

        mock_client.query_transaction_status.assert_called_once_with("TXNRECON")


class LogTransactionStatusResultTests(TestCase):
    def test_mismatch_persists_audit_log_entry(self):
        from audit.models import AuditLog
        from .tasks import log_transaction_status_result

        log_transaction_status_result({
            "Result": {"ResultCode": 1, "ResultDesc": "Transaction not found", "TransactionID": "TXNMISMATCH"}
        })

        entry = AuditLog.objects.get(action="reconciliation_mismatch")
        self.assertEqual(entry.target_object_id, "TXNMISMATCH")
        self.assertEqual(entry.reason, "Transaction not found")

    def test_match_does_not_persist_audit_log_entry(self):
        from audit.models import AuditLog
        from .tasks import log_transaction_status_result

        log_transaction_status_result({"Result": {"ResultCode": 0, "ResultDesc": "OK"}})

        self.assertFalse(AuditLog.objects.filter(action="reconciliation_mismatch").exists())
