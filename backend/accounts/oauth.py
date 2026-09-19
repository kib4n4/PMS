# backend/accounts/oauth.py
"""Custom OAuth2 validator to bind client-credentials tokens to the
application owner so M2M calls are executed with the landlord's identity.
"""

from oauth2_provider.oauth2_validators import OAuth2Validator


class PMSOAuth2Validator(OAuth2Validator):
    def save_bearer_token(self, token, request, *args, **kwargs):
        # For client credentials, bind the request.user to the application's
        # owner so existing IsLandlord/role checks work as intended.
        try:
            if getattr(request, "grant_type", None) == "client_credentials" and getattr(request, "client", None) is not None:
                owner = getattr(request.client, "user", None)
                if not owner and hasattr(request.client, "owners"):
                    owners = list(request.client.owners.all())
                    owner = owners[0] if owners else None
                if owner:
                    request.user = owner
        except Exception:
            # be defensive — don't prevent token issuance on unexpected shapes
            pass
        return super().save_bearer_token(token, request, *args, **kwargs)
