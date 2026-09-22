<!-- backend/integrations/README.md -->

# Daraja Sandbox Test Credentials

This is a reference for testing `integrations/daraja.py` against Safaricom's
**sandbox** environment before any real landlord or platform credentials
exist. Nothing here is secret — these are the standard values Safaricom
publishes specifically so developers can test without moving real money.
**Never use these values, or this file's pattern, for production
credentials** — production secrets belong in the secrets manager only
(see the design doc's security requirements), never in a repo file.

## Shared sandbox values (STK Push / Lipa Na M-Pesa Online)

| Value | Test setting |
|---|---|
| Business Shortcode | `174379` |
| Passkey | `bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919` |
| Test phone number (PartyA/PhoneNumber) | `254708374149` |
| Test PIN | any 4 digits — sandbox accepts anything |
| Sandbox base URL | `https://sandbox.safaricom.co.ke` |
| Production base URL | `https://api.safaricom.co.ke` |

These are the long-standing, widely-documented default sandbox values for
the M-Pesa Express (STK Push) simulate flow. **One caveat**: on the current
Daraja portal, when you create a sandbox app and open the M-Pesa Express
"Simulate" panel, Safaricom may hand you an app-specific test passkey and
initiator password instead of (or alongside) the shared default above —
if what you get from the portal differs from the table, trust the portal.
Treat the table as the fallback/reference value, not a guarantee.

## Consumer Key / Consumer Secret

These are **not shared/public** — they're unique per app you register at
[developer.safaricom.co.ke](https://developer.safaricom.co.ke). Steps:

1. Create a developer account, log in, go to **My Apps**.
2. Create a new app, subscribe it to the **M-Pesa Sandbox** product.
3. The app detail page gives you a Consumer Key and Consumer Secret —
   these are what `DarajaClient.for_landlord()` / `.for_platform()` will
   eventually resolve from the secrets manager (see `daraja.py`).

## Initiator credentials (needed for B2C / Transaction Status, not STK Push)

- Sandbox initiator name is commonly `testapi` in community guides, but
  **confirm against your own app** — under the API tab, M-Pesa Express →
  Simulate → "Test Credentials" will show the initiator password and
  passkey tied to your specific sandbox app.
- The **Security Credential** used in B2C/Transaction Status requests is
  the initiator password encrypted with Safaricom's RSA public certificate
  (downloadable from the Daraja portal docs — sandbox and production use
  *different* certificates, don't mix them).

## C2B (Customer-to-Business) sandbox shortcodes

For testing C2B validation/confirmation flows specifically (distinct from
STK Push), Safaricom's sandbox historically provides shared shortcodes in
the `600000`–`600999` range for `registerurl`/simulate testing. Confirm
the current value in your Daraja portal's C2B product page — this range
has shifted over the product's history and shouldn't be hardcoded as fact
without checking the portal first.

## How this maps to our code

- `LandlordDarajaCredential` in `landlords/models.py` stores `*_secret_ref`
  fields — paths into the secrets manager, never raw values — even in
  sandbox. For local dev, it's fine to point a `*_secret_ref` at a local
  `.env` entry holding the sandbox value above; just don't carry that
  pattern into the production secrets-manager wiring in M2.
- `DarajaClient.for_landlord()` / `.for_platform()` in `daraja.py` are
  where the real HTTP calls get wired in M2 — everything above is what
  you'll plug in there first, against sandbox, before any landlord's real
  paybill is involved.
- Use the test phone number `254708374149` for every sandbox STK Push you
  trigger through the WhatsApp flow (`messaging/tasks.py`) or the landlord
  dashboard while M2 is in progress — real phone numbers won't do anything
  useful against a sandbox shortcode.

## Reference

Official docs: <https://developer.safaricom.co.ke/> — the definitive
source if anything here drifts from what the portal actually gives you.






<!-- backend/integrations/README.md -->
# Integrations: provider credentials & auth

Two separate things live here:

1. **Provider credentials** — how Twilio, Resend, and Daraja secrets get
   into the database (encrypted), and the JSON shape each one expects.
2. **OAuth2 (django-oauth-toolkit)** — how M2M and first-party clients get
   access tokens against this API.

---

## 1. Provider credentials

All third-party secrets live in `integrations.models.ProviderCredential`,
encrypted at rest with Fernet (`settings.FIELD_ENCRYPTION_KEY`). Never put
a real secret in `settings.py`, an env file committed to git, or a code
comment — only ever in one of the two flows below.

Twilio credentials are **per-landlord** (each landlord can have their own
WhatsApp sender); Resend is **platform-level** (`landlord=None`), since OTP
is a platform identity concern, not a landlord one.

### Templates

Copy one of these, fill in real values, and hand it to the admin form or
the CLI command below.

**Twilio** (`provider = twilio`, scoped to a landlord)
```json
{
  "account_sid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "auth_token": "your_twilio_auth_token",
  "whatsapp_number": "whatsapp:+14155238886"
}
```

**Resend** (`provider = resend`, platform-level — leave landlord blank)
```json
{
  "api_key": "re_xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```
Note: the current OTP flow (`accounts/services/otp.py`) actually reads its
key from `settings.RESEND_API_KEY`, not from a `ProviderCredential` row —
the row here is for future integrations service code that wants Resend
looked up the same way as everything else. Keep `RESEND_API_KEY` in the
environment for OTP to keep working.

**Daraja** (`provider = daraja`, scoped to a landlord — each landlord has
their own Paybill/Till per the Option-B payout design)
```json
{
  "consumer_key": "your_daraja_consumer_key",
  "consumer_secret": "your_daraja_consumer_secret",
  "shortcode": "174379",
  "passkey": "your_lipa_na_mpesa_passkey",
  "environment": "sandbox"
}
```

### Adding a credential — admin (one-off / non-technical staff)

1. Django admin → **Integrations → Provider credentials → Add**.
2. Pick `provider`, pick `landlord` (leave blank for Resend), optional
   `label`.
3. Paste the JSON template above (filled in) into **Credentials json**.
4. Save. The form encrypts it before it ever touches the database — the
   admin never shows plaintext again after that.

### Adding a credential — CLI (scripted / repeatable)

```bash
# Twilio, scoped to a landlord
python manage.py set_provider_credential twilio \
  --landlord-id 3f9c1e2a-... \
  --label "primary WhatsApp number" \
  --file twilio.json

# Resend, platform-level (no --landlord-id)
python manage.py set_provider_credential resend --json '{"api_key": "re_..."}'
```

The command deactivates any existing active credential for that
`(provider, landlord)` pair first, so re-running it to rotate a secret is
safe — it won't collide with the unique-active-credential constraint.

### Reading a credential in code

```python
from integrations.models import Provider, ProviderCredential

cred = ProviderCredential.get_active(Provider.TWILIO, landlord=some_landlord)
data = cred.get_credentials()  # decrypted dict, matches the template above
```
`get_active()` raises `ProviderCredential.DoesNotExist` if nothing's
configured — `WhatsAppClient.for_landlord()` already catches that and
falls back to the platform-level Twilio account in settings.

### Rotating `FIELD_ENCRYPTION_KEY`

All existing rows become undecryptable if you change this key without
migrating them first. To rotate: decrypt every row with the old key,
re-encrypt with the new one, then swap the env var. There's no built-in
command for this yet — write one before you actually need to rotate in
production.

---

## 2. OAuth2 (django-oauth-toolkit)

`oauth2_provider` (the "OAuth Toolkit") is what issues and validates
access tokens for this API. It's configured in `config/settings.py` under
`OAUTH2_PROVIDER` and wired into DRF via
`DEFAULT_AUTHENTICATION_CLASSES = ['oauth2_provider.contrib.rest_framework.OAuth2Authentication', ...]`.

### What's configured

- **PKCE is required** (`PKCE_REQUIRED = True`) for every authorization-code
  client — no plain public clients without a code verifier.
- **Refresh token rotation** (`ROTATE_REFRESH_TOKEN = True`) — each refresh
  issues a new refresh token and invalidates the old one.
- **Access tokens last 1 hour**, refresh tokens 30 days.
- **Scopes**: `read`, `write`, `tenants`, `properties`, `billing` — map
  these to what a client application is actually allowed to touch when you
  register it.
- **Custom validator**: `accounts.oauth.PMSOAuth2Validator`. For
  client-credentials (M2M) tokens, it binds `request.user` to the OAuth
  Application's owner, so the existing `IsLandlord`/role-based permission
  classes work the same way for M2M calls as they do for session logins —
  without this, `request.user` would be anonymous and every role check
  would fail.

### Registering a client application

Django admin → **Django OAuth Toolkit → Applications → Add**.
- **Client type**: `confidential` for server-to-server (M2M), `public` for
  a mobile/SPA client using PKCE.
- **Authorization grant type**: `client-credentials` for M2M,
  `authorization-code` for anything with a user logging in through a
  browser/app.
- **Owner**: for M2M apps, set this to the landlord (or platform) user
  whose identity/permissions the token should carry — this is what
  `PMSOAuth2Validator` reads.

### Flows, with curl

**Client credentials (M2M)**
```bash
curl -s -X POST "https://api.example.com/o/token/" \
  -u "CLIENT_ID:CLIENT_SECRET" \
  -d "grant_type=client_credentials&scope=read%20write"
```

**Authorization code + PKCE (exchange)**
```bash
curl -s -X POST "https://api.example.com/o/token/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code&code=AUTH_CODE&redirect_uri=REDIRECT_URI&client_id=CLIENT_ID&code_verifier=CODE_VERIFIER"
```

**Revoke a token**
```bash
curl -X POST "https://api.example.com/o/revoke_token/" \
  -u "CLIENT_ID:CLIENT_SECRET" \
  -d "token=ACCESS_OR_REFRESH_TOKEN"
```

**Introspect a token**
```bash
curl -X POST "https://api.example.com/o/introspect/" \
  -u "CLIENT_ID:CLIENT_SECRET" \
  -d "token=ACCESS_TOKEN"
```

### Local dev over plain HTTP

The toolkit refuses to issue tokens over non-TLS by default. For local
testing only:
```bash
export OAUTHLIB_INSECURE_TRANSPORT=1
```
Never set this in a deployed environment.

### Token response shape

```json
{
  "access_token": "...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "...",
  "scope": "read write"
}
```