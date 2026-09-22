# backend/messaging/tests.py

import hashlib
import hmac
import json
from datetime import date
from unittest.mock import patch

from django.test import TestCase

from accounts.models import Role, User
from billing.models import Invoice
from caretakers.models import Caretaker, CaretakerAssignment
from credentials.models import PlatformCredential, PlatformCredentialKey
from integrations.whatsapp import WhatsAppError
from landlords.models import Landlord, LandlordDarajaCredential, OnboardingStatus, Organization
from leasing.models import Lease, LeaseStatus, Tenant
from maintenance.models import MaintenanceTicket
from properties.models import Property, Unit

from .models import EmailMessage, MessageDirection, NotificationTemplate, TemplateApprovalStatus, WhatsAppDeliveryStatus, WhatsAppMessage
from .tasks import (
    handle_inbound_whatsapp_message,
    handle_whatsapp_status_update,
    send_email_notification,
    send_rent_reminders,
    send_whatsapp_template,
)


def _build_tenant_chain(shortcode="800100", tenant_phone="+254711900001"):
    org = Organization.objects.create(name="Msg Org")
    landlord_user = User.objects.create_user(username=f"ll-{shortcode}", role=Role.LANDLORD)
    landlord = Landlord.objects.create(organization=org, user=landlord_user, full_name="Landlord M")
    credential = LandlordDarajaCredential.objects.create(
        landlord=landlord, shortcode=shortcode, consumer_key="ck", consumer_secret="cs", passkey="pk",
        status=OnboardingStatus.SANDBOX_TESTING,
    )
    prop = Property.objects.create(landlord=landlord, name="Msg Towers")
    unit = Unit.objects.create(property=prop, label="C1")
    tenant_user = User.objects.create_user(username=f"tenant-{shortcode}", role=Role.TENANT, phone_number=tenant_phone)
    tenant = Tenant.objects.create(user=tenant_user, full_name="Tina Tenant")
    lease = Lease.objects.create(unit=unit, tenant=tenant, rent_amount=12000, billing_day=1, start_date=date.today(), status=LeaseStatus.ACTIVE)
    return landlord, prop, tenant, lease


class BalanceInquiryTests(TestCase):
    @patch("messaging.tasks.WhatsAppClient")
    def test_replies_with_open_invoice_balance(self, mock_whatsapp_cls):
        _, _, tenant, lease = _build_tenant_chain(tenant_phone="+254711900002")
        invoice = Invoice.objects.create(
            lease=lease, period_start=date.today(), period_end=date.today(), amount_due=12000, due_date=date.today()
        )

        handle_inbound_whatsapp_message("+254711900002", "balance")

        reply = WhatsAppMessage.objects.filter(direction=MessageDirection.OUTBOUND, phone_number="+254711900002").latest("created_at")
        self.assertIn("12,000", reply.body)
        self.assertEqual(reply.related_object_id, str(invoice.id))

    @patch("messaging.tasks.WhatsAppClient")
    def test_unknown_tenant_gets_generic_reply(self, mock_whatsapp_cls):
        handle_inbound_whatsapp_message("+254799999999", "balance")
        reply = WhatsAppMessage.objects.filter(direction=MessageDirection.OUTBOUND, phone_number="+254799999999").latest("created_at")
        self.assertIn("couldn't find your tenant record", reply.body)


class TalkToCaretakerTests(TestCase):
    @patch("messaging.tasks.WhatsAppClient")
    def test_replies_with_assigned_caretaker_contact(self, mock_whatsapp_cls):
        _, prop, tenant, _lease = _build_tenant_chain(tenant_phone="+254711900003")
        caretaker_user = User.objects.create_user(username="caretaker-x", role=Role.CARETAKER, phone_number="+254722000111")
        caretaker = Caretaker.objects.create(user=caretaker_user, full_name="Cathy Caretaker")
        CaretakerAssignment.objects.create(caretaker=caretaker, property=prop, effective_start=date.today())

        handle_inbound_whatsapp_message("+254711900003", "caretaker")

        reply = WhatsAppMessage.objects.filter(direction=MessageDirection.OUTBOUND, phone_number="+254711900003").latest("created_at")
        self.assertIn("Cathy Caretaker", reply.body)
        self.assertIn("+254722000111", reply.body)

    @patch("messaging.tasks.WhatsAppClient")
    def test_no_caretaker_assigned_gets_fallback_message(self, mock_whatsapp_cls):
        _build_tenant_chain(tenant_phone="+254711900004")
        handle_inbound_whatsapp_message("+254711900004", "4")
        reply = WhatsAppMessage.objects.filter(direction=MessageDirection.OUTBOUND, phone_number="+254711900004").latest("created_at")
        self.assertIn("No caretaker is assigned", reply.body)


class ReportIssueTests(TestCase):
    @patch("messaging.tasks.WhatsAppClient")
    def test_creates_ticket_with_inline_description(self, mock_whatsapp_cls):
        _, _, tenant, lease = _build_tenant_chain(tenant_phone="+254711900005")

        handle_inbound_whatsapp_message("+254711900005", "Report issue: leaking kitchen tap", "wamid.1")

        ticket = MaintenanceTicket.objects.get(unit=lease.unit)
        self.assertEqual(ticket.description, "leaking kitchen tap")
        self.assertEqual(ticket.tenant_id, tenant.id)
        self.assertEqual(ticket.whatsapp_thread_ref, "wamid.1")

    @patch("messaging.tasks.WhatsAppClient")
    def test_bare_trigger_asks_for_description_without_creating_ticket(self, mock_whatsapp_cls):
        _build_tenant_chain(tenant_phone="+254711900006")
        handle_inbound_whatsapp_message("+254711900006", "report issue")
        self.assertEqual(MaintenanceTicket.objects.count(), 0)
        reply = WhatsAppMessage.objects.filter(direction=MessageDirection.OUTBOUND, phone_number="+254711900006").latest("created_at")
        self.assertIn("describe the issue", reply.body)


class PayRentIntentTests(TestCase):
    @patch("messaging.services.initiate_invoice_payment")
    @patch("messaging.tasks.WhatsAppClient")
    def test_pay_rent_trigger_calls_initiate_payment(self, mock_whatsapp_cls, mock_initiate):
        from billing.models import STKPushRequest

        _, _, tenant, lease = _build_tenant_chain(tenant_phone="+254711900007")
        invoice = Invoice.objects.create(
            lease=lease, period_start=date.today(), period_end=date.today(), amount_due=12000, due_date=date.today()
        )
        mock_initiate.return_value = STKPushRequest(checkout_request_id="ws_CO_MSG1", invoice=invoice)

        handle_inbound_whatsapp_message("+254711900007", "pay rent")

        mock_initiate.assert_called_once()
        reply = WhatsAppMessage.objects.filter(direction=MessageDirection.OUTBOUND, phone_number="+254711900007").latest("created_at")
        self.assertIn("STK Push sent", reply.body)


class UnclassifiedMessageTests(TestCase):
    @patch("messaging.tasks.WhatsAppClient")
    def test_unrecognized_message_gets_menu_fallback_reply(self, mock_whatsapp_cls):
        result = handle_inbound_whatsapp_message("+254711900008", "hello there")
        self.assertEqual(result, {"ok": False, "reason": "unclassified_intent"})
        reply = WhatsAppMessage.objects.filter(direction=MessageDirection.OUTBOUND, phone_number="+254711900008").latest("created_at")
        self.assertIn("Pay Rent", reply.body)


class WhatsAppReplyDeliveryTests(TestCase):
    @patch("messaging.tasks.WhatsAppClient")
    def test_delivery_failure_is_recorded_but_does_not_raise(self, mock_whatsapp_cls):
        mock_whatsapp_cls.default.return_value.send_session_message.side_effect = WhatsAppError("boom")
        handle_inbound_whatsapp_message("+254711900009", "balance")
        reply = WhatsAppMessage.objects.filter(direction=MessageDirection.OUTBOUND, phone_number="+254711900009").latest("created_at")
        self.assertEqual(reply.delivery_status, "failed")


class WhatsAppWebhookSignatureTests(TestCase):
    def setUp(self):
        PlatformCredential.objects.create(key=PlatformCredentialKey.WHATSAPP_APP_SECRET, value="app-secret-123")
        PlatformCredential.objects.create(key=PlatformCredentialKey.WHATSAPP_VERIFY_TOKEN, value="verify-me")

    def _signed_post(self, payload: dict, secret: str = "app-secret-123"):
        body = json.dumps(payload).encode()
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return self.client.post(
            "/webhooks/whatsapp/", data=body, content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=f"sha256={signature}",
        )

    def test_verification_handshake_echoes_challenge(self):
        response = self.client.get(
            "/webhooks/whatsapp/", {"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "12345"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"12345")

    def test_verification_handshake_rejects_wrong_token(self):
        response = self.client.get(
            "/webhooks/whatsapp/", {"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "12345"}
        )
        self.assertEqual(response.status_code, 403)

    def test_valid_signature_is_accepted(self):
        response = self._signed_post({"entry": []})
        self.assertEqual(response.status_code, 200)

    def test_invalid_signature_is_rejected(self):
        response = self._signed_post({"entry": []}, secret="wrong-secret")
        self.assertEqual(response.status_code, 403)

    def test_missing_signature_header_is_rejected(self):
        response = self.client.post("/webhooks/whatsapp/", data=json.dumps({"entry": []}), content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_no_app_secret_configured_fails_closed(self):
        PlatformCredential.objects.filter(key=PlatformCredentialKey.WHATSAPP_APP_SECRET).delete()
        response = self._signed_post({"entry": []})
        self.assertEqual(response.status_code, 403)

    @patch("messaging.webhook_views.handle_inbound_whatsapp_message.delay")
    def test_valid_signature_dispatches_parsed_messages(self, mock_delay):
        payload = {
            "entry": [{"changes": [{"value": {"messages": [
                {"id": "wamid.x", "from": "254711000001", "type": "text", "text": {"body": "Pay Rent"}},
            ]}}]}]
        }
        response = self._signed_post(payload)
        self.assertEqual(response.status_code, 200)
        mock_delay.assert_called_once_with("254711000001", "Pay Rent", "wamid.x")


class SendEmailNotificationTaskTests(TestCase):
    @patch("integrations.resend_client.requests.post")
    def test_successful_send_marks_sent(self, mock_post):
        from unittest.mock import MagicMock

        response = MagicMock()
        response.ok = True
        response.json.return_value = {"id": "email-1"}
        mock_post.return_value = response

        PlatformCredential.objects.create(key=PlatformCredentialKey.RESEND_API_KEY, value="re_key")

        send_email_notification(to_email="tenant@example.com", subject="Hi", html="<p>Hi</p>")

        record = EmailMessage.objects.get(to_email="tenant@example.com")
        self.assertEqual(record.delivery_status, "sent")
        self.assertEqual(record.resend_message_id, "email-1")

    def test_no_recipient_creates_no_record(self):
        send_email_notification(to_email="", subject="Hi", html="<p>Hi</p>")
        self.assertEqual(EmailMessage.objects.count(), 0)

    @patch("integrations.resend_client.requests.post")
    def test_send_failure_marks_failed(self, mock_post):
        from unittest.mock import MagicMock

        response = MagicMock()
        response.ok = False
        response.status_code = 422
        response.json.return_value = {"message": "invalid"}
        mock_post.return_value = response

        PlatformCredential.objects.create(key=PlatformCredentialKey.RESEND_API_KEY, value="re_key")

        send_email_notification(to_email="tenant@example.com", subject="Hi", html="<p>Hi</p>")

        record = EmailMessage.objects.get(to_email="tenant@example.com")
        self.assertEqual(record.delivery_status, "failed")


class PhoneNumberNormalizationTests(TestCase):
    """Meta's webhook sends bare-digit MSISDNs ("254711...", no "+"), but
    User.phone_number is stored E.164 ("+254711..."). Before
    accounts.phone.normalize_msisdn was wired into
    messaging.services.find_tenant_by_phone, an inbound message shaped
    exactly like what Meta actually sends would never match a real
    tenant."""

    @patch("messaging.tasks.WhatsAppClient")
    def test_bare_digit_phone_number_matches_e164_stored_tenant(self, mock_whatsapp_cls):
        _, _, tenant, lease = _build_tenant_chain(tenant_phone="+254711900050")
        Invoice.objects.create(
            lease=lease, period_start=date.today(), period_end=date.today(), amount_due=12000, due_date=date.today()
        )

        # Simulates the RAW shape a real Meta webhook delivers — bare
        # digits, exactly as test_valid_signature_dispatches_parsed_messages
        # (WhatsAppWebhookSignatureTests) confirms is what actually gets
        # dispatched to this task.
        result = handle_inbound_whatsapp_message("254711900050", "balance")

        self.assertTrue(result.get("ok"))
        reply = WhatsAppMessage.objects.filter(direction=MessageDirection.OUTBOUND, phone_number="254711900050").latest("created_at")
        self.assertIn("12,000", reply.body)


class WhatsAppStatusUpdateTests(TestCase):
    def test_updates_delivery_status_by_meta_message_id(self):
        message = WhatsAppMessage.objects.create(
            direction=MessageDirection.OUTBOUND, phone_number="+254711900060", body="hi",
            meta_message_id="wamid.abc123", delivery_status=WhatsAppDeliveryStatus.SENT,
        )
        handle_whatsapp_status_update("wamid.abc123", "delivered")
        message.refresh_from_db()
        self.assertEqual(message.delivery_status, WhatsAppDeliveryStatus.DELIVERED)

    def test_unrecognized_status_value_is_ignored(self):
        message = WhatsAppMessage.objects.create(
            direction=MessageDirection.OUTBOUND, phone_number="+254711900061", body="hi",
            meta_message_id="wamid.def456", delivery_status=WhatsAppDeliveryStatus.SENT,
        )
        handle_whatsapp_status_update("wamid.def456", "some_unknown_status")
        message.refresh_from_db()
        self.assertEqual(message.delivery_status, WhatsAppDeliveryStatus.SENT)

    def test_no_matching_message_does_not_crash(self):
        handle_whatsapp_status_update("wamid.doesnotexist", "read")

    @patch("messaging.webhook_views.handle_whatsapp_status_update.delay")
    @patch("messaging.webhook_views.handle_inbound_whatsapp_message.delay")
    def test_webhook_dispatches_status_updates(self, mock_message_delay, mock_status_delay):
        from credentials.models import PlatformCredential, PlatformCredentialKey

        PlatformCredential.objects.create(key=PlatformCredentialKey.WHATSAPP_APP_SECRET, value="app-secret-456")
        payload = {
            "entry": [{"changes": [{"value": {"statuses": [
                {"id": "wamid.status1", "status": "delivered", "recipient_id": "254711000001"},
            ]}}]}]
        }
        body = json.dumps(payload).encode()
        signature = hmac.new(b"app-secret-456", body, hashlib.sha256).hexdigest()
        response = self.client.post(
            "/webhooks/whatsapp/", data=body, content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=f"sha256={signature}",
        )
        self.assertEqual(response.status_code, 200)
        mock_status_delay.assert_called_once_with("wamid.status1", "delivered")
        mock_message_delay.assert_not_called()


class SendWhatsAppTemplateTests(TestCase):
    @patch("messaging.tasks.WhatsAppClient")
    def test_sends_approved_template_and_sets_template_used(self, mock_whatsapp_cls):
        from integrations.whatsapp import SendMessageResult

        mock_whatsapp_cls.default.return_value.send_template_message.return_value = SendMessageResult(message_id="wamid.tpl1")
        template = NotificationTemplate.objects.create(
            name="rent_reminder", body="Hi {{tenant_name}}, KES {{amount_due}} is due {{due_date}}.",
            approval_status=TemplateApprovalStatus.APPROVED,
        )

        message = send_whatsapp_template(
            "+254711900070", "rent_reminder",
            {"tenant_name": "Tom", "amount_due": "5000", "due_date": "2026-01-01"},
        )

        self.assertEqual(message.template_used_id, template.id)
        self.assertEqual(message.delivery_status, WhatsAppDeliveryStatus.SENT)
        self.assertEqual(message.meta_message_id, "wamid.tpl1")
        self.assertIn("Tom", message.body)
        self.assertIn("5000", message.body)

    def test_raises_when_no_approved_template_exists(self):
        from .services import TemplateNotApprovedError

        NotificationTemplate.objects.create(
            name="rent_reminder", body="draft body", approval_status=TemplateApprovalStatus.DRAFT
        )
        with self.assertRaises(TemplateNotApprovedError):
            send_whatsapp_template("+254711900071", "rent_reminder", {})

    @patch("messaging.tasks.WhatsAppClient")
    def test_picks_latest_approved_version(self, mock_whatsapp_cls):
        from integrations.whatsapp import SendMessageResult

        mock_whatsapp_cls.default.return_value.send_template_message.return_value = SendMessageResult(message_id="wamid.tpl2")
        NotificationTemplate.objects.create(
            name="rent_reminder", version=1, body="old", approval_status=TemplateApprovalStatus.APPROVED
        )
        newer = NotificationTemplate.objects.create(
            name="rent_reminder", version=2, body="new {{tenant_name}}", approval_status=TemplateApprovalStatus.APPROVED
        )

        message = send_whatsapp_template("+254711900072", "rent_reminder", {"tenant_name": "Tom"})
        self.assertEqual(message.template_used_id, newer.id)


class SendRentRemindersTests(TestCase):
    @patch("messaging.tasks.WhatsAppClient")
    def test_sends_reminder_for_due_soon_invoice(self, mock_whatsapp_cls):
        from integrations.whatsapp import SendMessageResult

        mock_whatsapp_cls.default.return_value.send_template_message.return_value = SendMessageResult(message_id="wamid.rr1")
        NotificationTemplate.objects.create(
            name="rent_reminder", body="Hi {{tenant_name}}", approval_status=TemplateApprovalStatus.APPROVED
        )
        _, _, tenant, lease = _build_tenant_chain(tenant_phone="+254711900080")
        from datetime import timedelta
        invoice = Invoice.objects.create(
            lease=lease, period_start=date.today(), period_end=date.today(),
            amount_due=10000, due_date=date.today() + timedelta(days=2),
        )

        sent = send_rent_reminders(days_before_due=3)

        self.assertEqual(sent, 1)
        self.assertTrue(
            WhatsAppMessage.objects.filter(related_object_type="Invoice", related_object_id=str(invoice.id)).exists()
        )

    @patch("messaging.tasks.WhatsAppClient")
    def test_does_not_send_duplicate_reminder_same_day(self, mock_whatsapp_cls):
        from integrations.whatsapp import SendMessageResult

        mock_whatsapp_cls.default.return_value.send_template_message.return_value = SendMessageResult(message_id="wamid.rr2")
        NotificationTemplate.objects.create(
            name="rent_reminder", body="Hi {{tenant_name}}", approval_status=TemplateApprovalStatus.APPROVED
        )
        _, _, tenant, lease = _build_tenant_chain(tenant_phone="+254711900081")
        from datetime import timedelta
        invoice = Invoice.objects.create(
            lease=lease, period_start=date.today(), period_end=date.today(),
            amount_due=10000, due_date=date.today() + timedelta(days=1),
        )

        first = send_rent_reminders(days_before_due=3)
        second = send_rent_reminders(days_before_due=3)

        self.assertEqual(first, 1)
        self.assertEqual(second, 0)

    def test_skips_gracefully_when_no_approved_template(self):
        _, _, tenant, lease = _build_tenant_chain(tenant_phone="+254711900082")
        from datetime import timedelta
        Invoice.objects.create(
            lease=lease, period_start=date.today(), period_end=date.today(),
            amount_due=10000, due_date=date.today() + timedelta(days=1),
        )
        sent = send_rent_reminders(days_before_due=3)
        self.assertEqual(sent, 0)
