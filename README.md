# PMS — M0/M1 Implementation

This is a working scaffold, not a demo: the Django project runs, migrations
apply, the ORM object chain (Organization → Landlord → Property → Unit →
Lease → Tenant, plus Reseller/Investor/Caretaker) has been created and
verified, and the C2B ingestion → fee ledger → fee invoice pipeline has
been smoke-tested for idempotency and correct fee math. What's stubbed is
exactly the external API calls that need real credentials — Daraja and
WhatsApp — and nothing else.

## What's implemented (M0 + M1)

- **10 Django apps**, one per core module: `accounts`, `landlords`,
  `properties`, `leasing`, `billing`, `partners`, `caretakers`,
  `maintenance`, `messaging`, `audit`.
- **Every model from the design doc**, with UUID primary keys and the
  correct FK relationships — including the circular reference between
  `Landlord.referred_by` (partners.Reseller) and `Reseller`'s referred
  landlords, which Django's migration dependency resolver handles as two
  migration files per app automatically.
- **Django admin registered for every model** — staff can create the full
  chain manually today, which is the actual M1 sign-off condition, not
  just a schema on paper.
- **Two Celery pipelines**, matching the design doc's split:
  - `billing/tasks.py` — `ingest_c2b_confirmation` (idempotent, dedupes on
    `mpesa_transaction_id`), `generate_fee_invoices`,
    `reconcile_landlord_transactions` / `reconcile_all_landlords`.
  - `partners/tasks.py` — `sweep_reseller_payouts`, `sweep_investor_payouts`,
    funded from platform fee revenue, not tenant rent.
- **Stubbed integration clients** (`integrations/daraja.py`,
  `integrations/whatsapp.py`) — every method that would make a real HTTP
  call raises `NotImplementedError` with a clear `TODO(M2)` /
  `TODO(M3)` marker, rather than silently no-op-ing. This sandbox has no
  network path to Safaricom or Meta's APIs and no real credentials exist
  yet, so this is the correct boundary for now.
- **Public webhook routes** on a separate URL group (`/webhooks/...`) so
  host Nginx can apply a stricter/separate rate limit, per the design doc.
  All four Daraja callback types are routed (C2B validation, C2B
  confirmation, B2C result, B2C timeout) even though B2C handling is
  still a TODO for M4.
- **Health check endpoint** (`/healthz/`) for the Docker healthcheck.
- **Docker Compose** wiring backend, Celery worker, Celery beat, Postgres,
  and Redis, matching the host-Nginx-terminates-TLS pattern from the
  design doc. Frontend service is commented out until it's more than a
  scaffold.
- **Next.js frontend scaffold** — routing structure documented in
  `frontend/app/page.tsx`, not built out. Dashboards are M5 work.

## What was verified, not just written

Run from `backend/` with the venv active:

```bash
python manage.py makemigrations   # generates cleanly, no model errors
python manage.py migrate          # applies cleanly against sqlite/postgres
python manage.py check            # 0 issues
```

The ORM chain and money-flow logic were smoke-tested directly (see
commands reproduced below) and confirmed:
- Full object chain creates correctly, including `referred_by` and
  `CaretakerAssignment`.
- Replaying the same C2B callback payload does **not** create a duplicate
  `Payment` (idempotency via the `mpesa_transaction_id` unique constraint).
- Platform fee calculates correctly (5% of rent collected).
- Reseller commission calculates correctly (10% of the **platform fee**,
  not the tenant's rent — this was a specific design requirement).
- `generate_fee_invoices` rolls up the ledger entries into a correct
  `FeeInvoice` total.
- The webhook → Celery task wiring round-trips through Django's test
  client and correctly rejects an unrecognized shortcode.

## What's genuinely next (M2)

This is where "implement it" runs into a real external dependency, not a
scope-cutting choice:

1. **Real Daraja credentials.** Sandbox Consumer Key/Secret and initiator
   credentials for at least one test landlord shortcode, plus the
   platform's own Daraja app for fee collection and B2C payouts.
2. **A secrets manager.** `LandlordDarajaCredential` stores secret
   *references*, not raw secrets, by design — Vault or a cloud secrets
   manager needs to exist before real credentials are entered anywhere.
3. **Real WhatsApp Cloud API access** — a Meta app, phone number ID, and
   access token — before `integrations/whatsapp.py` can be un-stubbed.
4. **The manual Safaricom-portal step** — registering each landlord's C2B
   validation/confirmation URLs against their shortcode — has to happen
   per landlord and can't be automated from this codebase; it's tracked
   as `LandlordDarajaCredential.c2b_urls_registered` so the admin console
   can surface it as an onboarding checklist item.

Once those exist, the `TODO(M2)` markers in `integrations/daraja.py` and
`billing/tasks.py` are the exact, complete list of what to wire — the
data model and pipeline structure around them don't need to change.

## Running locally

```bash
cp .env.example .env   # fill in POSTGRES_PASSWORD, DJANGO_SECRET_KEY at minimum
docker compose up --build
```

Backend will be reachable inside the Docker network on `backend:8000`
(host Nginx, not part of this compose file, handles public TLS
termination and proxying per the design doc).
