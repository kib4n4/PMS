# backend/api_auth/tests.py

from datetime import date
from io import StringIO

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Role, User
from accounts.serializers import RoleTokenObtainPairSerializer
from billing.models import Invoice
from landlords.models import Landlord, Organization
from leasing.models import Lease, LeaseStatus, Tenant
from properties.models import Property, Unit

from .models import PlatformApiClient, Scope
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


class ScopeValidationTests(TestCase):
    def test_generate_rejects_unknown_scope(self):
        with self.assertRaises(ValidationError):
            PlatformApiClient.generate(name="Bad Scope", scopes=["not:a:real:scope"])

    def test_clean_rejects_unknown_scope_on_existing_client(self):
        client, _ = PlatformApiClient.generate(name="Acme", scopes=[Scope.INVOICES_READ])
        client.scopes = ["invoices:delete_everything"]
        with self.assertRaises(ValidationError):
            client.clean()

    def test_generate_accepts_registered_scopes(self):
        client, _ = PlatformApiClient.generate(name="Acme", scopes=[Scope.INVOICES_READ, Scope.PAYMENTS_READ])
        self.assertEqual(client.scopes, ["invoices:read", "payments:read"])


class RotateApiClientSecretTests(TestCase):
    def test_rotate_secret_invalidates_old_one(self):
        client, old_secret = PlatformApiClient.generate(name="Acme", scopes=["invoices:read"])
        new_secret = client.rotate_secret()

        self.assertNotEqual(new_secret, old_secret)
        self.assertFalse(client.verify_secret(old_secret))
        self.assertTrue(client.verify_secret(new_secret))
        # client_id/scopes/landlord untouched by rotation.
        self.assertEqual(PlatformApiClient.objects.get(pk=client.pk).scopes, ["invoices:read"])

    def test_rotate_api_client_secret_command(self):
        client, old_secret = PlatformApiClient.generate(name="CLI Rotate", scopes=["invoices:read"])
        out = StringIO()
        call_command("rotate_api_client_secret", "--client-id", client.client_id, stdout=out)

        client.refresh_from_db()
        self.assertFalse(client.verify_secret(old_secret))
        self.assertIn("client_secret:", out.getvalue())

    def test_rotate_unknown_client_id_errors(self):
        with self.assertRaises(CommandError):
            call_command("rotate_api_client_secret", "--client-id", "pms_doesnotexist")


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-token-endpoint-throttle",
        }
    }
)
class TokenEndpointThrottleTests(APITestCase):
    """POST /api/oauth/token/ is a credential-guessing target with no
    other rate limit in front of it — see api_views.TokenEndpointThrottle.

    Runs against its own dedicated cache LOCATION (not the shared
    "default" every other test also reads/writes) — the request-count
    history this throttle keeps is wall-clock-timestamped, so sharing a
    cache backend with unrelated tests makes this assertion's outcome
    depend on full-suite run order/timing rather than just this test.
    """

    def setUp(self):
        cache.clear()
        self.client_obj, self.secret = PlatformApiClient.generate(name="Acme", scopes=["invoices:read"])

    def tearDown(self):
        cache.clear()

    def test_throttles_after_configured_rate(self):
        from django.conf import settings

        limit = int(settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["oauth_token"].split("/")[0])
        for _ in range(limit):
            response = self.client.post(
                "/api/oauth/token/", {"client_id": self.client_obj.client_id, "client_secret": "wrong"}, format="json"
            )
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        throttled = self.client.post(
            "/api/oauth/token/", {"client_id": self.client_obj.client_id, "client_secret": self.secret}, format="json"
        )
        self.assertEqual(throttled.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


# ---------------------------------------------------------------------------
# Extended external read API: invoice context, tickets, disbursements, leases
# ---------------------------------------------------------------------------

from datetime import timedelta  # noqa: E402

from django.utils import timezone  # noqa: E402

from maintenance.models import MaintenanceTicket, TicketStatus  # noqa: E402
from partners.models import (  # noqa: E402
    Disbursement,
    DisbursementRecipientType,
    DisbursementStatus,
    PayoutAccount,
    Reseller,
)


def _external_token(scopes, landlord=None):
    client_obj, _ = PlatformApiClient.generate(name="Ext Reader", scopes=scopes, landlord=landlord)
    return issue_client_credentials_token(client_obj)


class _ExternalReadTestCase(APITestCase):
    def setUp(self):
        self.landlord, self.invoice = _build_landlord_with_invoice("Mine")
        self.other_landlord, self.other_invoice = _build_landlord_with_invoice("Theirs")
        # Creating a RESOLVED ticket fires the resolution WhatsApp task, which
        # fails without a token and sets the provider-backoff cache key; left
        # behind, that key breaks unrelated messaging tests that run later.
        self.addCleanup(cache.clear)

    def _get(self, path, token):
        return self.client.get(path, HTTP_AUTHORIZATION=f"Bearer {token}")


class ExternalInvoiceContextTests(_ExternalReadTestCase):
    def test_invoice_rows_carry_unit_property_tenant_and_days_overdue(self):
        self.invoice.due_date = timezone.localdate() - timedelta(days=10)
        self.invoice.save(update_fields=["due_date"])
        token = _external_token(["invoices:read"], self.landlord)

        row = self._get("/api/external/invoices/", token).data[0]

        self.assertEqual(row["unit_label"], "E1")
        self.assertEqual(row["property_name"], "Ext Towers")
        self.assertEqual(row["tenant_name"], "Ext Tenant")
        self.assertEqual(row["days_overdue"], 10)

    def test_invoice_not_yet_due_has_zero_days_overdue(self):
        self.invoice.due_date = timezone.localdate() + timedelta(days=3)
        self.invoice.save(update_fields=["due_date"])
        token = _external_token(["invoices:read"], self.landlord)

        self.assertEqual(self._get("/api/external/invoices/", token).data[0]["days_overdue"], 0)

    def test_paid_invoice_has_zero_days_overdue(self):
        self.invoice.due_date = timezone.localdate() - timedelta(days=10)
        self.invoice.status = "paid"
        self.invoice.save(update_fields=["due_date", "status"])
        token = _external_token(["invoices:read"], self.landlord)

        self.assertEqual(self._get("/api/external/invoices/", token).data[0]["days_overdue"], 0)

    def test_invoice_rows_never_expose_a_phone_number(self):
        token = _external_token(["invoices:read"], self.landlord)

        row = self._get("/api/external/invoices/", token).data[0]

        self.assertNotIn("phone_number", row)
        self.assertNotIn("tenant_phone", row)


def _ticket_for(invoice, description, status_=TicketStatus.OPEN, age_hours=0):
    ticket = MaintenanceTicket.objects.create(
        unit=invoice.lease.unit, tenant=invoice.lease.tenant, description=description, status=status_
    )
    if age_hours:
        MaintenanceTicket.objects.filter(pk=ticket.pk).update(created_at=timezone.now() - timedelta(hours=age_hours))
    return ticket


class ExternalTicketListViewTests(_ExternalReadTestCase):
    def test_scoped_client_sees_only_its_landlords_tickets(self):
        mine = _ticket_for(self.invoice, "Leaking tap")
        _ticket_for(self.other_invoice, "Broken door")
        token = _external_token(["tickets:read"], self.landlord)

        response = self._get("/api/external/tickets/", token)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual({row["id"] for row in response.data}, {str(mine.id)})

    def test_ticket_row_has_unit_age_and_no_tenant_contact_details(self):
        _ticket_for(self.invoice, "Leaking tap", age_hours=50)
        token = _external_token(["tickets:read"], self.landlord)

        row = self._get("/api/external/tickets/", token).data[0]

        self.assertEqual(
            set(row),
            {"id", "unit_label", "category", "description", "status", "assigned_caretaker", "created_at", "resolved_at", "age_hours"},
        )
        self.assertEqual(row["unit_label"], "E1")
        self.assertIsNone(row["assigned_caretaker"])
        self.assertAlmostEqual(row["age_hours"], 50, delta=1)

    def test_status_filter_narrows_the_list(self):
        open_ticket = _ticket_for(self.invoice, "Open one")
        _ticket_for(self.invoice, "Done one", status_=TicketStatus.RESOLVED)
        token = _external_token(["tickets:read"], self.landlord)

        response = self._get("/api/external/tickets/?status=open", token)

        self.assertEqual({row["id"] for row in response.data}, {str(open_ticket.id)})

    def test_oldest_ticket_comes_first(self):
        newer = _ticket_for(self.invoice, "Newer", age_hours=2)
        older = _ticket_for(self.invoice, "Older", age_hours=90)
        token = _external_token(["tickets:read"], self.landlord)

        ids = [row["id"] for row in self._get("/api/external/tickets/", token).data]

        self.assertEqual(ids, [str(older.id), str(newer.id)])

    def test_platform_wide_client_gets_empty_list(self):
        _ticket_for(self.invoice, "Leaking tap")
        token = _external_token(["tickets:read"], None)

        self.assertEqual(self._get("/api/external/tickets/", token).data, [])

    def test_client_without_scope_is_forbidden(self):
        token = _external_token(["invoices:read"], self.landlord)

        self.assertEqual(self._get("/api/external/tickets/", token).status_code, status.HTTP_403_FORBIDDEN)


def _disbursement(status_=DisbursementStatus.PENDING, amount=500):
    account = PayoutAccount.objects.create(phone_number="+254700111222")
    user = User.objects.create_user(username=f"reseller-{Reseller.objects.count()}", role=Role.RESELLER)
    reseller = Reseller.objects.create(user=user, full_name="Rita Reseller", payout_account=account)
    return Disbursement.objects.create(
        recipient_type=DisbursementRecipientType.RESELLER, reseller=reseller, amount=amount, status=status_
    )


class ExternalDisbursementListViewTests(_ExternalReadTestCase):
    """Payouts are platform-funded and never target a landlord, so unlike the
    other external endpoints this one is platform-wide only: a landlord-bound
    client must not see reseller commissions."""

    def test_platform_wide_client_sees_all_disbursements(self):
        one = _disbursement()
        two = _disbursement(status_=DisbursementStatus.FAILED, amount=900)
        token = _external_token(["disbursements:read"], None)

        response = self._get("/api/external/disbursements/", token)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual({row["id"] for row in response.data}, {str(one.id), str(two.id)})

    def test_landlord_bound_client_gets_empty_list(self):
        _disbursement()
        token = _external_token(["disbursements:read"], self.landlord)

        self.assertEqual(self._get("/api/external/disbursements/", token).data, [])

    def test_row_shape_has_no_recipient_contact_details(self):
        _disbursement()
        token = _external_token(["disbursements:read"], None)

        row = self._get("/api/external/disbursements/", token).data[0]

        self.assertEqual(set(row), {"id", "recipient_type", "recipient_name", "amount", "status", "created_at"})
        self.assertEqual(row["recipient_name"], "Rita Reseller")

    def test_status_filter_narrows_the_list(self):
        _disbursement()
        failed = _disbursement(status_=DisbursementStatus.FAILED)
        token = _external_token(["disbursements:read"], None)

        response = self._get("/api/external/disbursements/?status=failed", token)

        self.assertEqual({row["id"] for row in response.data}, {str(failed.id)})

    def test_client_without_scope_is_forbidden(self):
        token = _external_token(["invoices:read"], None)

        self.assertEqual(self._get("/api/external/disbursements/", token).status_code, status.HTTP_403_FORBIDDEN)


class ExternalLeaseListViewTests(_ExternalReadTestCase):
    def _set_end(self, invoice, days):
        lease = invoice.lease
        lease.end_date = None if days is None else timezone.localdate() + timedelta(days=days)
        lease.save(update_fields=["end_date"])

    def test_scoped_client_sees_only_its_landlords_leases(self):
        token = _external_token(["leases:read"], self.landlord)

        response = self._get("/api/external/leases/", token)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual({row["id"] for row in response.data}, {str(self.invoice.lease_id)})

    def test_row_carries_days_to_end_and_no_tenant_contact_details(self):
        self._set_end(self.invoice, 45)
        token = _external_token(["leases:read"], self.landlord)

        row = self._get("/api/external/leases/", token).data[0]

        self.assertEqual(
            set(row), {"id", "unit_label", "tenant_name", "status", "rent_amount", "end_date", "days_to_end"}
        )
        self.assertEqual(row["days_to_end"], 45)
        self.assertEqual(row["tenant_name"], "Ext Tenant")

    def test_open_ended_lease_has_null_days_to_end(self):
        self._set_end(self.invoice, None)
        token = _external_token(["leases:read"], self.landlord)

        self.assertIsNone(self._get("/api/external/leases/", token).data[0]["days_to_end"])

    def test_ending_within_keeps_only_leases_ending_inside_the_window(self):
        self._set_end(self.invoice, 45)
        _, far_invoice = _build_landlord_with_invoice("Far")
        far_invoice.lease.unit.property.landlord = self.landlord
        far_invoice.lease.unit.property.save()
        self._set_end(far_invoice, 200)
        token = _external_token(["leases:read"], self.landlord)

        response = self._get("/api/external/leases/?ending_within=60", token)

        self.assertEqual({row["id"] for row in response.data}, {str(self.invoice.lease_id)})

    def test_ending_within_excludes_open_ended_and_already_ended_leases(self):
        self._set_end(self.invoice, None)
        token = _external_token(["leases:read"], self.landlord)
        self.assertEqual(self._get("/api/external/leases/?ending_within=60", token).data, [])

        self._set_end(self.invoice, -5)
        self.assertEqual(self._get("/api/external/leases/?ending_within=60", token).data, [])

    def test_ending_within_excludes_terminated_leases(self):
        self._set_end(self.invoice, 10)
        self.invoice.lease.status = LeaseStatus.TERMINATED
        self.invoice.lease.save(update_fields=["status"])
        token = _external_token(["leases:read"], self.landlord)

        self.assertEqual(self._get("/api/external/leases/?ending_within=60", token).data, [])

    def test_non_numeric_ending_within_is_a_400(self):
        token = _external_token(["leases:read"], self.landlord)

        self.assertEqual(
            self._get("/api/external/leases/?ending_within=soon", token).status_code, status.HTTP_400_BAD_REQUEST
        )

    def test_platform_wide_client_gets_empty_list(self):
        token = _external_token(["leases:read"], None)

        self.assertEqual(self._get("/api/external/leases/", token).data, [])

    def test_client_without_scope_is_forbidden(self):
        token = _external_token(["invoices:read"], self.landlord)

        self.assertEqual(self._get("/api/external/leases/", token).status_code, status.HTTP_403_FORBIDDEN)


class NewScopeRegistryTests(TestCase):
    def test_new_scopes_are_grantable(self):
        client_obj, _ = PlatformApiClient.generate(
            name="All", scopes=["tickets:read", "disbursements:read", "leases:read"]
        )
        for scope in ("tickets:read", "disbursements:read", "leases:read"):
            self.assertTrue(client_obj.has_scope(scope))
