# backend/caretakers/tests.py

from datetime import date, timedelta

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import Role, User
from landlords.models import Landlord, Organization
from properties.models import Property

from .models import Caretaker, CaretakerAssignment


def _build_caretaker_with_assignment(username="caretaker-me1"):
    org = Organization.objects.create(name="CT Org")
    landlord_user = User.objects.create_user(username=f"ll-{username}", role=Role.LANDLORD)
    landlord = Landlord.objects.create(organization=org, user=landlord_user, full_name="CT Landlord")
    prop = Property.objects.create(landlord=landlord, name="CT Towers")

    caretaker_user = User.objects.create_user(username=username, role=Role.CARETAKER)
    caretaker = Caretaker.objects.create(user=caretaker_user, full_name="Carl Caretaker")
    CaretakerAssignment.objects.create(caretaker=caretaker, property=prop, effective_start=date.today())
    return caretaker, prop


class CaretakerMeViewTests(APITestCase):
    def test_returns_own_active_assignments(self):
        caretaker, prop = _build_caretaker_with_assignment()
        client = APIClient()
        client.force_authenticate(user=caretaker.user)

        response = client.get("/api/caretakers/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(caretaker.id))
        self.assertEqual(len(response.data["assignments"]), 1)
        self.assertEqual(response.data["assignments"][0]["property"]["id"], str(prop.id))

    def test_ended_assignment_is_excluded(self):
        caretaker, prop = _build_caretaker_with_assignment("caretaker-me2")
        CaretakerAssignment.objects.filter(caretaker=caretaker).update(
            effective_end=date.today() - timedelta(days=1)
        )
        client = APIClient()
        client.force_authenticate(user=caretaker.user)

        response = client.get("/api/caretakers/me/")
        self.assertEqual(response.data["assignments"], [])

    def test_non_caretaker_gets_404(self):
        landlord_user = User.objects.create_user(username="not-a-caretaker", role=Role.LANDLORD)
        client = APIClient()
        client.force_authenticate(user=landlord_user)

        response = client.get("/api/caretakers/me/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_request_rejected(self):
        response = self.client.get("/api/caretakers/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
