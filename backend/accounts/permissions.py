# backend/accounts/permissions.py

from rest_framework.permissions import BasePermission, SAFE_METHODS

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


class HasOAuthScopeOrIsSessionUser(BasePermission):
    """Hybrid permission: allow session-authenticated users (first-party UI)
    to proceed and enforce role-based checks separately. For OAuth tokens,
    require `read` for safe methods and `write` for mutating methods.
    """

    message = "This token does not have the required OAuth scope."

    def has_permission(self, request, view):
        # First-party/session users (no token) are allowed; downstream
        # permissions (IsLandlord) will enforce role checks.
        if request.user and request.user.is_authenticated and not getattr(request, "auth", None):
            return True

        token = getattr(request, "auth", None)
        if not token:
            return False

        required = "read" if request.method in SAFE_METHODS else "write"

        # token.scope is the common shape (space-separated string). DOT also
        # stores scope on the AccessToken instance as .scope.
        scope_str = getattr(token, "scope", None)
        if scope_str is None:
            # Some wrappers expose token.token.scope
            inner = getattr(token, "token", None)
            scope_str = getattr(inner, "scope", None) if inner is not None else None

        if scope_str:
            return required in scope_str.split()

        # fallback: token.scopes list
        scopes = getattr(token, "scopes", None)
        if scopes:
            return required in scopes

        return False
