# backend/maintenance/signals.py

"""
Notifies a caretaker the moment they're assigned to a ticket, and
notifies the reporting tenant the moment it's resolved — regardless of
HOW either change happens (admin panel today, a future API endpoint
tomorrow). The signal is the one place each rule lives instead of being
duplicated at every call site that touches assigned_caretaker/status.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import MaintenanceTicket, TicketStatus


@receiver(pre_save, sender=MaintenanceTicket)
def _stash_previous_state(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_assigned_caretaker_id = None
        instance._previous_status = None
        return
    previous = (
        MaintenanceTicket.objects.filter(pk=instance.pk).values("assigned_caretaker_id", "status").first()
    )
    instance._previous_assigned_caretaker_id = previous["assigned_caretaker_id"] if previous else None
    instance._previous_status = previous["status"] if previous else None


@receiver(post_save, sender=MaintenanceTicket)
def _notify_on_caretaker_assignment(sender, instance, created, **kwargs):
    previous_id = getattr(instance, "_previous_assigned_caretaker_id", None)
    if instance.assigned_caretaker_id and instance.assigned_caretaker_id != previous_id:
        from .tasks import notify_caretaker_of_ticket_assignment

        notify_caretaker_of_ticket_assignment.delay(str(instance.id))


@receiver(post_save, sender=MaintenanceTicket)
def _handle_resolution(sender, instance, created, **kwargs):
    previous_status = getattr(instance, "_previous_status", None)
    if instance.status != TicketStatus.RESOLVED or previous_status == TicketStatus.RESOLVED:
        return

    if instance.resolved_at is None:
        # .update(), not instance.save() — avoids re-triggering these
        # signals for a change that's really just a timestamp stamp.
        MaintenanceTicket.objects.filter(pk=instance.pk).update(resolved_at=timezone.now())

    from .tasks import notify_tenant_of_ticket_resolution

    notify_tenant_of_ticket_resolution.delay(str(instance.id))
