import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";
import { setAuthCookies } from "@/lib/auth-cookies";
import { authHeaders, resolveAccessToken, safeJson } from "@/lib/authenticated-backend-fetch";
import { groupByMonth } from "@/lib/group-by-month";

type Disbursement = {
  id: string;
  recipient_type: "reseller" | "investor";
  amount: string;
  status: "pending" | "sent" | "confirmed" | "failed";
  mpesa_conversation_id: string;
  created_at: string;
};

type ReferredLandlord = { id: string; full_name: string; created_at: string };

type CommissionRule = {
  id: string;
  landlord: string;
  landlord_name: string;
  rate_percent: string;
  is_perpetual: boolean;
  expires_at: string | null;
};

type ResellerMeResponse = {
  id: string;
  full_name: string;
  referred_landlords: ReferredLandlord[];
  commission_rules: CommissionRule[];
  disbursements: Disbursement[];
};

/** GET /api/dashboard/reseller — shapes /api/partners/resellers/me/ into
 * what the reseller dashboard page needs (KPI numbers, a month-grouped
 * chart series). No mock data anywhere in this response. */
export async function GET(request: NextRequest) {
  const auth = await resolveAccessToken(request);
  if (!auth) {
    return NextResponse.json({ detail: "Not authenticated." }, { status: 401 });
  }

  const backendResponse = await backendFetch("/api/partners/resellers/me/", {
    headers: authHeaders(auth.accessToken),
  });
  if (!backendResponse.ok) {
    return NextResponse.json({ detail: "Failed to load reseller data." }, { status: backendResponse.status });
  }
  const me = await safeJson<ResellerMeResponse>(backendResponse, {
    id: "",
    full_name: "",
    referred_landlords: [],
    commission_rules: [],
    disbursements: [],
  });

  const confirmed = me.disbursements.filter((d) => d.status === "confirmed");
  const pending = me.disbursements.filter((d) => d.status === "pending" || d.status === "sent");
  const sum = (rows: Disbursement[]) => rows.reduce((total, d) => total + Number(d.amount), 0);

  const activeRules = me.commission_rules.filter((r) => r.is_perpetual || (r.expires_at && new Date(r.expires_at) > new Date()));
  const avgRate =
    activeRules.length > 0
      ? activeRules.reduce((total, r) => total + Number(r.rate_percent), 0) / activeRules.length
      : 0;

  const monthlyCommissions = groupByMonth(me.disbursements, 7);

  const payload = {
    kpis: {
      referredLandlords: me.referred_landlords.length,
      commissionEarned: sum(confirmed),
      pendingPayout: sum(pending),
      avgCommissionRate: avgRate,
    },
    referredLandlords: me.referred_landlords.map((landlord) => {
      const rule = me.commission_rules.find((r) => r.landlord === landlord.id);
      return {
        id: landlord.id,
        name: landlord.full_name,
        joined: landlord.created_at.slice(0, 10),
        ratePercent: rule ? Number(rule.rate_percent) : null,
        perpetual: rule ? rule.is_perpetual : null,
      };
    }),
    payoutHistory: me.disbursements.map((d) => ({
      date: d.created_at.slice(0, 10),
      amount: Number(d.amount),
      status: d.status,
      txnId: d.mpesa_conversation_id || d.id.slice(0, 8),
    })),
    monthlyCommissions,
    payoutStatus: { confirmed: sum(confirmed), pending: sum(pending) },
  };

  const response = NextResponse.json(payload);
  if (auth.refreshedTokens) {
    setAuthCookies(response, auth.refreshedTokens.access, auth.refreshedTokens.refresh);
  }
  return response;
}
