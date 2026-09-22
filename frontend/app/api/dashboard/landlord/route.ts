import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";
import { setAuthCookies } from "@/lib/auth-cookies";
import { authHeaders, resolveAccessToken, safeJson } from "@/lib/authenticated-backend-fetch";

type Unit = { id: string; label: string; status: "vacant" | "occupied" | "maintenance" };
type Property = { id: string; name: string; address: string; units: Unit[]; created_at: string };
type Payment = {
  id: string;
  invoice_reference: string;
  tenant_name: string;
  unit_label: string;
  amount: string;
  mpesa_transaction_id: string;
  received_at: string;
};
type MaintenanceTicket = {
  id: string;
  unit_label: string;
  category: string;
  status: string;
  caretaker_name: string | null;
  created_at: string;
};
type FeeLedgerEntry = { id: string; platform_fee_amount: string; created_at: string };

/** GET /api/dashboard/landlord — combines /api/properties/,
 * /api/billing/payments/, /api/maintenance/tickets/, and
 * /api/billing/fee-ledger-entries/ (all already scoped to this landlord
 * by the backend) into what the landlord dashboard needs. No mock data. */
export async function GET(request: NextRequest) {
  const auth = await resolveAccessToken(request);
  if (!auth) {
    return NextResponse.json({ detail: "Not authenticated." }, { status: 401 });
  }
  const headers = authHeaders(auth.accessToken);

  const [propertiesRes, paymentsRes, ticketsRes, feesRes] = await Promise.all([
    backendFetch("/api/properties/", { headers }),
    backendFetch("/api/billing/payments/", { headers }),
    backendFetch("/api/maintenance/tickets/", { headers }),
    backendFetch("/api/billing/fee-ledger-entries/", { headers }),
  ]);

  const properties = await safeJson<Property[]>(propertiesRes, []);
  const payments = await safeJson<Payment[]>(paymentsRes, []);
  const tickets = await safeJson<MaintenanceTicket[]>(ticketsRes, []);
  const feeEntries = await safeJson<FeeLedgerEntry[]>(feesRes, []);

  const units = properties.flatMap((p) => p.units);
  const occupied = units.filter((u) => u.status === "occupied").length;
  const vacant = units.filter((u) => u.status === "vacant").length;
  const maintenance = units.filter((u) => u.status === "maintenance").length;

  const now = new Date();
  const isThisMonth = (iso: string) => {
    const d = new Date(iso);
    return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth();
  };
  const revenueMtd = payments.filter((p) => isThisMonth(p.received_at)).reduce((t, p) => t + Number(p.amount), 0);
  const feesMtd = feeEntries.filter((f) => isThisMonth(f.created_at)).reduce((t, f) => t + Number(f.platform_fee_amount), 0);

  const openTickets = tickets.filter((t) => t.status !== "resolved");

  const payload = {
    kpis: {
      totalProperties: properties.length,
      totalUnits: units.length,
      occupiedUnits: occupied,
      revenueMtd,
      feesMtd,
      openTickets: openTickets.length,
    },
    occupancy: { occupied, vacant, maintenance, total: units.length },
    // Per-unit statuses (not just aggregate counts) — feeds the unit
    // tally grid visualization in place of a donut. Previously computed
    // and discarded; now passed through since the design plan's
    // occupancy treatment needs the real per-unit shape.
    unitStatuses: units.map((u) => u.status),
    monthlyData: groupRentAndFeesByMonth(payments, feeEntries, 7),
    recentPayments: payments.slice(0, 5).map((p) => ({
      id: p.mpesa_transaction_id || p.id.slice(0, 8),
      tenant: p.tenant_name,
      unit: p.unit_label,
      amount: Number(p.amount),
      date: p.received_at.slice(0, 10),
    })),
    maintenanceTickets: tickets.slice(0, 5).map((t) => ({
      id: t.id.slice(0, 8),
      unit: t.unit_label,
      category: t.category || "General",
      status: t.status,
      caretaker: t.caretaker_name ?? "Unassigned",
    })),
  };

  const response = NextResponse.json(payload);
  if (auth.refreshedTokens) {
    setAuthCookies(response, auth.refreshedTokens.access, auth.refreshedTokens.refresh);
  }
  return response;
}

function groupRentAndFeesByMonth(payments: Payment[], feeEntries: FeeLedgerEntry[], months: number) {
  const now = new Date();
  const buckets: { key: string; month: string; rent: number; fees: number }[] = [];
  for (let i = months - 1; i >= 0; i -= 1) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    buckets.push({ key: `${d.getFullYear()}-${d.getMonth()}`, month: d.toLocaleString("en-US", { month: "short" }), rent: 0, fees: 0 });
  }
  const keyOf = (iso: string) => {
    const d = new Date(iso);
    return `${d.getFullYear()}-${d.getMonth()}`;
  };
  for (const p of payments) {
    const bucket = buckets.find((b) => b.key === keyOf(p.received_at));
    if (bucket) bucket.rent += Number(p.amount);
  }
  for (const f of feeEntries) {
    const bucket = buckets.find((b) => b.key === keyOf(f.created_at));
    if (bucket) bucket.fees += Number(f.platform_fee_amount);
  }
  return buckets.map(({ month, rent, fees }) => ({ month, rent, fees }));
}
