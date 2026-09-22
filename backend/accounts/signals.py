# backend/accounts/signals.py

from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Role, User

ROLE_GROUP_PREFIX = "role:"


def role_group_name(role: str) -> str:
    return f"{ROLE_GROUP_PREFIX}{role}"


@receiver(post_save, sender=User)
def sync_role_group(sender, instance, created, raw, **kwargs):
    """
    Keeps each user's Django Group membership in lockstep with their PMS
    `role` field, and grants Django-admin login (`is_staff`) to ADMIN-role
    users automatically. This is what lets `sync_role_permissions` (see
    accounts/management/commands/sync_role_permissions.py) express RBAC on
    top of the Unfold admin using Django's own permission framework instead
    of only ad-hoc DRF-side role checks.

    Never downgrades `is_staff`/`is_superuser` — this only ever grants,
    matching the fact that a superuser or a manually-elevated staff account
    should never be silently stripped of admin access by a role edit.
    """
    if raw or not instance.role:
        return

    target_group, _ = Group.objects.get_or_create(name=role_group_name(instance.role))
    stale_groups = instance.groups.filter(name__startswith=ROLE_GROUP_PREFIX).exclude(pk=target_group.pk)
    if stale_groups.exists():
        instance.groups.remove(*stale_groups)
    if not instance.groups.filter(pk=target_group.pk).exists():
        instance.groups.add(target_group)

    if instance.role == Role.ADMIN and not instance.is_staff:
        User.objects.filter(pk=instance.pk).update(is_staff=True)
        instance.is_staff = True
