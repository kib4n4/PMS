# backend/partners/tests.py

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from accounts.models import Role, User
from billing.models import FeeLedgerEntry, Invoice, Payment
from integrations.daraja import B2CResult, DarajaError
from landlords.models import Landlord, LandlordDarajaCredential, Organization
from leasing.models import Lease, LeaseStatus, Tenant
from properties.models import Property, Unit

from .models import Disbursement, DisbursementStatus, PayoutAccount, ReferralCommissionRule, Reseller


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
