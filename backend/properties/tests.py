# backend/properties/tests.py

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import Role, User
from landlords.models import Landlord, Organization

from .models import Property, Unit, UnitStatus


def _build_property_with_units(landlord_username="ll-props1"):
    org = Organization.objects.create(name="Props Org")
    user = User.objects.create_user(username=landlord_username, role=Role.LANDLORD)
    landlord = Landlord.objects.create(organization=org, user=user, full_name="Props Landlord")
    prop = Property.objects.create(landlord=landlord, name="Sunrise Apartments")
    Unit.objects.create(property=prop, label="A1", status=UnitStatus.OCCUPIED)
    Unit.objects.create(property=prop, label="A2", status=UnitStatus.VACANT)
    return landlord, prop


class PropertyViewSetTests(APITestCase):
    def setUp(self):
        self.landlord, self.prop = _build_property_with_units()
        self.other_landlord, self.other_prop = _build_property_with_units("ll-props2")
        self.admin = User.objects.create_superuser(username="props-admin", password="x", role=Role.ADMIN)

    def test_landlord_sees_only_their_own_properties(self):
        client = APIClient()
        client.force_authenticate(user=self.landlord.user)
        response = client.get("/api/properties/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in response.data}
        self.assertEqual(ids, {str(self.prop.id)})

    def test_units_are_nested_with_status(self):
        client = APIClient()
        client.force_authenticate(user=self.landlord.user)
        response = client.get("/api/properties/")
        units = response.data[0]["units"]
        self.assertEqual(len(units), 2)
        statuses = {u["status"] for u in units}
        self.assertEqual(statuses, {"occupied", "vacant"})

    def test_admin_sees_all_properties(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        response = client.get("/api/properties/")
        ids = {row["id"] for row in response.data}
        self.assertEqual(ids, {str(self.prop.id), str(self.other_prop.id)})

    def test_unrelated_landlord_sees_nothing(self):
        client = APIClient()
        client.force_authenticate(user=self.other_landlord.user)
        response = client.get("/api/properties/")
        ids = {row["id"] for row in response.data}
        self.assertNotIn(str(self.prop.id), ids)

    def test_unauthenticated_request_rejected(self):
        response = self.client.get("/api/properties/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
