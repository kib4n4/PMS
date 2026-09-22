# backend/accounts/tests.py

from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from .models import OTPRequest, Role, User
from .permissions import IsAdmin, IsLandlord, IsSelfOrAdmin, IsSuperAdmin, IsTenant


def _make_user(**kwargs):
    kwargs.setdefault("password", "correct-horse-battery-staple")
    return User.objects.create_user(**kwargs)


class PermissionsModuleImportTests(TestCase):
    """Regression test for the stray-text bug that previously made this
    module raise NameError at import time and take the whole
    /api/landlord/tenants/ route down with it."""

    def test_permission_classes_are_importable_and_distinct(self):
        classes = {IsLandlord, IsTenant, IsAdmin, IsSuperAdmin, IsSelfOrAdmin}
        self.assertEqual(len(classes), 5)


class RolePermissionUnitTests(TestCase):
    def test_is_admin_requires_admin_role(self):
        admin_user = _make_user(username="staff1", role=Role.ADMIN)
        landlord_user = _make_user(username="landlord1", role=Role.LANDLORD)
        request = SimpleNamespace(user=admin_user)
        self.assertTrue(IsAdmin().has_permission(request, None))
        request.user = landlord_user
        self.assertFalse(IsAdmin().has_permission(request, None))

    def test_is_super_admin_requires_is_superuser_flag(self):
        admin_user = _make_user(username="staff2", role=Role.ADMIN)
        super_user = _make_user(username="root", role=Role.ADMIN, is_superuser=True, is_staff=True)
        request = SimpleNamespace(user=admin_user)
        self.assertFalse(IsSuperAdmin().has_permission(request, None))
        request.user = super_user
        self.assertTrue(IsSuperAdmin().has_permission(request, None))

    def test_is_self_or_admin_object_permission(self):
        owner = _make_user(username="tenant1", role=Role.TENANT)
        other = _make_user(username="tenant2", role=Role.TENANT)
        admin_user = _make_user(username="staff3", role=Role.ADMIN)

        perm = IsSelfOrAdmin()
        self.assertTrue(perm.has_object_permission(SimpleNamespace(user=owner), None, owner))
        self.assertFalse(perm.has_object_permission(SimpleNamespace(user=other), None, owner))
        self.assertTrue(perm.has_object_permission(SimpleNamespace(user=admin_user), None, owner))


class LoginViewTests(APITestCase):
    def setUp(self):
        self.user = _make_user(
            username="landlord1",
            role=Role.LANDLORD,
            phone_number="+254700000001",
            password="correct-horse-battery-staple",
        )

    def test_login_with_valid_credentials_returns_tokens_and_role_claim(self):
        response = self.client.post(
            "/api/auth/login/",
            {"username": "landlord1", "password": "correct-horse-battery-staple"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["role"], Role.LANDLORD)
        self.assertEqual(response.data["user"]["phone_number"], "+254700000001")

    def test_login_with_wrong_password_is_rejected(self):
        response = self.client.post(
            "/api/auth/login/", {"username": "landlord1", "password": "wrong"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_rotates_token(self):
        login = self.client.post(
            "/api/auth/login/",
            {"username": "landlord1", "password": "correct-horse-battery-staple"},
            format="json",
        )
        first_refresh = login.data["refresh"]

        refreshed = self.client.post("/api/auth/token/refresh/", {"refresh": first_refresh}, format="json")
        self.assertEqual(refreshed.status_code, status.HTTP_200_OK)
        self.assertNotEqual(refreshed.data["refresh"], first_refresh)

        # Rotation blacklists the original — replaying it must fail.
        replayed = self.client.post("/api/auth/token/refresh/", {"refresh": first_refresh}, format="json")
        self.assertEqual(replayed.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_endpoint_requires_auth(self):
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_endpoint_returns_current_user(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.get("/api/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "landlord1")


@override_settings(DEBUG=True)
class OTPFlowTests(APITestCase):
    def setUp(self):
        self.user = _make_user(
            username="tenant1", role=Role.TENANT, phone_number="+254711111111"
        )

    def test_request_for_unknown_number_does_not_leak_existence(self):
        response = self.client.post(
            "/api/auth/otp/request/", {"phone_number": "+254700000999"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("debug_code", response.data)

    def test_request_then_verify_issues_tokens(self):
        requested = self.client.post(
            "/api/auth/otp/request/", {"phone_number": "+254711111111"}, format="json"
        )
        self.assertEqual(requested.status_code, status.HTTP_200_OK)
        code = requested.data["debug_code"]

        verified = self.client.post(
            "/api/auth/otp/verify/",
            {"phone_number": "+254711111111", "code": code},
            format="json",
        )
        self.assertEqual(verified.status_code, status.HTTP_200_OK)
        self.assertIn("access", verified.data)
        self.assertEqual(verified.data["user"]["phone_number"], "+254711111111")

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_phone_verified)

    def test_wrong_code_is_rejected_and_cannot_be_reused(self):
        requested = self.client.post(
            "/api/auth/otp/request/", {"phone_number": "+254711111111"}, format="json"
        )
        correct_code = requested.data["debug_code"]
        wrong_code = "000000" if correct_code != "000000" else "111111"

        wrong = self.client.post(
            "/api/auth/otp/verify/",
            {"phone_number": "+254711111111", "code": wrong_code},
            format="json",
        )
        self.assertEqual(wrong.status_code, status.HTTP_400_BAD_REQUEST)

        right = self.client.post(
            "/api/auth/otp/verify/",
            {"phone_number": "+254711111111", "code": correct_code},
            format="json",
        )
        self.assertEqual(right.status_code, status.HTTP_200_OK)

    def test_otp_cannot_be_replayed(self):
        requested = self.client.post(
            "/api/auth/otp/request/", {"phone_number": "+254711111111"}, format="json"
        )
        code = requested.data["debug_code"]

        first = self.client.post(
            "/api/auth/otp/verify/", {"phone_number": "+254711111111", "code": code}, format="json"
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        second = self.client.post(
            "/api/auth/otp/verify/", {"phone_number": "+254711111111", "code": code}, format="json"
        )
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_expired_otp_is_rejected(self):
        otp = OTPRequest.objects.create(
            phone_number="+254711111111",
            code_hash=make_password("123456"),
            channel="whatsapp",
            expires_at=timezone.now() - timezone.timedelta(minutes=1),
        )
        response = self.client.post(
            "/api/auth/otp/verify/", {"phone_number": "+254711111111", "code": "123456"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(OTPRequest.objects.filter(pk=otp.pk, consumed_at__isnull=True).exists())


@override_settings(DEBUG=True)
class OTPEmailChannelTests(APITestCase):
    def setUp(self):
        self.user = _make_user(
            username="tenant-email1", role=Role.TENANT, phone_number="+254711222222", email="tenant@example.com"
        )

    @patch("messaging.tasks.send_email_notification")
    def test_email_channel_queues_email_instead_of_logging_only(self, mock_send_email):
        response = self.client.post(
            "/api/auth/otp/request/",
            {"phone_number": "+254711222222", "channel": "email"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send_email.delay.assert_called_once()
        kwargs = mock_send_email.delay.call_args.kwargs
        self.assertEqual(kwargs["to_email"], "tenant@example.com")
        self.assertIn(response.data["debug_code"], kwargs["html"])
        otp = OTPRequest.objects.filter(phone_number="+254711222222").latest("created_at")
        self.assertEqual(otp.channel, "email")

    def test_email_channel_without_email_on_file_does_not_crash(self):
        _make_user(username="tenant-noemail", role=Role.TENANT, phone_number="+254711333333")
        response = self.client.post(
            "/api/auth/otp/request/", {"phone_number": "+254711333333", "channel": "email"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_invalid_channel_is_rejected(self):
        response = self.client.post(
            "/api/auth/otp/request/", {"phone_number": "+254711222222", "channel": "carrier_pigeon"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_default_channel_is_whatsapp_and_does_not_email(self):
        with patch("messaging.tasks.send_email_notification") as mock_send_email:
            response = self.client.post(
                "/api/auth/otp/request/", {"phone_number": "+254711222222"}, format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send_email.delay.assert_not_called()
        otp = OTPRequest.objects.filter(phone_number="+254711222222").latest("created_at")
        self.assertEqual(otp.channel, "whatsapp")


class LandlordTenantRoutePermissionTests(APITestCase):
    """RBAC scoping: only landlord-role users (with a landlord_profile)
    can reach /api/landlord/tenants/ — this is also the route that was
    completely broken by the permissions.py import bug."""

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get("/api/landlord/tenants/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_wrong_role_is_forbidden(self):
        tenant_user = _make_user(username="tenant2", role=Role.TENANT)
        client = APIClient()
        client.force_authenticate(user=tenant_user)
        response = client.get("/api/landlord/tenants/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
