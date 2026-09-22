# PMS Backend — Endpoints Reference

Status: reflects what's actually wired and working in the codebase today.
Every endpoint below is live — there are no remaining stubs at the HTTP
layer. (Real Daraja/WhatsApp *credentials* are a per-deployment secrets
step, not a code gap — see `README.md`.)

Full interactive documentation (request/response schemas, try-it-out) is
auto-generated and publicly reachable, no login required:

| Path | What |
|---|---|
| `/api/docs/` | Swagger UI |
| `/api/redoc/` | Redoc |
| `/api/schema/` | Raw OpenAPI 3 schema (JSON) |

## General

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/healthz/` | none | Health check. Returns `{"status": "ok"}`. Used by the Docker `HEALTHCHECK`. |
| ANY | `/admin/` | Django session (staff) | Unfold-themed Django admin. `role=admin` (auto-grants `is_staff`) or `is_superuser` required to log in — see **RBAC** below. |

## Auth (`/api/auth/...`) — JWT, session-independent

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/auth/login/` | none | Username/password → JWT pair. Every role can use this (Dime staff's primary path; a fallback for phone-first roles). |
| POST | `/api/auth/otp/request/` | none | `{"phone_number", "channel"?: "whatsapp"\|"email"}` — issues a 6-digit OTP for an *existing* user only (never creates accounts; anti-enumeration — same response either way). Email delivery is real; WhatsApp OTP delivery needs a Meta-pre-approved template before it can send (an external approval step, not a code gap) so it's logged-only until one exists. `DEBUG=True` echoes the code in the response. |
| POST | `/api/auth/otp/verify/` | none | `{"phone_number", "code"}` → JWT pair + user profile. |
| POST | `/api/auth/token/refresh/` | refresh token | SimpleJWT's standard refresh-token exchange. |
| POST | `/api/auth/logout/` | JWT | Blacklists the refresh token. |
| GET | `/api/auth/me/` | JWT | Current user's role/profile — the frontend's source of truth. |

## RBAC

`accounts.Role` (`admin`, `landlord`, `tenant`, `reseller`, `investor`,
`caretaker`) drives two independent layers:
- **API-level**: DRF permission classes (`accounts/permissions.py`) and
  per-view `get_queryset()` scoping (landlord/tenant/reseller/investor
  each see only their own data; see `accounts/rbac.py::resolve_actor_scope`
  for the shared resolver used by newer viewsets).
- **Admin-level**: every `User` save syncs a matching Django `Group`
  (`accounts/signals.py`); `python manage.py sync_role_permissions`
  grants `role=admin` staff real Django model permissions inside
  `/admin/` — view/add/change on operational models, no delete on
  financial records (`Payment`, `FeeLedgerEntry`, `Disbursement`), zero
  access to anything secret-bearing (`PlatformCredential`,
  `LandlordDarajaCredential`, `LandlordKRACredential`, `PlatformApiClient`
  — superuser-only).

## Landlord — tenant management (`/api/landlord/tenants/...`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/landlord/tenants/?active=true` | JWT, `role=landlord` | List leases scoped to the landlord's own properties. `?active=false` includes terminated leases. |
| POST | `/api/landlord/tenants/` | JWT, `role=landlord` | Onboard a tenant onto one of the landlord's vacant units (reuses an existing User/Tenant by phone number if known). |
| POST | `/api/landlord/tenants/{lease_id}/offboard/` | JWT, `role=landlord` | Terminates the lease, frees the unit. Tenant/User record kept as history. |

## Billing (`/api/billing/...`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/billing/invoices/` , `/{id}/` | JWT | JSON list/detail. Admin sees all; landlord sees their properties' invoices; tenant sees only their own. |
| GET | `/api/billing/payments/` , `/{id}/` | JWT | Same scoping, via the payment's invoice. |
| GET | `/api/billing/fee-invoices/` , `/{id}/` | JWT | What a landlord owes the platform. Admin sees all; landlord sees their own; tenants see none. |
| GET | `/api/billing/invoices/{id}/pdf/` | JWT | Downloadable invoice PDF. |
| GET | `/api/billing/payments/{id}/receipt/` | JWT | Downloadable payment receipt PDF. |
| POST | `/api/billing/invoices/{id}/pay/` | JWT | `{"phone_number"?}` — triggers an M-Pesa STK Push for the invoice's remaining balance (tenant's own shortcode-of-record, i.e. their landlord's). Returns 202 once Safaricom acknowledges; the actual payment lands later via the STK callback webhook. |

`FeeInvoice` collection (landlord → platform) uses the *same* STK-callback
webhook as tenant rent, discriminated by which FK is set on the
`STKPushRequest` row — see `billing/tasks.py::ingest_stk_callback`.
Triggering it and the manual "mark paid" fallback are admin actions on
`FeeInvoiceAdmin`, not separate endpoints.

## Partners (`/api/partners/...`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/partners/resellers/me/` | JWT, reseller | The authenticated reseller's own referred landlords, commission rules, disbursement history. |
| GET | `/api/partners/investors/me/` | JWT, investor | The authenticated investor's own revenue-share agreements and disbursement history. |
| GET | `/api/partners/resellers/` , `/{id}/` | JWT, `role=admin`/superuser | Same dashboard shape, for any reseller — Dime-staff-only. |
| GET | `/api/partners/investors/` , `/{id}/` | JWT, `role=admin`/superuser | Same, for any investor. |

## Taxes (`/api/taxes/...`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/taxes/returns/` | JWT | Landlord sees only their own Monthly Rental Income returns; superuser sees every landlord's. |

## External integrator API (`/api/external/...`) — OAuth2 client-credentials

Not user-facing — for third-party integrators issued a `client_id`/
`client_secret` out-of-band (`python manage.py create_api_client`, see
`README.md`). Entirely separate token type from the JWT above; the two
can never substitute for each other.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/oauth/token/` | none (rate-limited, 10/min/IP) | `{"client_id", "client_secret"}` → short-lived Bearer token scoped to whatever the client was granted. |
| GET | `/api/external/invoices/` | Bearer (client-credentials token), `invoices:read` scope | Read-only, scoped to the client's bound landlord (empty list for a platform-wide client). |

## M-Pesa Webhooks (`/webhooks/mpesa/...`)

Kept on a separate path group so host Nginx/a WAF can apply a stricter,
distinct rate limit from the rest of the API. All handlers are plain
Django views (not DRF — they speak Safaricom's payload shapes, not this
platform's JSON API, so they never appear in `/api/docs/`), `@csrf_exempt`,
and dispatch to Celery for idempotent processing.

| Method | Path | Purpose |
|---|---|---|
| POST | `/webhooks/mpesa/c2b/validation/` | Safaricom calls this before accepting a C2B payment. Accepts unconditionally today. |
| POST | `/webhooks/mpesa/c2b/confirmation/` | Confirmed C2B payment (manual Paybill-menu payments, or any C2B-registered shortcode). Resolves landlord by shortcode, invoice by AccountReference/MSISDN, records the payment idempotently. |
| POST | `/webhooks/mpesa/stk/callback/` | Result of an STK Push initiated via `/api/billing/invoices/{id}/pay/`, the WhatsApp "Pay Rent" flow, or a fee-invoice collection push. Correlates via `CheckoutRequestID` against the `STKPushRequest` row written at initiation. |
| POST | `/webhooks/mpesa/b2c/result/` | Outcome of a B2C payout (reseller/investor disbursement). Updates `Disbursement.status`, notifies the recipient via WhatsApp on success. |
| POST | `/webhooks/mpesa/b2c/timeout/` | B2C request timed out without a result — marks the disbursement `FAILED` for manual retry. |
| POST | `/webhooks/mpesa/transactionstatus/result/` | Async answer to a nightly reconciliation query. A non-zero `ResultCode` persists an `AuditLog` entry (`action="reconciliation_mismatch"`), queryable/actionable from `/admin/`. |
| POST | `/webhooks/mpesa/transactionstatus/timeout/` | Reconciliation query timed out — logged only. |

Security: Safaricom cannot send CSRF tokens (hence `@csrf_exempt`); a real
deployment must additionally allowlist Safaricom's IP ranges at the
Nginx/WAF layer — nothing in the application code restricts *who* can
POST to these paths, only whether the payload's shortcode/reference
resolves to something real.

## WhatsApp Webhook (`/webhooks/whatsapp/`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/webhooks/whatsapp/` | Meta's subscription verification handshake (`hub.mode`/`hub.verify_token`/`hub.challenge`). |
| POST | `/webhooks/whatsapp/` | Inbound messages and delivery-status updates. HMAC-SHA256-signed (`X-Hub-Signature-256`) against the configured app secret — **fails closed** (403) if no secret is configured, rather than silently accepting unsigned traffic. Dispatches parsed messages to intent routing (Pay Rent / Balance / Caretaker / Report Issue / menu fallback) and parsed status updates (`sent`/`delivered`/`read`/`failed`) to update the matching `WhatsAppMessage.delivery_status`. |

## Not exposed over HTTP (Celery-only)

Reconciliation, fee invoicing, and payout sweeps run on a schedule, not
on request — `python manage.py seed_periodic_tasks` seeds their
`django-celery-beat` schedules (nothing runs until this has been run once
per environment):

- `billing.tasks.generate_fee_invoices` — monthly
- `billing.tasks.reconcile_all_landlords` — nightly
- `partners.tasks.sweep_reseller_payouts` — monthly
- `partners.tasks.sweep_investor_payouts` — monthly (the underlying
  revenue-share *computation* is still a documented Phase 4+ TODO — the
  B2C payout plumbing works, the accounting math behind the amount
  doesn't exist yet)
- `messaging.tasks.send_rent_reminders` — daily
