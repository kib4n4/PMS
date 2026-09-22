# Dime PMS

A multi-tenant property management system for the Kenyan market: M-Pesa
rent collection (Daraja), platform fee billing, reseller/investor payouts,
WhatsApp tenant communication, maintenance ticketing, and KRA rental-income
filing. Backend is Django/DRF with a django-unfold admin theme, RBAC, a
JWT + OAuth2-client-credentials auth split, and a publicly-documented
OpenAPI schema; frontend is a Next.js scaffold with mock-data dashboards.

Full architecture and data model: **`CODEBASE_EXPLAINED.md`**.
Full endpoint reference: **`pms-endpoints.md`**.

## Status

Every backend app has real, tested logic behind it — not stubs. What
remains is mostly operational (real credentials, a few Phase 4+ business
rules), not architectural. See `CODEBASE_EXPLAINED.md#status` for the
precise breakdown; in short:

- **Blocked on external dependencies**: real Daraja/WhatsApp credentials,
  a Meta-approved WhatsApp OTP template, the manual per-landlord
  Safaricom-portal C2B URL registration step.
- **Deliberately deferred (Phase 4+)**: per-landlord fee rates, investor
  revenue-share amount computation, platform B2C float-balance checks.
- **Not started**: wiring the Next.js frontend to the real JSON endpoints
  (it renders mock data today; the endpoints exist).

Verify locally (from `backend/`, with the venv active):
```bash
python manage.py makemigrations --check   # no pending model changes
python manage.py migrate                  # applies cleanly against sqlite/postgres
python manage.py check                    # 0 issues
python manage.py test                     # full suite
```

## Running locally

```bash
cp .env.example .env   # fill in POSTGRES_PASSWORD, DJANGO_SECRET_KEY at minimum
docker compose up --build
```

Backend will be reachable inside the Docker network on `backend:8000`
(host Nginx, not part of this compose file, handles public TLS
termination and proxying per the design doc).

## One-time setup per environment (after `migrate`)

These are deliberate manual steps, not part of `migrate` — each is an
operational decision (who gets what permissions, when things run), not a
schema change:

```bash
# Grants role=admin staff their baseline Django-admin permissions (view/add/
# change on operational models, no delete on financial records, zero access
# to secret-bearing models — see accounts/management/commands/sync_role_permissions.py).
# Safe to re-run any time; fully replaces the group's permission set each time.
docker compose exec backend python manage.py sync_role_permissions

# Seeds django-celery-beat schedules for fee invoicing, nightly reconciliation,
# reseller/investor payout sweeps, and rent reminders — none of these run on
# any schedule until this has been run once. Idempotent.
docker compose exec backend python manage.py seed_periodic_tasks

# Issues an external-integrator API client (OAuth2 client-credentials grant,
# POST /api/oauth/token/) — the secret is shown once, at creation.
docker compose exec backend python manage.py create_api_client --name "Acme Accounting" --scopes invoices:read

# Rotates an existing client's secret (e.g. after a suspected leak) without
# touching its scopes/landlord binding — new secret is shown once.
docker compose exec backend python manage.py rotate_api_client_secret --client-id pms_xxxxxxxx
```

The Unfold-themed admin is at `/admin/`; a Dime staff user needs
`role=admin` (grants `is_staff` automatically — see
`accounts/signals.py`) or `is_superuser` to log in. API documentation
(Swagger UI) is public, no login required, at `/api/docs/`
(`/api/redoc/` and `/api/schema/` too).
