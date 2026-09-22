# Dime PMS — Codebase Explained

> This document explains the entire Property Management System (PMS) codebase,
> what each part does, and how the backend and frontend fit together.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Backend Architecture](#backend-architecture)
   - [Django Apps](#django-apps)
   - [Data Model](#data-model)
   - [API Layer](#api-layer)
   - [Celery Pipelines](#celery-pipelines)
   - [Webhooks](#webhooks)
   - [Integrations](#integrations)
3. [Frontend Architecture](#frontend-architecture)
   - [Tech Stack](#tech-stack)
   - [Routing](#routing)
   - [Components](#components)
   - [Dashboard Pages](#dashboard-pages)
4. [Core Flows](#core-flows)
   - [Rent Collection Flow](#rent-collection-flow)
   - [Fee & Commission Flow](#fee--commission-flow)
   - [Payout Flow](#payout-flow)
   - [Maintenance Flow](#maintenance-flow)
   - [Messaging Flow](#messaging-flow)
5. [How to Run Locally](#how-to-run-locally)
6. [Milestone Status](#milestone-status)
7. [Glossary](#glossary)

---

## System Overview

Dime PMS is a **multi-tenant Property Management System** built for the Kenyan
market. It connects landlords, tenants, resellers, investors, caretakers, and
Dime staff (admin) in a single platform that orchestrates:

- Property and lease management
- M-Pesa rent collection via Safaricom Daraja
- Platform fee billing and commission payouts
- WhatsApp-based tenant communication
- Maintenance ticketing
- Full audit trail for every financial action

The system is designed around **Option B** from the design doc: each landlord
keeps their own M-Pesa Paybill/Till. The platform observes payments via shared
webhooks and bills the landlord a platform fee separately.

---

## Backend Architecture

### Django Apps

| App | Purpose |
|-----|---------|
| `accounts` | Custom User model with roles (admin, landlord, tenant, reseller, investor, caretaker), OTP requests |
| `landlords` | Organization, Landlord profile, Daraja credentials, onboarding status |
| `properties` | Property and Unit models with status tracking |
| `leasing` | Tenant, Lease, tenant onboarding/offboarding serializers and viewsets |
| `billing` | Invoice, Payment, FeeLedgerEntry, FeeInvoice, C2B webhook views, Celery tasks |
| `partners` | Reseller, Investor, PayoutAccount, ReferralCommissionRule, RevenueShareAgreement, Disbursement |
| `caretakers` | Caretaker profile and effective-dated property assignments |
| `maintenance` | MaintenanceTicket model linked to units and tenants |
| `messaging` | NotificationTemplate, WhatsAppMessage, webhook views, Celery tasks |
| `audit` | AuditLog for manual admin overrides |

### Data Model

```
Organization
 └── Landlord (user, referred_by → Reseller?)
      ├── Property
      │    └── Unit (status: vacant/occupied/maintenance)
      │         └── Lease (status: application/active/renewal_pending/terminated)
      │              └── Tenant (user, full_name)
      ├── LandlordDarajaCredential (shortcode, environment, status)
      └── FeeInvoice (period, total, status)

Reseller (user, payout_account)
 └── ReferralCommissionRule (landlord, rate_percent, is_perpetual)

Investor (user, payout_account)
 └── RevenueShareAgreement (organization?, basis, rate_percent, cadence)

Caregiver (user)
 └── CaretakerAssignment (property, effective_start, effective_end)

MaintenanceTicket (unit, tenant, assigned_caretaker, status)

Payment (invoice, mpesa_transaction_id, amount, raw_callback_payload)
 └── FeeLedgerEntry (platform_fee_amount, reseller_commission_amount, reseller, invoiced)
      └── FeeInvoice (via M2M)

Disbursement (recipient_type, reseller|investor, amount, status, mpesa_conversation_id)

NotificationTemplate (name, meta_template_id, body, variables, approval_status, version)
 └── WhatsAppMessage (direction, phone_number, body, delivery_status, related_object)

AuditLog (actor, action, target_object_type, target_object_id, reason, metadata)
```

### API Layer

**Framework:** Django REST Framework (DRF)

**Authentication:** Session + Token

**Default permission:** `IsAuthenticated`

**Current endpoints:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/landlord/tenants/?active=true` | List active leases (scoped to landlord's properties) |
| POST | `/api/landlord/tenants/` | Onboard tenant onto a unit |
| POST | `/api/landlord/tenants/{id}/offboard/` | Terminate lease, free unit |

**Endpoint detail:** `backend/leasing/api_views.py` — `LandlordTenantViewSet`

- `get_queryset()` filters leases to only units in the requesting landlord's properties
- `TenantOnboardSerializer` reuses existing User/Tenant by phone number, validates unit belongs to landlord and is vacant
- `LeaseOffboardSerializer` sets lease to TERMINATED and unit to VACANT

### Celery Pipelines

**Broker:** Redis (`redis://redis:6379/0`)

**Scheduler:** Django Celery Beat with DatabaseScheduler

**Tasks in `billing/tasks.py`:**

| Task | Trigger | Purpose |
|------|---------|---------|
| `ingest_c2b_confirmation` | C2B webhook | Idempotently record Payment + FeeLedgerEntry from Safaricom callback |
| `generate_fee_invoices` | Celery Beat (monthly) | Roll up uninvoiced FeeLedgerEntries into a FeeInvoice per landlord |
| `reconcile_landlord_transactions` | Celery Beat (nightly) | Cross-check Payments against Safaricom Transaction Status API |
| `reconcile_all_landlords` | Celery Beat (nightly) | Fan out per-landlord reconciliation |

**Tasks in `partners/tasks.py`:**

| Task | Purpose |
|------|---------|
| `sweep_reseller_payouts` | Aggregate pending reseller commissions into Disbursements |
| `sweep_investor_payouts` | Aggregate pending investor revenue share into Disbursements |

### Webhooks

All webhooks are on `/webhooks/...` so host Nginx can apply a stricter rate limit.

| Method | Path | Status |
|--------|------|--------|
| POST | `/webhooks/mpesa/c2b/validation/` | Stub — always accept |
| POST | `/webhooks/mpesa/c2b/confirmation/` | Routes to `ingest_c2b_confirmation.delay(payload)` |
| POST | `/webhooks/mpesa/b2c/result/` | Stub — not wired to Disbursement yet |
| POST | `/webhooks/mpesa/b2c/timeout/` | Stub — no retry logic yet |

Security notes:
- `@csrf_exempt` — Safaricom cannot send CSRF tokens
- Real deployment must verify Safaricom IP ranges at Nginx layer
- `ingest_c2b_confirmation` validates shortcode against known `LandlordDarajaCredential` before any side effect

### Integrations

**`integrations/daraja.py`** — Safaricom Daraja client (STUBBED)

- `DarajaClient.for_landlord(credential)` — builds client for landlord's own shortcode
- `DarajaClient.for_platform()` — builds client for platform's own Daraja app
- `initiate_stk_push()` — STK Push for rent/fee collection
- `initiate_b2c_payment()` — B2C payout to reseller/investor
- `query_transaction_status()` — nightly reconciliation

Every method raises `NotImplementedError` with a `TODO(M2)` marker. The rest of
the codebase is built against these signatures, so wiring real credentials is a
find/replace inside this file only.

**`integrations/whatsapp.py`** — Meta WhatsApp Cloud API client (STUBBED)

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
/caretaker           → Caretaker dashboard
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
| `components/Icons.tsx` | 14 inline SVG icon components |

### Dashboard Pages

Each dashboard page follows the same pattern:
1. Page header with title and description
2. KPI grid (4 cards)
3. Charts section (2-column or 3-column grid)
4. Data tables section

**Landlord (`/landlord`):**
- KPIs: Total Properties, Occupied Units, Revenue (MTD), Open Tickets
- Charts: Revenue vs Platform Fees (bar), Occupancy by Property (donut)
- Tables: Recent Payments, Maintenance Tickets

**Reseller (`/reseller`):**
- KPIs: Referred Landlords, Commission Earned, Pending Payout, Avg Commission Rate
- Charts: Commission Trend (bar), Payout Status (donut)
- Tables: Referred Landlords, Payout History

**Investor (`/investor`):**
- KPIs: Revenue Share, Pending Payout, Active Agreements, Next Disbursement
- Charts: Revenue Share Trend (bar), Agreement Summary (cards)
- Tables: Active Agreements, Disbursement History

**Caretaker (`/caretaker`):**
- KPIs: Assigned Properties, Open Tickets, Avg Response Time, Resolution Rate
- Charts: Weekly Ticket Volume (bar), Assigned Properties (cards)
- Tables: Ticket Queue with status badges and icons

**Admin (`/admin`):**
- KPIs: Total Users, Active Landlords, System Health, Pending Reviews
- Charts: System Metrics (grid), Onboarding Queue (cards)
- Tables: Recent Audit Log

---

## Core Flows

### Rent Collection Flow

```
Tenant sends "Pay Rent" via WhatsApp
    ↓
messaging/webhook_views.py (inbound webhook)
    ↓
messaging/tasks.py (process message)
    ↓
messaging/services.py (trigger_stk_push_for_tenant)
    ├── Find tenant by phone
    ├── Find active lease
    ├── Find open invoice
    ├── Resolve landlord's LandlordDarajaCredential
    └── DarajaClient.initiate_stk_push() ← STUBBED
    ↓
Tenant receives M-Pesa STK Push prompt
    ↓
Tenant enters PIN on their phone
    ↓
Safaricom processes payment on LANDLORD's shortcode
    ↓
Safaricom calls /webhooks/mpesa/c2b/confirmation/
    ↓
billing/webhook_views.py → ingest_c2b_confirmation.delay(payload)
    ↓
Celery task:
    ├── Look up LandlordDarajaCredential by shortcode
    ├── Dedupe on mpesa_transaction_id (DB unique constraint)
    ├── Create Payment record
    ├── Calculate platform fee (5% of rent)
    ├── Calculate reseller commission (10% of platform fee)
    └── Create FeeLedgerEntry
```

### Fee & Commission Flow

```
Nightly / Monthly Celery Beat triggers generate_fee_invoices
    ↓
For each landlord:
    ├── Sum all uninvoiced FeeLedgerEntries
    └── Create FeeInvoice, mark entries as invoiced

FeeInvoice status:
    - open → awaiting landlord payment
    - paid → landlord paid via STK Push
    - overdue → past due_date
```

### Payout Flow

```
Celery Beat triggers sweep_reseller_payouts / sweep_investor_payouts
    ↓
Aggregate pending commissions / revenue share
    ↓
Create Disbursement records
    ↓
DarajaClient.initiate_b2c_payment() ← STUBBED
    ↓
Safaricom calls /webhooks/mpesa/b2c/result/
    ↓
Update Disbursement status to confirmed
```

### Maintenance Flow

```
Tenant reports issue via WhatsApp or app
    ↓
Create MaintenanceTicket (unit, tenant, category, description)
    ↓
Admin/Caretaker assigns ticket
    ↓
Caretaker resolves ticket
    ↓
WhatsApp notification sent to tenant (via messaging/tasks.py)
```

### Messaging Flow

```
Outbound:
    ├── Rent reminders (scheduled via Celery Beat)
    ├── Payment confirmations (triggered by webhook)
    ├── Maintenance status updates
    └── Onboarding messages

Inbound:
    ├── WhatsApp webhook receives message
    ├── Classify intent (pay rent, report issue, etc.)
    └── Trigger appropriate action
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
- Django: `http://localhost:8000` (inside Docker network)
- Celery Worker: auto-started
- Celery Beat: auto-started
- Postgres: `localhost:5432`
- Redis: `localhost:6379`

**Apply migrations:**
```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
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

## Milestone Status

| Milestone | Status | Notes |
|-----------|--------|-------|
| M0 | Done | Project scaffold, Docker Compose, 10 Django apps |
| M1 | Done | All models, admin, migrations, smoke-tested ORM chain |
| M2 | Pending | Real Daraja credentials + secrets manager |
| M3 | Pending | WhatsApp Cloud API wiring |
| M4 | Pending | B2C payout webhook wiring, reconciliation |
| M5 | Pending | Frontend connected to live DRF APIs |

**What works now:**
- Full Django ORM object chain (create via admin)
- C2B webhook → Celery task → idempotent Payment + FeeLedgerEntry
- Platform fee and reseller commission math
- Fee invoice generation
- Tenant onboarding/offboarding via DRF
- Frontend dashboard with mock data

**What needs real credentials before going live:**
- `integrations/daraja.py` — all methods are `NotImplementedError`
- `integrations/whatsapp.py` — all methods are `NotImplementedError`
- `LandlordDarajaCredential.c2b_urls_registered` — manual Safaricom portal step

---

## Glossary

| Term | Meaning |
|------|---------|
| **Daraja** | Safaricom's API gateway for M-Pesa |
| **C2B** | Customer-to-Business payment (tenant paying landlord) |
| **B2C** | Business-to-Customer payout (platform paying reseller/investor) |
| **STK Push** | M-Pesa push notification asking user to enter PIN |
| **FeeInvoice** | Monthly bill the platform sends a landlord for accumulated fees |
| **FeeLedgerEntry** | Single fee record created per confirmed payment |
| **Disbursement** | A B2C payout batch to a reseller or investor |
| **LandlordDarajaCredential** | Per-landlord Paybill/Till credentials for Option B |
| **Option B** | Each landlord keeps their own M-Pesa shortcode; platform never holds tenant funds |
| **Celery Beat** | Scheduled task runner (like cron, but inside Django) |
| **Onboarding Status** | Pending → Sandbox Testing → Awaiting C2B URL Registration → Live |

---

*Generated on 2026-08-20*
