# backend/maintenance/tasks.py

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def notify_caretaker_of_ticket_assignment(ticket_id: str):
    from messaging.tasks import send_whatsapp_reply

    from .models import MaintenanceTicket

    try:
        ticket = MaintenanceTicket.objects.select_related(
            "assigned_caretaker__user", "unit__property", "tenant"
        ).get(id=ticket_id)
    except MaintenanceTicket.DoesNotExist:
        logger.error("notify_caretaker_of_ticket_assignment: no ticket %s", ticket_id)
        return

    caretaker = ticket.assigned_caretaker
    if caretaker is None:
        return

    phone_number = caretaker.user.phone_number
    if not phone_number:
        logger.warning("Caretaker %s has no phone number on file — cannot notify", caretaker.id)
        return

    body = (
        f"New ticket assigned: {ticket.unit} — {ticket.description[:200]} "
        f"(reported by {ticket.tenant.full_name})."
    )
    send_whatsapp_reply(phone_number, body, related_object_type="MaintenanceTicket", related_object_id=str(ticket.id))


@shared_task
def notify_tenant_of_ticket_resolution(ticket_id: str):
    from messaging.tasks import send_whatsapp_reply

    from .models import MaintenanceTicket

    try:
        ticket = MaintenanceTicket.objects.select_related("tenant__user", "unit").get(id=ticket_id)
    except MaintenanceTicket.DoesNotExist:
        logger.error("notify_tenant_of_ticket_resolution: no ticket %s", ticket_id)
        return

    phone_number = ticket.tenant.user.phone_number
    if not phone_number:
        logger.warning("Tenant %s has no phone number on file — cannot notify of resolution", ticket.tenant_id)
        return

    body = f"Your maintenance ticket for {ticket.unit} has been resolved. Reply 'Report issue' if it recurs."
    send_whatsapp_reply(phone_number, body, related_object_type="MaintenanceTicket", related_object_id=str(ticket.id))
