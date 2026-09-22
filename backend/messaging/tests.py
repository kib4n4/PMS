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

from .models import EmailMessage, MessageDirection, WhatsAppMessage
from .tasks import handle_inbound_whatsapp_message, send_email_notification


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
    def test_unrecognized_message_is_logged_not_replied_to(self):
        result = handle_inbound_whatsapp_message("+254711900008", "hello there")
        self.assertEqual(result, {"ok": False, "reason": "unclassified_intent"})
        self.assertFalse(WhatsAppMessage.objects.filter(direction=MessageDirection.OUTBOUND).exists())


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
