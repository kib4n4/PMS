# backend/api_auth/permissions.py

from rest_framework.permissions import BasePermission


class HasScope(BasePermission):
    """Base class — use require_scope(...) below rather than this
    directly, since DRF's permission_classes list needs classes, not
    pre-built instances with arguments."""

    required_scope = None
    message = "This API client is not authorized for this scope."

    def has_permission(self, request, view):
        principal = request.user
        if not hasattr(principal, "has_scope"):
            return False
        return principal.has_scope(self.required_scope)


def require_scope(scope: str):
    """Factory: require_scope("invoices:read") returns a permission
    class gating access on that exact scope string."""
    return type(f"HasScope_{scope.replace(':', '_')}", (HasScope,), {"required_scope": scope})
