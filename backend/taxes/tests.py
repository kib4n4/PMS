# backend/taxes/tests.py

from datetime import date
from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import Role, User
from billing.models import Invoice, Payment
from integrations.kra import KRAClient
from landlords.models import Landlord, LandlordDarajaCredential, Organization
from leasing.models import Lease, LeaseStatus, Tenant
from properties.models import Property, Unit

from .models import LandlordKRACredential, RentalIncomeReturn, RentalIncomeReturnStatus
from .tasks import generate_all_landlord_rental_income_returns, generate_rental_income_return


def _build_landlord_with_payment(shortcode="900100", amount=10000):
    org = Organization.objects.create(name="Tax Org")
    user = User.objects.create_user(username=f"ll-tax-{shortcode}", role=Role.LANDLORD)
    landlord = Landlord.objects.create(organization=org, user=user, full_name="Tax Landlord")
    credential = LandlordDarajaCredential.objects.create(
        landlord=landlord, shortcode=shortcode, consumer_key="ck", consumer_secret="cs", passkey="pk",
    )
    prop = Property.objects.create(landlord=landlord, name="Tax Towers")
    unit = Unit.objects.create(property=prop, label="T1")
    tenant_user = User.objects.create_user(username=f"tenant-tax-{shortcode}", role=Role.TENANT, phone_number=f"+2547{shortcode}")
    tenant = Tenant.objects.create(user=tenant_user, full_name="Tax Tenant")
    lease = Lease.objects.create(unit=unit, tenant=tenant, rent_amount=amount, billing_day=1, start_date=date.today(), status=LeaseStatus.ACTIVE)
    invoice = Invoice.objects.create(lease=lease, period_start=date.today(), period_end=date.today(), amount_due=amount, due_date=date.today())
    Payment.objects.create(invoice=invoice, landlord_credential=credential, amount=amount, mpesa_transaction_id=f"TXNTAX{shortcode}")
    return landlord


class KRAClientStubTests(TestCase):
    def test_submit_rental_income_return_raises_not_implemented(self):
        client = KRAClient(client_id="id", client_secret="secret", kra_pin="A123456789Z")
        with self.assertRaises(NotImplementedError):
            client.submit_rental_income_return("2026-09-01", "2026-09-30", "10000", "750")

    def test_check_pin_status_raises_not_implemented(self):
        client = KRAClient(client_id="id", client_secret="secret", kra_pin="A123456789Z")
        with self.assertRaises(NotImplementedError):
            client.check_pin_status()

    def test_for_landlord_reads_decrypted_fields(self):
        landlord = _build_landlord_with_payment(shortcode="900101")
        credential = LandlordKRACredential.objects.create(
            landlord=landlord, kra_pin="A987654321B", client_id="kra-id", client_secret="kra-secret",
        )
        client = KRAClient.for_landlord(credential)
        self.assertEqual(client.client_id, "kra-id")
        self.assertEqual(client.client_secret, "kra-secret")
        self.assertEqual(client.kra_pin, "A987654321B")


class GenerateRentalIncomeReturnTests(TestCase):
    def test_no_payments_creates_no_return(self):
        org_landlord = _build_landlord_with_payment(shortcode="900200", amount=0)
        Payment.objects.all().delete()
        result = generate_rental_income_return(str(org_landlord.id), date(2026, 1, 1), date(2026, 1, 31))
        self.assertIsNone(result)
        self.assertEqual(RentalIncomeReturn.objects.count(), 0)

    def test_unknown_landlord_does_not_crash(self):
        import uuid

        result = generate_rental_income_return(str(uuid.uuid4()))
        self.assertIsNone(result)

    def test_no_kra_credential_marks_not_configured(self):
        landlord = _build_landlord_with_payment(shortcode="900300", amount=10000)
        today = date.today()
        result = generate_rental_income_return(str(landlord.id), today.replace(day=1), today)
        self.assertEqual(result.status, RentalIncomeReturnStatus.NOT_CONFIGURED)
        self.assertEqual(float(result.gross_rental_income), 10000.0)
        self.assertEqual(float(result.tax_due), 750.0)  # 7.5% of 10000

    def test_kra_credential_configured_stays_pending_until_real_filing_exists(self):
        landlord = _build_landlord_with_payment(shortcode="900400", amount=20000)
        LandlordKRACredential.objects.create(landlord=landlord, kra_pin="A111222333C", client_id="id", client_secret="secret")

        today = date.today()
        result = generate_rental_income_return(str(landlord.id), today.replace(day=1), today)

        self.assertEqual(result.status, RentalIncomeReturnStatus.PENDING)
        self.assertEqual(float(result.tax_due), 1500.0)  # 7.5% of 20000
        self.assertEqual(result.kra_reference, "")

    @patch("taxes.tasks.KRAClient.for_landlord")
    def test_successful_submission_marks_submitted(self, mock_for_landlord):
        from integrations.kra import ReturnSubmissionResult

        mock_client = mock_for_landlord.return_value
        mock_client.submit_rental_income_return.return_value = ReturnSubmissionResult(
            kra_reference="KRA-REF-001", status="accepted", message="OK"
        )

        landlord = _build_landlord_with_payment(shortcode="900500", amount=15000)
        LandlordKRACredential.objects.create(landlord=landlord, kra_pin="A444555666D", client_id="id", client_secret="secret")

        today = date.today()
        result = generate_rental_income_return(str(landlord.id), today.replace(day=1), today)

        self.assertEqual(result.status, RentalIncomeReturnStatus.SUBMITTED)
        self.assertEqual(result.kra_reference, "KRA-REF-001")
        self.assertIsNotNone(result.submitted_at)

    def test_rerunning_same_period_updates_pending_return_not_duplicates(self):
        landlord = _build_landlord_with_payment(shortcode="900600", amount=10000)
        today = date.today()

        first = generate_rental_income_return(str(landlord.id), today.replace(day=1), today)
        self.assertEqual(float(first.gross_rental_income), 10000.0)

        # A late payment lands for the same period.
        invoice = Invoice.objects.filter(lease__unit__property__landlord=landlord).first()
        credential = landlord.daraja_credential
        Payment.objects.create(invoice=invoice, landlord_credential=credential, amount=5000, mpesa_transaction_id="TXNLATE900600")

        second = generate_rental_income_return(str(landlord.id), today.replace(day=1), today)

        self.assertEqual(first.id, second.id)
        self.assertEqual(RentalIncomeReturn.objects.count(), 1)
        self.assertEqual(float(second.gross_rental_income), 15000.0)

    def test_does_not_overwrite_already_submitted_return(self):
        landlord = _build_landlord_with_payment(shortcode="900700", amount=10000)
        today = date.today()

        tax_return = RentalIncomeReturn.objects.create(
            landlord=landlord, period_start=today.replace(day=1), period_end=today,
            gross_rental_income=10000, tax_due=750, status=RentalIncomeReturnStatus.SUBMITTED,
            kra_reference="ALREADY-FILED",
        )

        result = generate_rental_income_return(str(landlord.id), today.replace(day=1), today)

        tax_return.refresh_from_db()
        self.assertEqual(result.id, tax_return.id)
        self.assertEqual(tax_return.status, RentalIncomeReturnStatus.SUBMITTED)
        self.assertEqual(tax_return.kra_reference, "ALREADY-FILED")
        self.assertEqual(float(tax_return.gross_rental_income), 10000.0)  # unchanged, not overwritten


class GenerateAllLandlordReturnsTests(TestCase):
    @patch("taxes.tasks.generate_rental_income_return.delay")
    def test_fans_out_per_landlord(self, mock_delay):
        landlord1 = _build_landlord_with_payment(shortcode="900800")
        landlord2 = _build_landlord_with_payment(shortcode="900801")

        generate_all_landlord_rental_income_returns()

        called_ids = {call.args[0] for call in mock_delay.call_args_list}
        self.assertEqual(called_ids, {str(landlord1.id), str(landlord2.id)})


class RentalIncomeReturnListViewTests(APITestCase):
    def setUp(self):
        self.landlord = _build_landlord_with_payment(shortcode="900900", amount=10000)
        self.other_landlord = _build_landlord_with_payment(shortcode="900901", amount=8000)
        today = date.today()
        self.own_return = RentalIncomeReturn.objects.create(
            landlord=self.landlord, period_start=today.replace(day=1), period_end=today,
            gross_rental_income=10000, tax_due=750,
        )
        self.other_return = RentalIncomeReturn.objects.create(
            landlord=self.other_landlord, period_start=today.replace(day=1), period_end=today,
            gross_rental_income=8000, tax_due=600,
        )
        self.super_admin = User.objects.create_superuser(username="root-tax", password="x", role=Role.ADMIN)

    def test_landlord_sees_only_own_returns(self):
        client = APIClient()
        client.force_authenticate(user=self.landlord.user)
        response = client.get("/api/taxes/returns/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in response.data}
        self.assertEqual(ids, {str(self.own_return.id)})

    def test_super_admin_sees_all_returns(self):
        client = APIClient()
        client.force_authenticate(user=self.super_admin)
        response = client.get("/api/taxes/returns/")
        ids = {row["id"] for row in response.data}
        self.assertEqual(ids, {str(self.own_return.id), str(self.other_return.id)})

    def test_tenant_sees_no_returns(self):
        tenant_user = self.landlord.properties.first().units.first().leases.first().tenant.user
        client = APIClient()
        client.force_authenticate(user=tenant_user)
        response = client.get("/api/taxes/returns/")
        self.assertEqual(response.data, [])

    def test_unauthenticated_request_rejected(self):
        response = self.client.get("/api/taxes/returns/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
