# backend/maintenance/tests.py

from datetime import date
from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import Role, User
from caretakers.models import Caretaker
from landlords.models import Landlord, Organization
from leasing.models import Lease, LeaseStatus, Tenant
from properties.models import Property, Unit

from .models import MaintenanceTicket, TicketStatus


def _build_ticket():
    org = Organization.objects.create(name="Maint Org")
    landlord_user = User.objects.create_user(username="ll-maint", role=Role.LANDLORD)
    landlord = Landlord.objects.create(organization=org, user=landlord_user, full_name="Landlord Maint")
    prop = Property.objects.create(landlord=landlord, name="Maint Towers")
    unit = Unit.objects.create(property=prop, label="D1")
    tenant_user = User.objects.create_user(username="tenant-maint", role=Role.TENANT, phone_number="+254733000001")
    tenant = Tenant.objects.create(user=tenant_user, full_name="Terry Tenant")
    Lease.objects.create(unit=unit, tenant=tenant, rent_amount=9000, billing_day=1, start_date=date.today(), status=LeaseStatus.ACTIVE)
    return MaintenanceTicket.objects.create(unit=unit, tenant=tenant, description="Broken window")


class CaretakerAssignmentSignalTests(TestCase):
    @patch("maintenance.tasks.notify_caretaker_of_ticket_assignment.delay")
    def test_assigning_caretaker_triggers_notification(self, mock_delay):
        ticket = _build_ticket()
        caretaker_user = User.objects.create_user(username="caretaker-maint", role=Role.CARETAKER, phone_number="+254744000001")
        caretaker = Caretaker.objects.create(user=caretaker_user, full_name="Carl Caretaker")

        ticket.assigned_caretaker = caretaker
        ticket.status = TicketStatus.ASSIGNED
        ticket.save()

        mock_delay.assert_called_once_with(str(ticket.id))

    @patch("maintenance.tasks.notify_caretaker_of_ticket_assignment.delay")
    def test_creating_ticket_without_caretaker_does_not_notify(self, mock_delay):
        _build_ticket()
        mock_delay.assert_not_called()

    @patch("maintenance.tasks.notify_caretaker_of_ticket_assignment.delay")
    def test_resaving_with_same_caretaker_does_not_renotify(self, mock_delay):
        ticket = _build_ticket()
        caretaker_user = User.objects.create_user(username="caretaker-maint2", role=Role.CARETAKER, phone_number="+254744000002")
        caretaker = Caretaker.objects.create(user=caretaker_user, full_name="Cara Caretaker")

        ticket.assigned_caretaker = caretaker
        ticket.save()
        mock_delay.assert_called_once_with(str(ticket.id))

        mock_delay.reset_mock()
        ticket.status = TicketStatus.IN_PROGRESS
        ticket.save()
        mock_delay.assert_not_called()

    @patch("maintenance.tasks.notify_caretaker_of_ticket_assignment.delay")
    def test_reassigning_to_different_caretaker_notifies_again(self, mock_delay):
        ticket = _build_ticket()
        caretaker_user1 = User.objects.create_user(username="caretaker-maint3", role=Role.CARETAKER, phone_number="+254744000003")
        caretaker1 = Caretaker.objects.create(user=caretaker_user1, full_name="First Caretaker")
        caretaker_user2 = User.objects.create_user(username="caretaker-maint4", role=Role.CARETAKER, phone_number="+254744000004")
        caretaker2 = Caretaker.objects.create(user=caretaker_user2, full_name="Second Caretaker")

        ticket.assigned_caretaker = caretaker1
        ticket.save()
        ticket.assigned_caretaker = caretaker2
        ticket.save()

        self.assertEqual(mock_delay.call_count, 2)


class NotifyCaretakerTaskTests(TestCase):
    @patch("messaging.tasks.send_whatsapp_reply")
    def test_sends_whatsapp_with_ticket_details(self, mock_send_reply):
        from .tasks import notify_caretaker_of_ticket_assignment

        ticket = _build_ticket()
        caretaker_user = User.objects.create_user(username="caretaker-maint5", role=Role.CARETAKER, phone_number="+254744000005")
        caretaker = Caretaker.objects.create(user=caretaker_user, full_name="Task Test Caretaker")
        ticket.assigned_caretaker = caretaker
        ticket.save()
        mock_send_reply.reset_mock()  # save() already triggered the signal path once (eager Celery in tests)

        notify_caretaker_of_ticket_assignment(str(ticket.id))

        mock_send_reply.assert_called_once()
        args, kwargs = mock_send_reply.call_args
        self.assertEqual(args[0], "+254744000005")
        self.assertIn("Broken window", args[1])

    @patch("messaging.tasks.send_whatsapp_reply")
    def test_caretaker_without_phone_number_does_not_crash(self, mock_send_reply):
        from .tasks import notify_caretaker_of_ticket_assignment

        ticket = _build_ticket()
        caretaker_user = User.objects.create_user(username="caretaker-maint6", role=Role.CARETAKER)
        caretaker = Caretaker.objects.create(user=caretaker_user, full_name="No Phone Caretaker")
        ticket.assigned_caretaker = caretaker
        ticket.save()

        notify_caretaker_of_ticket_assignment(str(ticket.id))
        mock_send_reply.assert_not_called()


class TicketResolutionSignalTests(TestCase):
    @patch("maintenance.tasks.notify_tenant_of_ticket_resolution.delay")
    def test_resolving_ticket_sets_resolved_at_and_notifies(self, mock_delay):
        ticket = _build_ticket()
        self.assertIsNone(ticket.resolved_at)

        ticket.status = TicketStatus.RESOLVED
        ticket.save()

        ticket.refresh_from_db()
        self.assertIsNotNone(ticket.resolved_at)
        mock_delay.assert_called_once_with(str(ticket.id))

    @patch("maintenance.tasks.notify_tenant_of_ticket_resolution.delay")
    def test_resaving_already_resolved_ticket_does_not_renotify(self, mock_delay):
        ticket = _build_ticket()
        ticket.status = TicketStatus.RESOLVED
        ticket.save()
        mock_delay.assert_called_once()

        mock_delay.reset_mock()
        ticket.category = "plumbing"
        ticket.save()
        mock_delay.assert_not_called()

    @patch("maintenance.tasks.notify_tenant_of_ticket_resolution.delay")
    def test_non_resolution_status_change_does_not_notify(self, mock_delay):
        ticket = _build_ticket()
        ticket.status = TicketStatus.IN_PROGRESS
        ticket.save()
        mock_delay.assert_not_called()


class NotifyTenantOfResolutionTaskTests(TestCase):
    @patch("messaging.tasks.send_whatsapp_reply")
    def test_sends_whatsapp_to_tenant(self, mock_send_reply):
        from .tasks import notify_tenant_of_ticket_resolution

        ticket = _build_ticket()
        ticket.status = TicketStatus.RESOLVED
        ticket.save()
        mock_send_reply.reset_mock()  # save() already triggered the signal path once (eager Celery in tests)

        notify_tenant_of_ticket_resolution(str(ticket.id))

        mock_send_reply.assert_called_once()
        args, kwargs = mock_send_reply.call_args
        self.assertEqual(args[0], "+254733000001")
        self.assertIn("resolved", args[1])

    @patch("messaging.tasks.send_whatsapp_reply")
    def test_tenant_without_phone_number_does_not_crash(self, mock_send_reply):
        from .tasks import notify_tenant_of_ticket_resolution

        org = Organization.objects.create(name="Maint Org No Phone")
        landlord_user = User.objects.create_user(username="ll-maint-np", role=Role.LANDLORD)
        landlord = Landlord.objects.create(organization=org, user=landlord_user, full_name="Landlord Maint NP")
        prop = Property.objects.create(landlord=landlord, name="Maint Towers NP")
        unit = Unit.objects.create(property=prop, label="D2")
        tenant_user = User.objects.create_user(username="tenant-maint-np", role=Role.TENANT)
        tenant = Tenant.objects.create(user=tenant_user, full_name="No Phone Tenant")
        Lease.objects.create(unit=unit, tenant=tenant, rent_amount=9000, billing_day=1, start_date=date.today(), status=LeaseStatus.ACTIVE)
        ticket = MaintenanceTicket.objects.create(unit=unit, tenant=tenant, description="Leak", status=TicketStatus.RESOLVED)

        notify_tenant_of_ticket_resolution(str(ticket.id))
        mock_send_reply.assert_not_called()


class MaintenanceTicketViewSetTests(APITestCase):
    def setUp(self):
        self.ticket = _build_ticket()
        self.landlord = self.ticket.unit.property.landlord
        self.caretaker_user = User.objects.create_user(username="caretaker-vs1", role=Role.CARETAKER)
        self.caretaker = Caretaker.objects.create(user=self.caretaker_user, full_name="VS Caretaker")
        self.ticket.assigned_caretaker = self.caretaker
        self.ticket.save()
        self.admin = User.objects.create_superuser(username="maint-admin", password="x", role=Role.ADMIN)

        other_org = Organization.objects.create(name="Other Maint Org")
        other_user = User.objects.create_user(username="other-ll-maint", role=Role.LANDLORD)
        self.other_landlord = Landlord.objects.create(organization=other_org, user=other_user, full_name="Other")

    def test_landlord_sees_tickets_on_their_properties(self):
        client = APIClient()
        client.force_authenticate(user=self.landlord.user)
        response = client.get("/api/maintenance/tickets/")
        ids = {row["id"] for row in response.data}
        self.assertEqual(ids, {str(self.ticket.id)})

    def test_caretaker_sees_only_assigned_tickets(self):
        client = APIClient()
        client.force_authenticate(user=self.caretaker_user)
        response = client.get("/api/maintenance/tickets/")
        ids = {row["id"] for row in response.data}
        self.assertEqual(ids, {str(self.ticket.id)})

    def test_admin_sees_all_tickets(self):
        client = APIClient()
        client.force_authenticate(user=self.admin)
        response = client.get("/api/maintenance/tickets/")
        ids = {row["id"] for row in response.data}
        self.assertIn(str(self.ticket.id), ids)

    def test_unrelated_landlord_sees_nothing(self):
        client = APIClient()
        client.force_authenticate(user=self.other_landlord.user)
        response = client.get("/api/maintenance/tickets/")
        self.assertEqual(response.data, [])

    def test_unauthenticated_request_rejected(self):
        response = self.client.get("/api/maintenance/tickets/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
