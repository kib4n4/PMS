# backend/maintenance/signals.py

"""
Notifies a caretaker the moment they're assigned to a ticket, regardless
of HOW the assignment happens (admin panel today, a future API
endpoint tomorrow) — the signal is the one place this rule lives instead
of being duplicated at every call site that sets assigned_caretaker.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import MaintenanceTicket


@receiver(pre_save, sender=MaintenanceTicket)
def _stash_previous_caretaker(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_assigned_caretaker_id = None
        return
    previous_caretaker_id = (
        MaintenanceTicket.objects.filter(pk=instance.pk).values_list("assigned_caretaker_id", flat=True).first()
    )
    instance._previous_assigned_caretaker_id = previous_caretaker_id


@receiver(post_save, sender=MaintenanceTicket)
def _notify_on_caretaker_assignment(sender, instance, created, **kwargs):
    previous_id = getattr(instance, "_previous_assigned_caretaker_id", None)
    if instance.assigned_caretaker_id and instance.assigned_caretaker_id != previous_id:
        from .tasks import notify_caretaker_of_ticket_assignment

        notify_caretaker_of_ticket_assignment.delay(str(instance.id))
