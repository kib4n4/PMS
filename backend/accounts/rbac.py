# backend/accounts/rbac.py

"""
Central "who is this user, what are they scoped to" resolver for new
endpoints. `billing/api_views.py:_can_access_invoice` and
`taxes/api_views.py` predate this and have their own tested inline
scoping logic — left as-is. New object-scoped viewsets (billing JSON API,
partners dashboards) should use `resolve_actor_scope` instead of
duplicating the `hasattr(user, "<x>_profile")` pattern again.
"""

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from .models import Role


@dataclass(frozen=True)
class ActorScope:
    is_admin: bool
    landlord_id: Optional[UUID]
    tenant_id: Optional[UUID]
    reseller_id: Optional[UUID]
    investor_id: Optional[UUID]
    caretaker_id: Optional[UUID]


def resolve_actor_scope(user) -> ActorScope:
    is_admin = bool(user.is_superuser or getattr(user, "role", None) == Role.ADMIN)
    landlord = getattr(user, "landlord_profile", None)
    tenant = getattr(user, "tenant_profile", None)
    reseller = getattr(user, "reseller_profile", None)
    investor = getattr(user, "investor_profile", None)
    caretaker = getattr(user, "caretaker_profile", None)
    return ActorScope(
        is_admin=is_admin,
        landlord_id=landlord.id if landlord else None,
        tenant_id=tenant.id if tenant else None,
        reseller_id=reseller.id if reseller else None,
        investor_id=investor.id if investor else None,
        caretaker_id=caretaker.id if caretaker else None,
    )
