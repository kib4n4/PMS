# Dime PMS — Codebase Explained

> This document explains the entire Property Management System (PMS) codebase,
> what each part does, and how the backend and frontend fit together.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Backend Architecture](#backend-architecture)
   - [Django Apps](#django-apps)
   - [Data Model](#data-model)
   - [Auth & RBAC](#auth--rbac)
   - [Admin UI](#admin-ui)
   - [API Layer](#api-layer)
   - [Celery Pipelines](#celery-pipelines)
   - [Webhooks](#webhooks)
   - [Integrations](#integrations)
3. [Frontend Architecture](#frontend-architecture)
4. [Core Flows](#core-flows)
5. [How to Run Locally](#how-to-run-locally)
6. [Status](#status)
7. [Glossary](#glossary)

---

## System Overview

Dime PMS is a **multi-tenant Property Management System** built for the Kenyan
market. It connects landlords, tenants, resellers, investors, caretakers, and
Dime staff (admin) in a single platform that orchestrates:

- Property and lease management
- M-Pesa rent collection via Safaricom Daraja (each landlord's own shortcode)
- Platform fee billing (landlord → platform) and commission payouts
  (platform → reseller/investor)
- WhatsApp-based tenant communication, including proactive rent reminders
- Maintenance ticketing, with WhatsApp notifications on assignment and resolution
- KRA Monthly Rental Income tax filing
- An external, scoped OAuth2 API for third-party integrators
- Full audit trail for manual admin overrides and reconciliation discrepancies

The system is built around **Option B** from the original design doc: each
landlord keeps their own M-Pesa Paybill/Till. The platform observes payments
via shared webhooks and separately bills the landlord a platform fee — it
never holds tenant funds.

---

## Backend Architecture

### Django Apps

| App | Purpose |
|-----|---------|
| `accounts` | Custom User model with roles, phone-first OTP login, role→Group RBAC sync |
| `landlords` | Organization, Landlord profile, Daraja credentials, onboarding status |
| `properties` | Property and Unit models with status tracking |
| `leasing` | Tenant, Lease, landlord-facing tenant onboarding/offboarding API |
| `billing` | Invoice, Payment, FeeLedgerEntry, FeeInvoice, STK Push/C2B/B2C webhooks, Celery tasks, JSON API |
| `partners` | Reseller, Investor, PayoutAccount, ReferralCommissionRule, RevenueShareAgreement, Disbursement, dashboard API |
| `caretakers` | Caretaker profile and effective-dated property assignments |
| `maintenance` | MaintenanceTicket, with signals for assignment/resolution notifications |
| `messaging` | NotificationTemplate, WhatsAppMessage, EmailMessage, inbound webhook, intent routing, proactive reminders |
| `taxes` | LandlordKRACredential, RentalIncomeReturn (Monthly Rental Income filing) |
| `credentials` | Encrypted-at-rest platform-level secrets (Daraja, WhatsApp, Resend), DB-driven |
| `api_auth` | External-integrator OAuth2 client-credentials grant (`PlatformApiClient`) |
| `audit` | AuditLog — manual admin overrides and reconciliation mismatches |

### Data Model

```
Organization
 └── Landlord (user, referred_by → Reseller?)
      ├── Property
      │    └── Unit (status: vacant/occupied/maintenance)
      │         └── Lease (status: application/active/renewal_pending/terminated)
      │              └── Tenant (user, full_name)
      │                   └── MaintenanceTicket (status, resolved_at)
      ├── LandlordDarajaCredential (shortcode, environment, status — encrypted secrets)
      ├── LandlordKRACredential (kra_pin, environment, status — encrypted secrets)
      └── FeeInvoice (reference, period, total, status)

Reseller (user, payout_account)
 └── ReferralCommissionRule (landlord, rate_percent, is_perpetual)  — clean() rejects
     a second overlapping active rule for the same (reseller, landlord)

Investor (user, payout_account)
 └── RevenueShareAgreement (organization?, basis, rate_percent, cadence)

Caretaker (user)
 └── CaretakerAssignment (property, effective_start, effective_end)

Invoice (reference, status, due_date)
 └── Payment (mpesa_transaction_id, amount, raw_callback_payload)
      └── FeeLedgerEntry (platform_fee_amount, reseller_commission_amount, reseller, invoiced)
           └── FeeInvoice (via M2M)
                └── STKPushRequest (platform-fee collection push; landlord_credential blank)
 └── STKPushRequest (tenant-rent push; landlord_credential set) — same model, model-level
     clean() enforces exactly one of invoice/fee_invoice is set

Disbursement (recipient_type, reseller|investor, amount, status, mpesa_conversation_id)
 — clean() enforces recipient_type matches which FK is set

NotificationTemplate (name, meta_template_id, body, variables, approval_status, version)
 └── WhatsAppMessage (direction, phone_number, body, delivery_status, meta_message_id, related_object)

PlatformCredential (key, environment, value — encrypted)
PlatformApiClient (client_id, client_secret_hash, landlord?, scopes, is_active)

AuditLog (actor, action, target_object_type, target_object_id, reason, metadata)
```

### Auth & RBAC

Two independent authentication mechanisms, never interchangeable:

- **JWT** (`rest_framework_simplejwt`) — every internal, user-facing endpoint
  under `/api/`. Login is username/password (`POST /api/auth/login/`) or
  phone OTP (`POST /api/auth/otp/request/` → `/api/auth/otp/verify/`, real
  email delivery via Resend; WhatsApp OTP delivery is logged-only until a
  Meta-pre-approved OTP template exists — an external approval step, not a
  code gap). Tokens carry `role` and `is_super_admin` claims
  (`accounts/serializers.py::RoleTokenObtainPairSerializer`).
- **OAuth2 client-credentials** (`api_auth`) — external integrators only,
  under `/api/external/`. `POST /api/oauth/token/` exchanges a
  `client_id`/`client_secret` (issued via `manage.py create_api_client`,
  rotated via `manage.py rotate_api_client_secret`) for a scoped, short-lived
  Bearer token. Rate-limited (10/min/IP) since it's a credential-exchange
  endpoint with nothing else in front of it. Scopes are drawn from a fixed
  registry (`api_auth.models.Scope`), not free text.
  `api_auth/tests.py::TokenTypeIsolationTests` proves the two token types can
  never substitute for each other.

**RBAC** has two layers, both driven by the same `accounts.models.Role`:
- *API-level*: DRF permission classes (`accounts/permissions.py` —
  `IsLandlord`, `IsTenant`, `IsAdmin`, `IsSuperAdmin`, `IsPlatformStaff`,
  `IsSelfOrAdmin`) plus per-view `get_queryset()` scoping. Newer viewsets
  (billing/partners JSON APIs) use the shared
  `accounts/rbac.py::resolve_actor_scope(user)` resolver instead of
  duplicating the `hasattr(user, "<x>_profile")` pattern inline.
- *Admin-level*: a `post_save` signal on `User`
  (`accounts/signals.py::sync_role_group`) keeps each user in a matching
  Django `Group` (`role:admin`, `role:landlord`, ...) and auto-grants
  `is_staff` to `role=admin` users (never auto-revoked). `python manage.py
  sync_role_permissions` then grants that `role:admin` group real Django
  model permissions for the admin UI: view/add/change on operational models,
  **no delete** on financial records (`Payment`, `FeeLedgerEntry`,
  `Disbursement`), **zero access** to anything secret-bearing
  (`PlatformCredential`, `LandlordDarajaCredential`, `LandlordKRACredential`,
  `PlatformApiClient` — superuser-only). Re-running the command is safe;
  it fully replaces the group's permission set each time.

### Admin UI

**Theme:** [django-unfold](https://github.com/unfoldadmin/django-unfold) —
the only admin surface in the backend, and there are no custom-built JS admin
pages anywhere in this codebase. Every app's `ModelAdmin` is Unfold-based,
with:
- Inlines (e.g. read-only `PaymentInline` on `InvoiceAdmin` — payments are
  webhook-created, never hand-entered).
- `autocomplete_fields` throughout FK-heavy admins.
- Bulk actions: resend a payment receipt, initiate/mark-paid a `FeeInvoice`,
  approve/reject a `NotificationTemplate`, retry a failed `Disbursement`.
- Secret-bearing models (`LandlordDarajaCredential`, `LandlordKRACredential`,
  `PlatformCredential`) use a password-style widget
  (`credentials/admin_utils.py::SecretWidgetMixin`) that never pre-fills the
  decrypted current value — a blank submission on an *existing* row means
  "keep the current value," not "erase it." These fields stay genuinely
  editable (the whole point of `EncryptedSecretField` is DB-driven,
  redeploy-free credential entry) — access control lives in RBAC
  (superuser-only), not in making the fields read-only.
- Static assets served by whitenoise (`WhiteNoiseMiddleware`,
  `CompressedManifestStaticFilesStorage`) — there's no nginx/static-file
  layer anywhere else in this repo, so the Dockerfile runs `collectstatic`
  at build time.

### API Layer

**Framework:** Django REST Framework, `drf-spectacular` for OpenAPI 3 schema
generation.

**Default permission:** `IsAuthenticated` (except explicitly `AllowAny`
views: login, OTP, token exchange, and the docs routes themselves).

**Documentation:** `/api/docs/` (Swagger UI), `/api/redoc/`, `/api/schema/`
are all **publicly readable without login**
(`SPECTACULAR_SETTINGS['SERVE_PERMISSIONS'] = [AllowAny]` — this overrides
the global default for these three views only). No actual data is exposed,
only endpoint/schema shapes. Linked from the Unfold admin sidebar too.

Full endpoint list: **`pms-endpoints.md`**.

### Celery Pipelines

**Broker:** Redis. **Scheduler:** `django_celery_beat` `DatabaseScheduler` —
schedules are DB rows (`PeriodicTask`), not code, and **nothing is scheduled
by default**. `python manage.py seed_periodic_tasks` idempotently seeds all
five:

| Task | Cadence | Purpose |
|------|---------|---------|
| `billing.tasks.generate_fee_invoices` | monthly | Rolls up uninvoiced `FeeLedgerEntry` rows per landlord into a `FeeInvoice`, scoped to entries whose *payment* landed within the invoice's stated period. |
| `billing.tasks.reconcile_all_landlords` → `reconcile_landlord_transactions` | nightly | Cross-checks recent `Payment`s against Safaricom's Transaction Status API; a mismatch persists an `AuditLog` entry. |
| `partners.tasks.sweep_reseller_payouts` | monthly | B2C payout of accrued reseller commission. |
| `partners.tasks.sweep_investor_payouts` | monthly | B2C payout plumbing works; the revenue-share **amount computation** itself (`_compute_revenue_share_amount`) is a documented Phase 4+ TODO — a real accounting question, not a payout-mechanics gap. |
| `messaging.tasks.send_rent_reminders` | daily | One `rent_reminder` WhatsApp template per invoice due soon/overdue, deduped per invoice per day. |

Money math throughout `billing/tasks.py` is `decimal.Decimal` with
`ROUND_HALF_UP` — never binary float. Idempotency on the two hot paths
(`_record_payment`'s `Payment.mpesa_transaction_id` uniqueness,
`ingest_stk_callback`'s `STKPushRequest.status` check) is race-hardened:
a lost create-race raises `IntegrityError`, which is caught and treated as
"another delivery already recorded it," and the STK callback path uses
`select_for_update()` inside `transaction.atomic()` so two near-simultaneous
deliveries of the same Safaricom callback can't both proceed.

### Webhooks

All on `/webhooks/...` so host Nginx/a WAF can apply a stricter, separate
rate limit than the rest of the API — plain Django views, not DRF, so they
never appear in the OpenAPI schema. Full list: **`pms-endpoints.md`**.
Security: `@csrf_exempt` (Safaricom/Meta can't send CSRF tokens); the
WhatsApp webhook additionally verifies Meta's `X-Hub-Signature-256` HMAC and
**fails closed** if no app secret is configured. A real deployment must also
allowlist Safaricom's IP ranges at the Nginx/WAF layer.

### Integrations

**`integrations/daraja.py`** — real Safaricom Daraja HTTP client (OAuth2
token fetch, STK Push, B2C payout, transaction status query), used in two
distinct credential contexts: `DarajaClient.for_landlord(credential)` (a
specific landlord's own shortcode) and `DarajaClient.for_platform()` (the
platform's own Daraja app, for fee collection and B2C payouts, sourced from
`credentials.PlatformCredential` rows).

**`integrations/whatsapp.py`** — real Meta WhatsApp Cloud API client:
`send_session_message` (free-form, within Meta's 24h customer-initiated
window), `send_template_message` (pre-approved templates, works outside that
window), `parse_inbound_webhook` (extracts text/button/interactive-reply
messages), `parse_status_updates` (extracts delivery-status callbacks —
`sent`/`delivered`/`read`/`failed`).

Both clients are fully implemented — the only thing that's environment-specific
is whether real credentials have been entered (`LandlordDarajaCredential`
rows per landlord, `PlatformCredential` rows platform-wide, all
`EncryptedSecretField`, editable from `/admin/` without a redeploy). No
`NotImplementedError` stubs remain anywhere in the integration layer.

---

## Frontend Architecture

### Tech Stack

- **Framework:** Next.js 15 (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS v3
- **Icons:** Inline SVG components (no external icon library)
- **No UI component library** — all components are custom-built with Tailwind

### Routing

```
/                    → Role selection landing page
/landlord            → Landlord dashboard
/reseller            → Reseller dashboard
/investor            → Investor dashboard
/caretaker            → Caretaker dashboard
/admin               → Admin console
```

### Components

| File | Purpose |
|------|---------|
| `components/Sidebar.tsx` | Dark sidebar with role-filtered navigation and user profile |
| `components/DashboardLayout.tsx` | Shell: sidebar + scrollable main content |
| `components/KPICard.tsx` | Metric card with title, value, trend, icon, and accent color |
| `components/ChartCard.tsx` | Chart wrapper with title, description, and border |
| `components/DataTable.tsx` | Generic reusable table with column renderers |
| `components/Icons.tsx` | Inline SVG icon components |

Dashboards currently render mock data. The backend now has real JSON
endpoints they could consume (`/api/billing/...`, `/api/partners/...`,
`/api/landlord/tenants/`, `/api/taxes/returns/`) — wiring the frontend to
them is separate, not-yet-started work.

---

## Core Flows

### Rent Collection Flow

```
Tenant sends "Pay Rent" via WhatsApp (or calls POST /api/billing/invoices/{id}/pay/)
    ↓
messaging/services.py::trigger_stk_push_for_tenant
  — same billing/services.py::initiate_invoice_payment the authenticated
    API uses, so STKPushRequest is always written regardless of entrypoint
    ↓
DarajaClient.for_landlord(credential).initiate_stk_push()
    ↓
Tenant enters M-Pesa PIN
    ↓
Safaricom calls /webhooks/mpesa/stk/callback/ (or /c2b/confirmation/ for a
manual Paybill-menu payment)
    ↓
billing/tasks.py::ingest_stk_callback / ingest_c2b_confirmation
    ↓
_record_payment (idempotent, Decimal math):
    ├── Create Payment
    ├── Platform fee = amount × settings.PLATFORM_FEE_RATE (Decimal, ROUND_HALF_UP)
    ├── Reseller commission = platform_fee × rule.rate_percent (if referred)
    ├── Create FeeLedgerEntry
    └── invoice.refresh_status() + send_payment_receipt_email.delay()
```

### Fee Collection Flow (landlord → platform)

```
generate_fee_invoices (monthly) rolls up uninvoiced FeeLedgerEntry rows,
scoped to the invoice's stated period, into one FeeInvoice per landlord
    ↓
Admin action "Initiate STK push" (FeeInvoiceAdmin) → billing/services.py::
initiate_fee_invoice_payment — same STKPushRequest/webhook plumbing as
tenant rent, but via DarajaClient.for_platform() and discriminated by
STKPushRequest.fee_invoice (vs .invoice) being set
    ↓
/webhooks/mpesa/stk/callback/ → ingest_stk_callback branches on
stk_request.fee_invoice_id → _record_fee_invoice_payment → FeeInvoice.mark_paid()
```
(A manual "mark paid" admin action exists as a reconciliation fallback —
no Payment/FeeLedgerEntry is created for this direction of money flow;
those model tenant→landlord rent specifically.)

### Payout Flow (platform → reseller/investor)

```
sweep_reseller_payouts / sweep_investor_payouts (monthly)
    ↓
Create Disbursement (model-level clean() enforces recipient_type matches
the set FK)
    ↓
DarajaClient.for_platform().initiate_b2c_payment()
    ↓
/webhooks/mpesa/b2c/result/ → handle_b2c_result → Disbursement.status =
CONFIRMED/FAILED, WhatsApp confirmation to the recipient on success
```

### Maintenance Flow

```
Tenant reports issue via WhatsApp ("Report issue: <description>")
    ↓
messaging/services.py::create_maintenance_ticket_for_tenant → MaintenanceTicket (OPEN, unassigned)
    ↓
Admin/landlord assigns a caretaker
    ↓
maintenance/signals.py::_notify_on_caretaker_assignment → WhatsApp to caretaker
    ↓
Caretaker resolves the ticket (status → RESOLVED)
    ↓
maintenance/signals.py::_handle_resolution → auto-sets resolved_at,
notifies the reporting tenant via WhatsApp
```

### WhatsApp Messaging Flow

```
Outbound:
    ├── Intent-response replies (send_whatsapp_reply — free-form, within
    │   Meta's 24h session window)
    ├── Rent reminders (send_rent_reminders, daily — send_whatsapp_template,
    │   works outside the session window, requires an APPROVED
    │   NotificationTemplate, sets WhatsAppMessage.template_used)
    ├── Payment confirmations (webhook-triggered receipt email; WhatsApp
    │   confirmation on payout)
    └── Maintenance status updates (assignment, resolution)

Inbound:
    ├── HMAC-signature-verified webhook (fails closed with no app secret)
    ├── Phone number normalized (accounts/phone.py::normalize_msisdn) before
    │   tenant lookup — Meta sends bare-digit MSISDNs, User.phone_number is
    │   stored E.164; this match was silently broken before the fix
    ├── Intent classification (plain string matching — Pay Rent / Balance /
    │   Caretaker / Report Issue), unclassified input gets a menu fallback
    │   reply instead of silent drop
    └── Meta's delivery-status callbacks (sent/delivered/read/failed) update
        WhatsAppMessage.delivery_status via meta_message_id correlation
```

---

## How to Run Locally

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+ and npm

### Backend (Docker Compose)

```bash
cd "/Users/eli/PMS -UI/PMS"
cp .env.example .env
# Edit .env and set at minimum:
#   POSTGRES_PASSWORD
#   DJANGO_SECRET_KEY
docker compose up --build
```

Backend services:
- Django (Unfold admin at `/admin/`, public API docs at `/api/docs/`):
  `http://localhost:8000`
- Celery Worker: auto-started
- Celery Beat: auto-started (schedules must still be seeded — see below)
- Postgres: `localhost:5432`
- Redis: `localhost:6379`

**Apply migrations, then run one-time setup:**
```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
docker compose exec backend python manage.py sync_role_permissions
docker compose exec backend python manage.py seed_periodic_tasks
```

**Run tests:**
```bash
docker compose exec backend python manage.py test
```

### Frontend (Native)

```bash
cd "/Users/eli/PMS -UI/PMS/frontend"
npm install
npm run dev
```

Open `http://localhost:3000`

### Frontend (Docker)

Uncomment the `frontend` service in `docker-compose.yml` and run:
```bash
docker compose up --build
```

---

## Status

The M0/M1 "scaffold" framing this document used to carry is gone — every
app has real, tested logic behind it, not just a schema. What's left is
narrower and mostly operational, not architectural:

**Genuinely blocked on external dependencies:**
- Real Daraja credentials (sandbox at minimum) for at least one test
  landlord shortcode, plus the platform's own Daraja app.
- Real WhatsApp Cloud API access (Meta app, phone number ID, access token) —
  `integrations/whatsapp.py` is a complete client, it just has nothing to
  call with yet.
- A Meta-pre-approved WhatsApp OTP template, before OTP delivery over
  WhatsApp (vs. email, which works today) can go live.
- The manual Safaricom-portal step (registering each landlord's C2B
  validation/confirmation URLs against their shortcode) — tracked as
  `LandlordDarajaCredential.c2b_urls_registered`.

**Deliberately deferred (Phase 4+), not credential-blocked:**
- Per-landlord platform fee rates (currently one global
  `settings.PLATFORM_FEE_RATE`).
- Investor revenue-share amount computation
  (`partners.tasks._compute_revenue_share_amount` — the B2C payout
  mechanics work; the accounting formula behind the number doesn't exist
  yet).
- Platform B2C float-balance safety check before a payout sweep
  (`partners.tasks._check_platform_float`).

**Not started:**
- Wiring the Next.js frontend to the real JSON endpoints (it renders mock
  data today; the endpoints exist).

---

## Glossary

| Term | Meaning |
|------|---------|
| **Daraja** | Safaricom's API gateway for M-Pesa |
| **C2B** | Customer-to-Business payment (tenant paying landlord) |
| **B2C** | Business-to-Customer payout (platform paying reseller/investor) |
| **STK Push** | M-Pesa push notification asking the user to enter their PIN |
| **FeeInvoice** | Periodic bill the platform sends a landlord for accumulated platform fee — collected via its own STK Push flow, distinct from tenant rent |
| **FeeLedgerEntry** | Single fee record created per confirmed tenant payment |
| **Disbursement** | A B2C payout to a reseller or investor |
| **LandlordDarajaCredential** | Per-landlord Paybill/Till credentials for Option B, encrypted at rest |
| **Option B** | Each landlord keeps their own M-Pesa shortcode; the platform never holds tenant funds |
| **RBAC** | `Role` → Django `Group` sync + `sync_role_permissions`; see **Auth & RBAC** above |
| **OAuth2 client-credentials** | The external-integrator token grant (`api_auth`) — distinct from user JWT login |
| **Unfold** | The Django admin theme; the only admin UI in this backend |
| **Celery Beat** | Scheduled task runner (DB-driven via `django_celery_beat`; nothing runs until `seed_periodic_tasks` is run) |
| **Onboarding Status** | Pending → Sandbox Testing → Awaiting C2B URL Registration → Live |

---

*Last substantively updated 2026-09-22 — Unfold admin, RBAC, OAuth
hardening, billing/WhatsApp refinement, public OpenAPI docs.*
