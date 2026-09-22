# backend/maintenance/tests.py

from datetime import date
from unittest.mock import patch

from django.test import TestCase

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
