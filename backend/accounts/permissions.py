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