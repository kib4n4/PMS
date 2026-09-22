# backend/accounts/management/commands/sync_role_permissions.py

from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from accounts.models import Role
from accounts.signals import role_group_name

# Apps whose models the 'role:admin' group gets baseline permissions on.
# Anything not listed here (accounts, credentials, api_auth, audit) is
# handled explicitly below instead of by blanket app membership.
OPERATIONAL_APPS = [
    "landlords", "properties", "leasing", "billing", "partners",
    "caretakers", "maintenance", "messaging", "taxes",
]

# Secret-bearing models — Dime staff (role=admin) get zero permissions
# here; only a real Django superuser can view/edit these in the admin.
NO_ACCESS_MODELS = {
    ("credentials", "platformcredential"),
    ("landlords", "landlorddarajacredential"),
    ("api_auth", "platformapiclient"),
    ("taxes", "landlordkracredential"),
}

# Immutable financial records — add/change/view but never delete, matching
# their existing PROTECT-heavy FK design (see billing/partners models).
NO_DELETE_MODELS = {
    ("billing", "payment"),
    ("billing", "feeledgerentry"),
    ("partners", "disbursement"),
}

# Explicitly view-only, regardless of app.
VIEW_ONLY_MODELS = {
    ("audit", "auditlog"),
}


def _codenames_for(pair, model_name):
    if pair in NO_ACCESS_MODELS:
        return []
    if pair in VIEW_ONLY_MODELS:
        return [f"view_{model_name}"]
    if pair in NO_DELETE_MODELS:
        return [f"{action}_{model_name}" for action in ("add", "change", "view")]
    return [f"{action}_{model_name}" for action in ("add", "change", "delete", "view")]


class Command(BaseCommand):
    help = (
        "Idempotently syncs baseline Django model permissions onto the 'role:admin' Group, "
        "so role=admin staff get real, enforced RBAC inside the Unfold admin — not just the "
        "coarse role checks DRF views already do. Safe to re-run; fully replaces the group's "
        "permission set each time rather than only adding to it."
    )

    def handle(self, *args, **options):
        admin_group, _ = Group.objects.get_or_create(name=role_group_name(Role.ADMIN))

        target_pairs = set(NO_DELETE_MODELS) | set(VIEW_ONLY_MODELS)
        for app_label in OPERATIONAL_APPS:
            for model in apps.get_app_config(app_label).get_models():
                target_pairs.add((app_label, model._meta.model_name))
        target_pairs -= NO_ACCESS_MODELS

        granted = []
        for pair in sorted(target_pairs):
            app_label, model_name = pair
            try:
                model = apps.get_model(app_label, model_name)
            except LookupError:
                continue
            content_type = ContentType.objects.get_for_model(model)
            for codename in _codenames_for(pair, model_name):
                try:
                    granted.append(Permission.objects.get(content_type=content_type, codename=codename))
                except Permission.DoesNotExist:
                    continue

        admin_group.permissions.set(granted)
        self.stdout.write(self.style.SUCCESS(
            f"Synced {len(granted)} permissions onto '{admin_group.name}' across {len(target_pairs)} models."
        ))
