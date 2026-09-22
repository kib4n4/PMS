# backend/accounts/permissions.py

from rest_framework.permissions import BasePermission

from .models import Role


class IsLandlord(BasePermission):
    message = "Only landlord accounts can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == Role.LANDLORD
            and hasattr(request.user, "landlord_profile")
        )


class IsReseller(BasePermission):
    message = "Only reseller accounts can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.role == Role.RESELLER
        )


class IsInvestor(BasePermission):
    message = "Only investor accounts can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.role == Role.INVESTOR
        )


class IsCaretaker(BasePermission):
    message = "Only caretaker accounts can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.role == Role.CARETAKER
        )


class IsTenant(BasePermission):
    message = "Only tenant accounts can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.role == Role.TENANT
        )


class IsAdmin(BasePermission):
    """Dime staff — role == admin. Not the same as super admin; see
    IsSuperAdmin for the "only super admin" tier the platform-wide admin
    console cards are gated on."""

    message = "Only Dime staff/admin accounts can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.role == Role.ADMIN
        )


class IsSuperAdmin(BasePermission):
    """True platform super admin (Django's is_superuser flag) — the
    narrowest role tier. Cards/endpoints meant for super admin only
    (platform credentials, cross-landlord views, audit log) use this,
    not IsAdmin."""

    message = "Only super admin accounts can perform this action."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class IsSelfOrAdmin(BasePermission):
    """Object-level: the requester IS the target object, or is Dime
    staff/super admin. Useful for user-owned-resource endpoints where
    admins need override access."""

    message = "You can only access your own resource."

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser or user.role == Role.ADMIN:
            return True
        return obj == user