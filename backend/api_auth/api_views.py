# backend/api_auth/api_views.py

from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .models import PlatformApiClient
from .tokens import CLIENT_CREDENTIALS_TOKEN_LIFETIME, issue_client_credentials_token


class TokenEndpointThrottle(AnonRateThrottle):
    """
    Credential-exchange endpoints are a brute-force target — client_secret
    guessing has no other rate limit anywhere in front of it (no nginx/WAF
    in this repo). Scoped separately from the rest of the API so it
    doesn't share a bucket with ordinary anonymous browsing.
    """

    scope = "oauth_token"

_TokenRequestSerializer = inline_serializer(
    "TokenRequest",
    {"client_id": serializers.CharField(), "client_secret": serializers.CharField()},
)
_TokenResponseSerializer = inline_serializer(
    "TokenResponse",
    {
        "access_token": serializers.CharField(),
        "token_type": serializers.CharField(),
        "expires_in": serializers.IntegerField(),
        "scope": serializers.CharField(),
    },
)


class TokenView(APIView):
    """
    POST /api/oauth/token/ {"client_id", "client_secret"} — OAuth2
    client-credentials grant for external integrators. Returns a
    short-lived Bearer token; there is no refresh token for this grant —
    request a new one with the same client_id/client_secret once it
    expires.
    """

    permission_classes = [AllowAny]
    throttle_classes = [TokenEndpointThrottle]

    @extend_schema(
        summary="Exchange a customer key/secret for an access token",
        description=(
            "OAuth2 client-credentials grant for external integrators. `client_id`/`client_secret` are "
            "issued out-of-band by `python manage.py create_api_client` — there is no self-service signup. "
            "The returned token is a Bearer token, valid for `expires_in` seconds; request a new one when it "
            "expires (no refresh token for this grant type). Use it as `Authorization: Bearer <access_token>` "
            "against endpoints under /api/external/."
        ),
        request=_TokenRequestSerializer,
        responses={200: _TokenResponseSerializer},
        examples=[
            OpenApiExample(
                "Example request",
                value={"client_id": "pms_1a2b3c4d5e6f7g8h", "client_secret": "..."},
                request_only=True,
            ),
            OpenApiExample(
                "Example response",
                value={"access_token": "eyJ...", "token_type": "Bearer", "expires_in": 1800, "scope": "invoices:read"},
                response_only=True,
            ),
        ],
        auth=[],
    )
    def post(self, request):
        client_id = str(request.data.get("client_id", "")).strip()
        client_secret = str(request.data.get("client_secret", "")).strip()
        if not client_id or not client_secret:
            return Response(
                {"detail": "client_id and client_secret are required."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            client = PlatformApiClient.objects.get(client_id=client_id, is_active=True)
        except PlatformApiClient.DoesNotExist:
            return Response({"detail": "Invalid client credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        if not client.verify_secret(client_secret):
            return Response({"detail": "Invalid client credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        client.last_used_at = timezone.now()
        client.save(update_fields=["last_used_at"])

        return Response(
            {
                "access_token": issue_client_credentials_token(client),
                "token_type": "Bearer",
                "expires_in": int(CLIENT_CREDENTIALS_TOKEN_LIFETIME.total_seconds()),
                "scope": " ".join(client.scopes),
            }
        )
