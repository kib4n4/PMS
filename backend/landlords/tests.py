# backend/landlords/tests.py

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import Role, User
from audit.models import AuditLog

from .models import Landlord, LandlordDarajaCredential, OnboardingStatus, Organization


def _build_landlord(shortcode, onboarding_status):
    org = Organization.objects.create(name=f"Org {shortcode}")
    user = User.objects.create_user(username=f"ll-{shortcode}", role=Role.LANDLORD)
    landlord = Landlord.objects.create(organization=org, user=user, full_name=f"Landlord {shortcode}")
    LandlordDarajaCredential.objects.create(
        landlord=landlord, shortcode=shortcode, consumer_key="ck", consumer_secret="cs",
        status=onboarding_status,
    )
    return landlord


class AdminOverviewViewTests(APITestCase):
    def setUp(self):
        self.live_landlord = _build_landlord("900100", OnboardingStatus.LIVE)
        self.pending_landlord = _build_landlord("900200", OnboardingStatus.PENDING)
        AuditLog.objects.create(
            action="reconciliation_mismatch", target_object_type="Payment", target_object_id="TXN1", reason="test"
        )
        self.admin = User.objects.create_superuser(username="overview-admin", password="x", role=Role.ADMIN)
        self.staff = User.objects.create_user(username="overview-staff", role=Role.ADMIN)

    def test_admin_sees_real_counts(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        response = client.get("/api/admin/overview/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["active_landlords"], 1)
        self.assertEqual(response.data["pending_onboarding"], 1)
        self.assertGreaterEqual(response.data["total_users"], 4)
        self.assertEqual(len(response.data["recent_audit_log"]), 1)
        queue_shortcodes = {row["shortcode"] for row in response.data["onboarding_queue"]}
        self.assertEqual(queue_shortcodes, {"900200"})

    def test_role_admin_staff_can_access(self):
        client = APIClient()
        client.force_authenticate(user=self.staff)
        response = client.get("/api/admin/overview/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_staff_landlord_is_forbidden(self):
        client = APIClient()
        client.force_authenticate(user=self.live_landlord.user)
        response = client.get("/api/admin/overview/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_request_rejected(self):
        response = self.client.get("/api/admin/overview/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
