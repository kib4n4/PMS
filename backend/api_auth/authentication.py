# backend/api_auth/authentication.py

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from .models import PlatformApiClient


class ExternalApiPrincipal:
    """
    Stand-in for request.user on a client-credentials-authenticated
    request — NOT a Django User (an external integrator has no login, no
    password, no role). DRF's IsAuthenticated only checks
    `.is_authenticated`, so this is enough to reuse the same permission
    plumbing as user-authenticated requests without a shadow User row.
    """

    is_authenticated = True

    def __init__(self, client: PlatformApiClient, scopes: list):
        self.client = client
        self.scopes = scopes

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes


class ClientCredentialsAuthentication(BaseAuthentication):
    """
    Authenticates requests bearing a token issued by POST
    /api/oauth/token/. Entirely separate from JWTAuthentication (user
    login tokens) — only applied to explicitly external-facing views, not
    added to global DEFAULT_AUTHENTICATION_CLASSES, so it can't affect
    any endpoint that doesn't opt in.
    """

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        raw_token = auth_header[len("Bearer "):]

        try:
            token = AccessToken(raw_token)
        except TokenError:
            return None

        if token.get("grant_type") != "client_credentials":
            return None

        client_id = token.get("client_id")
        try:
            client = PlatformApiClient.objects.get(client_id=client_id, is_active=True)
        except PlatformApiClient.DoesNotExist:
            raise AuthenticationFailed("Unknown or inactive API client.")

        return (ExternalApiPrincipal(client, token.get("scopes", [])), token)

    def authenticate_header(self, request):
        # Without this, DRF silently coerces a missing/invalid-token 401
        # into a 403 (its documented behavior for any authenticator that
        # doesn't advertise a WWW-Authenticate scheme) — matches
        # JWTAuthentication's own behavior so both Bearer-token schemes
        # respond the same way.
        return "Bearer"


class ClientCredentialsScheme(OpenApiAuthenticationExtension):
    """Tells drf-spectacular how to document ClientCredentialsAuthentication
    in the OpenAPI schema — without this it shows up as an unresolvable
    authenticator warning instead of a proper Bearer scheme."""

    target_class = "api_auth.authentication.ClientCredentialsAuthentication"
    name = "ClientCredentialsAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Token issued by POST /api/oauth/token/ using client_id/client_secret (OAuth2 client-credentials grant).",
        }
