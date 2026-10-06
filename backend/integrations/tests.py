# backend/integrations/tests.py

import base64
from datetime import date
from unittest.mock import MagicMock, patch

import requests
from django.test import TestCase, override_settings

from accounts.models import Role, User
from credentials.models import PlatformCredential, PlatformCredentialKey
from landlords.models import Landlord, LandlordDarajaCredential, Organization

from .daraja import DarajaClient, DarajaError, _TOKEN_CACHE
from .resend_client import EmailAttachment, ResendClient, ResendError
from .twilio import TwilioClient
from .whatsapp import WhatsAppClient, WhatsAppError


def _mock_response(json_data, ok=True, status_code=200):
    response = MagicMock()
    response.ok = ok
    response.status_code = status_code
    response.json.return_value = json_data
    return response


class TwilioSignatureTests(TestCase):
    def test_validates_base64_signature_with_query_and_repeated_form_values(self):
        from django.http import QueryDict

        params = QueryDict("Body=world&Body=hello&From=whatsapp%3A%2B1415")

        self.assertTrue(
            TwilioClient.validate_signature(
                "https://example.com/webhooks/twilio/?foo=bar",
                params,
                "o3AySI2+Da6ZGVqGyutQ8KO00Sc=",
                "test-auth-token",
            )
        )

    def test_rejects_signature_for_different_auth_token(self):
        self.assertFalse(
            TwilioClient.validate_signature(
                "https://example.com/webhooks/twilio/",
                {"Body": "hello"},
                "not-a-valid-signature",
                "test-auth-token",
            )
        )


class DarajaClientFactoryTests(TestCase):
    def test_for_landlord_reads_decrypted_fields(self):
        org = Organization.objects.create(name="Org")
        user = User.objects.create_user(username="ll1", role=Role.LANDLORD)
        landlord = Landlord.objects.create(organization=org, user=user, full_name="L")
        credential = LandlordDarajaCredential.objects.create(
            landlord=landlord, shortcode="123456", environment="sandbox",
            consumer_key="ck-value", consumer_secret="cs-value", passkey="pk-value",
            initiator_credential="init-value", security_credential="sec-value",
        )
        client = DarajaClient.for_landlord(credential)
        self.assertEqual(client.consumer_key, "ck-value")
        self.assertEqual(client.consumer_secret, "cs-value")
        self.assertEqual(client.shortcode, "123456")
        self.assertEqual(client.passkey, "pk-value")
        self.assertEqual(client.initiator_name, "init-value")
        self.assertEqual(client.security_credential, "sec-value")

    def test_for_platform_reads_platform_credentials(self):
        PlatformCredential.objects.create(key=PlatformCredentialKey.PLATFORM_DARAJA_CONSUMER_KEY, value="pck")
        PlatformCredential.objects.create(key=PlatformCredentialKey.PLATFORM_DARAJA_CONSUMER_SECRET, value="pcs")
        PlatformCredential.objects.create(key=PlatformCredentialKey.PLATFORM_DARAJA_SHORTCODE, value="174379")
        PlatformCredential.objects.create(key=PlatformCredentialKey.PLATFORM_DARAJA_PASSKEY, value="ppk")

        client = DarajaClient.for_platform()
        self.assertEqual(client.consumer_key, "pck")
        self.assertEqual(client.consumer_secret, "pcs")
        self.assertEqual(client.shortcode, "174379")
        self.assertEqual(client.passkey, "ppk")


class DarajaClientHTTPTests(TestCase):
    def setUp(self):
        _TOKEN_CACHE.clear()
        self.client_obj = DarajaClient(
            consumer_key="ck", consumer_secret="cs", shortcode="174379",
            environment="sandbox", passkey="pk", initiator_name="init", security_credential="sec",
        )

    @patch("integrations.daraja.requests.get")
    def test_get_access_token_uses_basic_auth_and_caches(self, mock_get):
        mock_get.return_value = _mock_response({"access_token": "tok-1", "expires_in": "3599"})

        token1 = self.client_obj._get_access_token()
        token2 = self.client_obj._get_access_token()

        self.assertEqual(token1, "tok-1")
        self.assertEqual(token2, "tok-1")
        mock_get.assert_called_once()
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["auth"], ("ck", "cs"))

    @patch("integrations.daraja.requests.post")
    @patch("integrations.daraja.requests.get")
    @override_settings(PUBLIC_BASE_URL="https://api.example.com")
    def test_initiate_stk_push_builds_correct_payload(self, mock_get, mock_post):
        mock_get.return_value = _mock_response({"access_token": "tok", "expires_in": "3599"})
        mock_post.return_value = _mock_response(
            {"CheckoutRequestID": "ws_CO_1", "MerchantRequestID": "mr_1", "ResponseDescription": "Accepted"}
        )

        result = self.client_obj.initiate_stk_push(
            phone_number="254711000001", amount="500", account_reference="RENTAB12CD34EXTRALONGREF"
        )

        self.assertEqual(result.checkout_request_id, "ws_CO_1")
        self.assertEqual(result.merchant_request_id, "mr_1")

        url, kwargs = mock_post.call_args[0], mock_post.call_args[1]
        self.assertTrue(url[0].endswith("/mpesa/stkpush/v1/processrequest"))
        payload = kwargs["json"]
        self.assertEqual(payload["BusinessShortCode"], "174379")
        self.assertEqual(payload["Amount"], "500")
        self.assertEqual(payload["PartyA"], "254711000001")
        self.assertEqual(payload["PhoneNumber"], "254711000001")
        self.assertEqual(payload["CallBackURL"], "https://api.example.com/webhooks/mpesa/stk/callback/")
        self.assertEqual(len(payload["AccountReference"]), 20)
        decoded = base64.b64decode(payload["Password"]).decode()
        self.assertTrue(decoded.startswith("174379pk"))

    def test_initiate_stk_push_without_passkey_raises(self):
        self.client_obj.passkey = ""
        with self.assertRaises(DarajaError):
            self.client_obj.initiate_stk_push("254711000001", "500", "REF")

    @patch("integrations.daraja.requests.post")
    @patch("integrations.daraja.requests.get")
    @override_settings(PUBLIC_BASE_URL="https://api.example.com")
    def test_initiate_b2c_payment_builds_correct_payload(self, mock_get, mock_post):
        mock_get.return_value = _mock_response({"access_token": "tok", "expires_in": "3599"})
        mock_post.return_value = _mock_response(
            {"ConversationID": "conv-1", "OriginatorConversationID": "orig-1", "ResponseDescription": "Accepted"}
        )

        result = self.client_obj.initiate_b2c_payment(
            phone_number="254711000001", amount="1000", remarks="Payout", occasion="Monthly"
        )

        self.assertEqual(result.conversation_id, "conv-1")
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["InitiatorName"], "init")
        self.assertEqual(payload["SecurityCredential"], "sec")
        self.assertEqual(payload["CommandID"], "BusinessPayment")
        self.assertEqual(payload["PartyA"], "174379")
        self.assertEqual(payload["PartyB"], "254711000001")
        self.assertEqual(payload["ResultURL"], "https://api.example.com/webhooks/mpesa/b2c/result/")
        self.assertEqual(payload["QueueTimeOutURL"], "https://api.example.com/webhooks/mpesa/b2c/timeout/")

    def test_initiate_b2c_payment_without_initiator_creds_raises(self):
        self.client_obj.initiator_name = ""
        with self.assertRaises(DarajaError):
            self.client_obj.initiate_b2c_payment("254711000001", "1000", "Payout")

    @patch("integrations.daraja.requests.post")
    @patch("integrations.daraja.requests.get")
    def test_query_transaction_status_returns_raw_response(self, mock_get, mock_post):
        mock_get.return_value = _mock_response({"access_token": "tok", "expires_in": "3599"})
        mock_post.return_value = _mock_response({"ResponseCode": "0", "ResponseDescription": "Accepted"})

        data = self.client_obj.query_transaction_status("TXN123")
        self.assertEqual(data["ResponseCode"], "0")
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["TransactionID"], "TXN123")
        self.assertEqual(payload["CommandID"], "TransactionStatusQuery")

    @patch("integrations.daraja.requests.post")
    @patch("integrations.daraja.requests.get")
    def test_non_ok_response_raises_daraja_error(self, mock_get, mock_post):
        mock_get.return_value = _mock_response({"access_token": "tok", "expires_in": "3599"})
        mock_post.return_value = _mock_response({"errorMessage": "Bad request"}, ok=False, status_code=400)

        with self.assertRaises(DarajaError):
            self.client_obj.query_transaction_status("TXN123")

    @patch("integrations.daraja.requests.get")
    def test_oauth_http_error_is_wrapped_as_daraja_error(self, mock_get):
        # Regression test: a live smoke test against Safaricom's sandbox
        # with bad credentials surfaced a raw requests.HTTPError from
        # response.raise_for_status() instead of DarajaError, which meant
        # billing/api_views.py's `except DarajaError` never caught it and
        # the API returned an unhandled 500 instead of a clean 502.
        response = _mock_response({"error": "invalid_client"}, ok=False, status_code=401)
        response.raise_for_status.side_effect = requests.HTTPError("401 Client Error", response=response)
        mock_get.return_value = response

        with self.assertRaises(DarajaError):
            self.client_obj._get_access_token()

    @patch("integrations.daraja.requests.get")
    def test_oauth_connection_error_is_wrapped_as_daraja_error(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("DNS resolution failed")

        with self.assertRaises(DarajaError):
            self.client_obj._get_access_token()

    @patch("integrations.daraja.requests.post")
    @patch("integrations.daraja.requests.get")
    def test_post_connection_error_is_wrapped_as_daraja_error(self, mock_get, mock_post):
        mock_get.return_value = _mock_response({"access_token": "tok", "expires_in": "3599"})
        mock_post.side_effect = requests.ConnectionError("connection reset")

        with self.assertRaises(DarajaError):
            self.client_obj.query_transaction_status("TXN123")


class ResendClientTests(TestCase):
    def test_send_email_without_api_key_raises(self):
        client = ResendClient(api_key="", from_email="Dime <noreply@dime.co.ke>")
        with self.assertRaises(ResendError):
            client.send_email(to="tenant@example.com", subject="Hi", html="<p>Hi</p>")

    @patch("integrations.resend_client.requests.post")
    def test_send_email_builds_correct_payload(self, mock_post):
        mock_post.return_value = _mock_response({"id": "email-123"})
        client = ResendClient(api_key="re_key", from_email="Dime <noreply@dime.co.ke>")

        result = client.send_email(to="tenant@example.com", subject="Receipt", html="<p>Paid</p>", text="Paid")

        self.assertEqual(result.id, "email-123")
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["from"], "Dime <noreply@dime.co.ke>")
        self.assertEqual(payload["to"], ["tenant@example.com"])
        self.assertEqual(payload["subject"], "Receipt")
        self.assertEqual(payload["text"], "Paid")
        headers = mock_post.call_args[1]["headers"]
        self.assertEqual(headers["Authorization"], "Bearer re_key")

    @patch("integrations.resend_client.requests.post")
    def test_send_email_with_attachment_base64_encodes_content(self, mock_post):
        mock_post.return_value = _mock_response({"id": "email-456"})
        client = ResendClient(api_key="re_key", from_email="Dime <noreply@dime.co.ke>")

        client.send_email(
            to="tenant@example.com", subject="Receipt", html="<p>Paid</p>",
            attachments=[EmailAttachment(filename="receipt.pdf", content=b"%PDF-1.4 fake")],
        )

        payload = mock_post.call_args[1]["json"]
        attachment = payload["attachments"][0]
        self.assertEqual(attachment["filename"], "receipt.pdf")
        self.assertEqual(base64.b64decode(attachment["content"]), b"%PDF-1.4 fake")

    @patch("integrations.resend_client.requests.post")
    def test_non_ok_response_raises_resend_error(self, mock_post):
        mock_post.return_value = _mock_response({"message": "invalid"}, ok=False, status_code=422)
        client = ResendClient(api_key="re_key", from_email="Dime <noreply@dime.co.ke>")
        with self.assertRaises(ResendError):
            client.send_email(to="tenant@example.com", subject="Hi", html="<p>Hi</p>")

    @patch("integrations.resend_client.requests.post")
    def test_connection_error_wrapped_as_resend_error(self, mock_post):
        mock_post.side_effect = requests.ConnectionError("boom")
        client = ResendClient(api_key="re_key", from_email="Dime <noreply@dime.co.ke>")
        with self.assertRaises(ResendError):
            client.send_email(to="tenant@example.com", subject="Hi", html="<p>Hi</p>")


class WhatsAppClientHTTPTests(TestCase):
    def setUp(self):
        self.client_obj = WhatsAppClient(access_token="tok", phone_number_id="pnid-1")

    def test_send_without_credentials_raises(self):
        client = WhatsAppClient(access_token="", phone_number_id="")
        with self.assertRaises(WhatsAppError):
            client.send_session_message("254711000001", "Hi")

    @patch("integrations.whatsapp.requests.post")
    def test_send_session_message_builds_correct_payload(self, mock_post):
        mock_post.return_value = _mock_response({"messages": [{"id": "wamid.1"}]})
        result = self.client_obj.send_session_message("254711000001", "Your balance is KES 500")

        self.assertEqual(result.message_id, "wamid.1")
        url = mock_post.call_args[0][0]
        self.assertTrue(url.endswith("/pnid-1/messages"))
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["to"], "254711000001")
        self.assertEqual(payload["type"], "text")
        self.assertEqual(payload["text"]["body"], "Your balance is KES 500")
        headers = mock_post.call_args[1]["headers"]
        self.assertEqual(headers["Authorization"], "Bearer tok")

    @patch("integrations.whatsapp.requests.post")
    def test_send_template_message_builds_components_from_variables(self, mock_post):
        mock_post.return_value = _mock_response({"messages": [{"id": "wamid.2"}]})
        result = self.client_obj.send_template_message(
            "254711000001", "otp_code", {"code": "123456"}
        )

        self.assertEqual(result.message_id, "wamid.2")
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["template"]["name"], "otp_code")
        self.assertEqual(payload["template"]["components"][0]["parameters"][0]["text"], "123456")

    @patch("integrations.whatsapp.requests.post")
    def test_non_ok_response_raises_whatsapp_error(self, mock_post):
        mock_post.return_value = _mock_response({"error": "bad"}, ok=False, status_code=400)
        with self.assertRaises(WhatsAppError):
            self.client_obj.send_session_message("254711000001", "Hi")

    @patch("integrations.whatsapp.requests.post")
    def test_connection_error_wrapped_as_whatsapp_error(self, mock_post):
        mock_post.side_effect = requests.ConnectionError("boom")
        with self.assertRaises(WhatsAppError):
            self.client_obj.send_session_message("254711000001", "Hi")

    def test_parse_inbound_webhook_extracts_text_messages(self):
        payload = {
            "entry": [{"changes": [{"value": {"messages": [
                {"id": "wamid.in.1", "from": "254711000001", "type": "text", "text": {"body": "Pay Rent"}},
            ]}}]}]
        }
        messages = self.client_obj.parse_inbound_webhook(payload)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].phone_number, "254711000001")
        self.assertEqual(messages[0].body, "Pay Rent")

    def test_parse_inbound_webhook_extracts_button_reply(self):
        payload = {
            "entry": [{"changes": [{"value": {"messages": [
                {"id": "wamid.in.2", "from": "254711000001", "type": "interactive",
                 "interactive": {"button_reply": {"title": "Report Issue"}}},
            ]}}]}]
        }
        messages = self.client_obj.parse_inbound_webhook(payload)
        self.assertEqual(messages[0].body, "Report Issue")

    def test_parse_inbound_webhook_skips_unrecognized_shape(self):
        payload = {"entry": [{"changes": [{"value": {"messages": [{"id": "x", "from": "254711000001"}]}}]}]}
        messages = self.client_obj.parse_inbound_webhook(payload)
        self.assertEqual(messages, [])

    def test_parse_inbound_webhook_handles_empty_payload(self):
        self.assertEqual(self.client_obj.parse_inbound_webhook({}), [])
