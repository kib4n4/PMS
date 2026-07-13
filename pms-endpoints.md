# PMS Backend — Endpoints Reference (M0/M1 scaffold)

Status: reflects what's actually wired in the codebase so far. The webhook
views are routed but their handler bodies are still stubs pending real
Safaricom credentials (M2) — see `integrations/daraja.py`.

## General

| Method | Path | Purpose |
|---|---|---|
| GET | `/healthz/` | Health check. Returns `{"status": "ok"}`. Used by the Docker `HEALTHCHECK` and can be pointed at by an uptime monitor. |
| ANY | `/admin/` | Django admin console — full CRUD on every model for Dime staff during M1 (manual record creation before self-service exists). |

## M-Pesa Webhooks (`/webhooks/mpesa/...`)

Kept on a separate path group so host Nginx can apply a **stricter, distinct rate limit** from the rest of the API, per the design doc's reliability requirements. All handlers must be idempotent — dedupe on Safaricom's `TransactionID`/`ConversationID` via a DB unique constraint before any side effect runs.

| Method | Path | Purpose | Status |
|---|---|---|---|
| POST | `/webhooks/mpesa/c2b/validation/` | Safaricom calls this before accepting a C2B payment, to optionally reject it (e.g. unknown account reference). | Stub — always accept for now |
| POST | `/webhooks/mpesa/c2b/confirmation/` | Safaricom calls this once a C2B payment is confirmed. Discriminates by `BusinessShortCode` to resolve which landlord it belongs to, then feeds `billing.tasks.ingest_c2b_confirmation`. | Stub — routes to task, real payload parsing pending M2 |
| POST | `/webhooks/mpesa/b2c/result/` | Safaricom calls this with the outcome of a B2C payout (Reseller/Investor disbursement). Should update the matching `Disbursement.status`/`mpesa_conversation_id`. | Stub — not yet wired to `Disbursement` |
| POST | `/webhooks/mpesa/b2c/timeout/` | Safaricom calls this if a B2C request times out without a result. Should trigger a retry/alert path. | Stub — no retry logic yet |

## Not yet built

- WhatsApp Cloud API webhook (inbound messages, delivery status) — planned for M3, alongside `integrations/whatsapp.py`.
- DRF REST endpoints for landlord/reseller/investor/caretaker dashboards — planned once M1's admin-console sign-off is confirmed and the dashboards move to self-service.
- Nightly reconciliation and payout-sweep tasks (`billing.tasks.reconcile_all_landlords`, `partners.tasks.sweep_reseller_payouts`, `partners.tasks.sweep_investor_payouts`) are Celery tasks, not HTTP endpoints — triggered by Celery Beat on a schedule once wired in M2/M4.
