# backend/api_auth/tests.py

from datetime import date
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Role, User
from accounts.serializers import RoleTokenObtainPairSerializer
from billing.models import Invoice
from landlords.models import Landlord, Organization
from leasing.models import Lease, LeaseStatus, Tenant
from properties.models import Property, Unit

from .models import PlatformApiClient
from .tokens import issue_client_credentials_token


def _build_landlord_with_invoice(name="Ext Landlord"):
    org = Organization.objects.create(name="Ext Org")
    user = User.objects.create_user(username=f"ll-ext-{name}", role=Role.LANDLORD)
    landlord = Landlord.objects.create(organization=org, user=user, full_name=name)
    prop = Property.objects.create(landlord=landlord, name="Ext Towers")
    unit = Unit.objects.create(property=prop, label="E1")
    tenant_user = User.objects.create_user(username=f"tenant-ext-{name}", role=Role.TENANT, phone_number=f"+25470{abs(hash(name)) % 1000000:06d}")
    tenant = Tenant.objects.create(user=tenant_user, full_name="Ext Tenant")
    lease = Lease.objects.create(unit=unit, tenant=tenant, rent_amount=10000, billing_day=1, start_date=date.today(), status=LeaseStatus.ACTIVE)
    invoice = Invoice.objects.create(lease=lease, period_start=date.today(), period_end=date.today(), amount_due=10000, due_date=date.today())
    return landlord, invoice


class PlatformApiClientModelTests(TestCase):
    def test_generate_returns_plaintext_secret_once(self):
        client, secret = PlatformApiClient.generate(name="Acme", scopes=["invoices:read"])
        self.assertTrue(client.client_id.startswith("pms_"))
        self.assertNotEqual(client.client_secret_hash, secret)
        self.assertTrue(client.verify_secret(secret))
        self.assertFalse(client.verify_secret("wrong-secret"))

    def test_has_scope(self):
        client, _ = PlatformApiClient.generate(name="Acme", scopes=["invoices:read", "payments:read"])
        self.assertTrue(client.has_scope("invoices:read"))
        self.assertFalse(client.has_scope("payments:write"))


class TokenViewTests(APITestCase):
    def setUp(self):
        self.client_obj, self.secret = PlatformApiClient.generate(name="Acme", scopes=["invoices:read"])

    def test_valid_credentials_issue_token(self):
        response = self.client.post(
            "/api/oauth/token/", {"client_id": self.client_obj.client_id, "client_secret": self.secret}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.data)
        self.assertEqual(response.data["token_type"], "Bearer")
        self.assertEqual(response.data["scope"], "invoices:read")

        self.client_obj.refresh_from_db()
        self.assertIsNotNone(self.client_obj.last_used_at)

    def test_wrong_secret_rejected(self):
        response = self.client.post(
            "/api/oauth/token/", {"client_id": self.client_obj.client_id, "client_secret": "wrong"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unknown_client_id_rejected(self):
        response = self.client.post(
            "/api/oauth/token/", {"client_id": "pms_doesnotexist", "client_secret": "whatever"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_client_rejected(self):
        self.client_obj.is_active = False
        self.client_obj.save(update_fields=["is_active"])
        response = self.client.post(
            "/api/oauth/token/", {"client_id": self.client_obj.client_id, "client_secret": self.secret}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_fields_rejected(self):
        response = self.client.post("/api/oauth/token/", {"client_id": self.client_obj.client_id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ExternalInvoiceListViewTests(APITestCase):
    def setUp(self):
        self.landlord, self.invoice = _build_landlord_with_invoice("Scoped")
        self.other_landlord, self.other_invoice = _build_landlord_with_invoice("Other")

    def _bearer(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_scoped_client_sees_only_its_landlord_invoices(self):
        client_obj, _ = PlatformApiClient.generate(name="Acme", scopes=["invoices:read"], landlord=self.landlord)
        token = issue_client_credentials_token(client_obj)

        response = self.client.get("/api/external/invoices/", **self._bearer(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in response.data}
        self.assertEqual(ids, {str(self.invoice.id)})

    def test_platform_wide_client_gets_empty_list(self):
        client_obj, _ = PlatformApiClient.generate(name="Platform Tool", scopes=["invoices:read"], landlord=None)
        token = issue_client_credentials_token(client_obj)

        response = self.client.get("/api/external/invoices/", **self._bearer(token))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_client_without_scope_is_forbidden(self):
        client_obj, _ = PlatformApiClient.generate(name="No Scope", scopes=["payments:read"], landlord=self.landlord)
        token = issue_client_credentials_token(client_obj)

        response = self.client.get("/api/external/invoices/", **self._bearer(token))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_no_token_is_unauthorized(self):
        response = self.client.get("/api/external/invoices/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_client_token_rejected(self):
        client_obj, _ = PlatformApiClient.generate(name="Deactivated", scopes=["invoices:read"], landlord=self.landlord)
        token = issue_client_credentials_token(client_obj)
        client_obj.is_active = False
        client_obj.save(update_fields=["is_active"])

        response = self.client.get("/api/external/invoices/", **self._bearer(token))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_malformed_token_is_unauthorized(self):
        response = self.client.get("/api/external/invoices/", **self._bearer("not-a-real-token"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TokenTypeIsolationTests(APITestCase):
    """The two token types must never substitute for each other."""

    def setUp(self):
        self.landlord, self.invoice = _build_landlord_with_invoice("Isolation")
        self.user = User.objects.create_user(username="isolation-user", role=Role.LANDLORD, password="x")

    def test_user_jwt_cannot_access_external_endpoint(self):
        user_token = str(RoleTokenObtainPairSerializer.get_token(self.user).access_token)
        response = self.client.get("/api/external/invoices/", HTTP_AUTHORIZATION=f"Bearer {user_token}")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_client_credentials_token_cannot_access_user_endpoint(self):
        client_obj, _ = PlatformApiClient.generate(name="Isolation Client", scopes=["invoices:read"], landlord=self.landlord)
        client_token = issue_client_credentials_token(client_obj)
        response = self.client.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {client_token}")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_client_credentials_token_has_no_user_id_claim(self):
        client_obj, _ = PlatformApiClient.generate(name="Claims Client", scopes=["invoices:read"])
        token_str = issue_client_credentials_token(client_obj)
        decoded = AccessToken(token_str)
        self.assertNotIn("user_id", decoded.payload)
        self.assertEqual(decoded["grant_type"], "client_credentials")


class CreateApiClientCommandTests(TestCase):
    def test_command_creates_client_and_prints_credentials(self):
        out = StringIO()
        call_command("create_api_client", "--name", "CLI Test", "--scopes", "invoices:read,payments:read", stdout=out)

        client = PlatformApiClient.objects.get(name="CLI Test")
        self.assertEqual(client.scopes, ["invoices:read", "payments:read"])
        output = out.getvalue()
        self.assertIn(client.client_id, output)
        self.assertIn("client_secret:", output)

    def test_command_with_landlord_id_scopes_client(self):
        landlord, _ = _build_landlord_with_invoice("CLI Scoped")
        out = StringIO()
        call_command("create_api_client", "--name", "CLI Scoped Client", "--landlord-id", str(landlord.id), stdout=out)

        client = PlatformApiClient.objects.get(name="CLI Scoped Client")
        self.assertEqual(client.landlord_id, landlord.id)
