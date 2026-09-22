# backend/api_auth/tokens.py

from datetime import timedelta

from rest_framework_simplejwt.tokens import AccessToken

CLIENT_CREDENTIALS_TOKEN_LIFETIME = timedelta(minutes=30)


def issue_client_credentials_token(client) -> str:
    """
    Builds a bare SimpleJWT access token (no user_id — there's no Django
    User behind an external integrator) carrying client_id/scopes and a
    `grant_type` marker. Deliberately keeps token_type="access" (the
    SimpleJWT default) so signature/expiry validation stays standard;
    ClientCredentialsAuthentication is what actually distinguishes this
    from a user-issued access token, via the grant_type claim — a normal
    user token lacks it, and this token lacks user_id, so neither can be
    used in place of the other.
    """
    token = AccessToken()
    token.set_exp(lifetime=CLIENT_CREDENTIALS_TOKEN_LIFETIME)
    token["grant_type"] = "client_credentials"
    token["client_id"] = client.client_id
    token["scopes"] = client.scopes
    return str(token)
