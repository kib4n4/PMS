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