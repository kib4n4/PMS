# backend/partners/tests.py

from datetime import date, timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import Role, User
from billing.models import FeeLedgerEntry, Invoice, Payment
from integrations.daraja import B2CResult, DarajaError
from landlords.models import Landlord, LandlordDarajaCredential, Organization
from leasing.models import Lease, LeaseStatus, Tenant
from properties.models import Property, Unit

from .models import (
    Disbursement,
    DisbursementRecipientType,
    DisbursementStatus,
    Investor,
    PayoutAccount,
    ReferralCommissionRule,
    Reseller,
    RevenueShareAgreement,
    RevenueShareBasis,
)


def _build_landlord_with_payment(shortcode="700100"):
    org = Organization.objects.create(name="Org")
    user = User.objects.create_user(username=f"ll-{shortcode}", role=Role.LANDLORD)
    landlord = Landlord.objects.create(organization=org, user=user, full_name="Landlord X")
    credential = LandlordDarajaCredential.objects.create(
        landlord=landlord, shortcode=shortcode, consumer_key="ck", consumer_secret="cs", passkey="pk",
    )
    tenant_user = User.objects.create_user(username=f"tenant-{shortcode}", role=Role.TENANT, phone_number=f"+2547{shortcode}")
    tenant = Tenant.objects.create(user=tenant_user, full_name="Tenant X")
    prop = Property.objects.create(landlord=landlord, name="Prop")
    unit = Unit.objects.create(property=prop, label="U1")
    lease = Lease.objects.create(unit=unit, tenant=tenant, rent_amount=10000, billing_day=1, start_date=date.today(), status=LeaseStatus.ACTIVE)
    invoice = Invoice.objects.create(lease=lease, period_start=date.today(), period_end=date.today(), amount_due=10000, due_date=date.today())
    return landlord, credential, invoice


def _build_reseller_with_commission(rate_percent=10):
    payout_account = PayoutAccount.objects.create(phone_number="+254700888888")
    reseller_user = User.objects.create_user(username="reseller-x", role=Role.RESELLER)
    reseller = Reseller.objects.create(user=reseller_user, full_name="Reseller X", payout_account=payout_account)

    landlord, credential, invoice = _build_landlord_with_payment()
    landlord.referred_by = reseller
    landlord.save(update_fields=["referred_by"])
    ReferralCommissionRule.objects.create(reseller=reseller, landlord=landlord, rate_percent=rate_percent)

    payment = Payment.objects.create(invoice=invoice, landlord_credential=credential, amount=10000, mpesa_transaction_id="TXNRS1")
    FeeLedgerEntry.objects.create(
        payment=payment, platform_fee_amount=500, reseller_commission_amount=50, reseller=reseller,
    )
    return reseller


class SweepResellerPayoutsTests(TestCase):
    @patch("partners.tasks.DarajaClient.for_platform")
    def test_creates_sent_disbursement_on_success(self, mock_for_platform):
        mock_client = mock_for_platform.return_value
        mock_client.initiate_b2c_payment.return_value = B2CResult(
            conversation_id="conv-r1", originator_conversation_id="orig-r1", response_description="Accepted"
        )
        reseller = _build_reseller_with_commission()

        from .tasks import sweep_reseller_payouts
        sweep_reseller_payouts()

        disbursement = Disbursement.objects.get(reseller=reseller)
        self.assertEqual(disbursement.status, DisbursementStatus.SENT)
        self.assertEqual(disbursement.mpesa_conversation_id, "conv-r1")
        self.assertEqual(float(disbursement.amount), 50.0)

    @patch("partners.tasks.DarajaClient.for_platform")
    def test_marks_failed_on_daraja_error(self, mock_for_platform):
        mock_client = mock_for_platform.return_value
        mock_client.initiate_b2c_payment.side_effect = DarajaError("boom")
        reseller = _build_reseller_with_commission()

        from .tasks import sweep_reseller_payouts
        sweep_reseller_payouts()

        disbursement = Disbursement.objects.get(reseller=reseller)
        self.assertEqual(disbursement.status, DisbursementStatus.FAILED)

    @patch("partners.tasks.DarajaClient.for_platform")
    def test_no_disbursement_when_nothing_owed(self, mock_for_platform):
        payout_account = PayoutAccount.objects.create(phone_number="+254700777777")
        reseller_user = User.objects.create_user(username="reseller-empty", role=Role.RESELLER)
        Reseller.objects.create(user=reseller_user, full_name="Empty Reseller", payout_account=payout_account)

        from .tasks import sweep_reseller_payouts
        sweep_reseller_payouts()

        self.assertEqual(Disbursement.objects.count(), 0)

    @patch("partners.tasks.DarajaClient.for_platform")
    def test_already_disbursed_entries_excluded_from_next_sweep(self, mock_for_platform):
        mock_client = mock_for_platform.return_value
        mock_client.initiate_b2c_payment.return_value = B2CResult("c1", "o1", "Accepted")
        _build_reseller_with_commission()

        from .tasks import sweep_reseller_payouts
        sweep_reseller_payouts()
        self.assertEqual(Disbursement.objects.count(), 1)

        sweep_reseller_payouts()
        self.assertEqual(Disbursement.objects.count(), 1)


class HandleB2CResultTests(TestCase):
    def _make_sent_disbursement(self, conversation_id="conv-1"):
        reseller = _build_reseller_with_commission()
        return Disbursement.objects.create(
            recipient_type="reseller", reseller=reseller, amount=50,
            status=DisbursementStatus.SENT, mpesa_conversation_id=conversation_id,
        )

    @patch("messaging.tasks.send_whatsapp_reply")
    def test_success_result_confirms_disbursement_and_notifies_recipient(self, mock_send_reply):
        from .tasks import handle_b2c_result

        disbursement = self._make_sent_disbursement("conv-ok")
        disbursement.reseller.user.phone_number = "+254755000001"
        disbursement.reseller.user.save(update_fields=["phone_number"])

        handle_b2c_result({"Result": {"ConversationID": "conv-ok", "ResultCode": 0, "ResultDesc": "Success"}})

        disbursement.refresh_from_db()
        self.assertEqual(disbursement.status, DisbursementStatus.CONFIRMED)
        mock_send_reply.assert_called_once()
        args = mock_send_reply.call_args[0]
        self.assertEqual(args[0], "+254755000001")
        self.assertIn("50", args[1])

    @patch("messaging.tasks.send_whatsapp_reply")
    def test_no_notification_on_failed_result(self, mock_send_reply):
        from .tasks import handle_b2c_result

        self._make_sent_disbursement("conv-fail-notify")
        handle_b2c_result({"Result": {"ConversationID": "conv-fail-notify", "ResultCode": 1, "ResultDesc": "Failed"}})
        mock_send_reply.assert_not_called()

    def test_failure_result_marks_failed(self):
        from .tasks import handle_b2c_result

        disbursement = self._make_sent_disbursement("conv-fail")
        handle_b2c_result({"Result": {"ConversationID": "conv-fail", "ResultCode": 1, "ResultDesc": "Insufficient funds"}})
        disbursement.refresh_from_db()
        self.assertEqual(disbursement.status, DisbursementStatus.FAILED)

    def test_unknown_conversation_id_does_not_crash(self):
        from .tasks import handle_b2c_result

        handle_b2c_result({"Result": {"ConversationID": "conv-unknown", "ResultCode": 0}})
        # No exception raised is the assertion here.

    def test_duplicate_result_is_ignored(self):
        from .tasks import handle_b2c_result

        disbursement = self._make_sent_disbursement("conv-dup")
        handle_b2c_result({"Result": {"ConversationID": "conv-dup", "ResultCode": 0}})
        handle_b2c_result({"Result": {"ConversationID": "conv-dup", "ResultCode": 1}})
        disbursement.refresh_from_db()
        self.assertEqual(disbursement.status, DisbursementStatus.CONFIRMED)


class HandleB2CTimeoutTests(TestCase):
    def test_sent_disbursement_marked_failed_on_timeout(self):
        from .tasks import handle_b2c_timeout

        reseller = _build_reseller_with_commission()
        disbursement = Disbursement.objects.create(
            recipient_type="reseller", reseller=reseller, amount=50,
            status=DisbursementStatus.SENT, mpesa_conversation_id="conv-timeout",
        )
        handle_b2c_timeout({"Result": {"ConversationID": "conv-timeout"}})
        disbursement.refresh_from_db()
        self.assertEqual(disbursement.status, DisbursementStatus.FAILED)

    def test_no_matching_disbursement_does_not_crash(self):
        from .tasks import handle_b2c_timeout

        handle_b2c_timeout({"Result": {"ConversationID": "conv-none"}})


class DisbursementValidationTests(TestCase):
    def test_reseller_type_requires_reseller_and_no_investor(self):
        reseller = _build_reseller_with_commission()
        with self.assertRaises(ValidationError):
            Disbursement(recipient_type=DisbursementRecipientType.RESELLER, amount=100).clean()

    def test_reseller_type_rejects_investor_also_set(self):
        reseller = _build_reseller_with_commission()
        payout_account = PayoutAccount.objects.create(phone_number="+254700666666")
        investor_user = User.objects.create_user(username="investor-conflict", role=Role.INVESTOR)
        investor = Investor.objects.create(user=investor_user, full_name="Investor Y", payout_account=payout_account)

        with self.assertRaises(ValidationError):
            Disbursement(
                recipient_type=DisbursementRecipientType.RESELLER, reseller=reseller, investor=investor, amount=100
            ).clean()

    def test_valid_reseller_disbursement_passes_clean(self):
        reseller = _build_reseller_with_commission()
        Disbursement(recipient_type=DisbursementRecipientType.RESELLER, reseller=reseller, amount=100).clean()


class ReferralCommissionRuleValidationTests(TestCase):
    def _make_reseller_and_landlord(self):
        payout_account = PayoutAccount.objects.create(phone_number="+254700555555")
        reseller_user = User.objects.create_user(username="reseller-dupe", role=Role.RESELLER)
        reseller = Reseller.objects.create(user=reseller_user, full_name="Reseller Dupe", payout_account=payout_account)
        landlord, _credential, _invoice = _build_landlord_with_payment(shortcode="700200")
        return reseller, landlord

    def test_second_active_perpetual_rule_for_same_pair_is_rejected(self):
        reseller, landlord = self._make_reseller_and_landlord()
        ReferralCommissionRule.objects.create(reseller=reseller, landlord=landlord, rate_percent=10)

        duplicate = ReferralCommissionRule(reseller=reseller, landlord=landlord, rate_percent=5)
        with self.assertRaises(ValidationError):
            duplicate.clean()

    def test_new_rule_allowed_once_prior_rule_is_expired(self):
        reseller, landlord = self._make_reseller_and_landlord()
        ReferralCommissionRule.objects.create(
            reseller=reseller, landlord=landlord, rate_percent=10,
            is_perpetual=False, expires_at=timezone.now() - timedelta(days=1),
        )
        newer = ReferralCommissionRule(reseller=reseller, landlord=landlord, rate_percent=5)
        newer.clean()  # should not raise

    def test_editing_the_same_rule_does_not_conflict_with_itself(self):
        reseller, landlord = self._make_reseller_and_landlord()
        rule = ReferralCommissionRule.objects.create(reseller=reseller, landlord=landlord, rate_percent=10)
        rule.rate_percent = 12
        rule.clean()  # should not raise — excludes its own pk


class PartnersDashboardAPITests(APITestCase):
    def setUp(self):
        self.reseller = _build_reseller_with_commission()
        payout_account = PayoutAccount.objects.create(phone_number="+254700444444")
        investor_user = User.objects.create_user(username="investor-dash", role=Role.INVESTOR)
        self.investor = Investor.objects.create(user=investor_user, full_name="Investor Dash", payout_account=payout_account)
        RevenueShareAgreement.objects.create(
            investor=self.investor, basis=RevenueShareBasis.GROSS_FEE_REVENUE, rate_percent=5,
            effective_start=date.today(),
        )
        self.admin = User.objects.create_superuser(username="partners-admin", password="x", role=Role.ADMIN)

    def test_reseller_sees_own_dashboard(self):
        client = APIClient()
        client.force_authenticate(user=self.reseller.user)
        response = client.get("/api/partners/resellers/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.reseller.id))
        self.assertEqual(len(response.data["commission_rules"]), 1)

    def test_non_reseller_gets_404_on_reseller_dashboard(self):
        client = APIClient()
        client.force_authenticate(user=self.investor.user)
        response = client.get("/api/partners/resellers/me/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_investor_sees_own_dashboard(self):
        client = APIClient()
        client.force_authenticate(user=self.investor.user)
        response = client.get("/api/partners/investors/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["agreements"]), 1)

    def test_unauthenticated_dashboard_request_rejected(self):
        response = self.client.get("/api/partners/resellers/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_staff_cannot_list_all_resellers(self):
        client = APIClient()
        client.force_authenticate(user=self.reseller.user)
        response = client.get("/api/partners/resellers/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_list_all_resellers(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        response = client.get("/api/partners/resellers/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in response.data}
        self.assertIn(str(self.reseller.id), ids)

    def test_admin_can_list_all_investors(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        response = client.get("/api/partners/investors/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in response.data}
        self.assertIn(str(self.investor.id), ids)
