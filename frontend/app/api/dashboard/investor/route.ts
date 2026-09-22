import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";
import { setAuthCookies } from "@/lib/auth-cookies";
import { authHeaders, resolveAccessToken, safeJson } from "@/lib/authenticated-backend-fetch";
import { groupByMonth } from "@/lib/group-by-month";

type Disbursement = {
  id: string;
  amount: string;
  status: "pending" | "sent" | "confirmed" | "failed";
  mpesa_conversation_id: string;
  created_at: string;
};

type RevenueShareAgreement = {
  id: string;
  organization: string | null;
  organization_name: string | null;
  basis: "gross_fee_revenue" | "net_profit";
  rate_percent: string;
  payout_cadence: "monthly" | "quarterly";
  effective_start: string;
  effective_end: string | null;
};

type InvestorMeResponse = {
  id: string;
  full_name: string;
  agreements: RevenueShareAgreement[];
  disbursements: Disbursement[];
};

/** GET /api/dashboard/investor — shapes /api/partners/investors/me/ into
 * what the investor dashboard page needs. No mock data anywhere here. */
export async function GET(request: NextRequest) {
  const auth = await resolveAccessToken(request);
  if (!auth) {
    return NextResponse.json({ detail: "Not authenticated." }, { status: 401 });
  }

  const backendResponse = await backendFetch("/api/partners/investors/me/", {
    headers: authHeaders(auth.accessToken),
  });
  if (!backendResponse.ok) {
    return NextResponse.json({ detail: "Failed to load investor data." }, { status: backendResponse.status });
  }
  const me = await safeJson<InvestorMeResponse>(backendResponse, {
    id: "",
    full_name: "",
    agreements: [],
    disbursements: [],
  });

  const today = new Date();
  const isActive = (a: RevenueShareAgreement) => !a.effective_end || new Date(a.effective_end) > today;
  const activeAgreements = me.agreements.filter(isActive);

  const confirmed = me.disbursements.filter((d) => d.status === "confirmed");
  const pending = me.disbursements.filter((d) => d.status === "pending" || d.status === "sent");
  const sum = (rows: Disbursement[]) => rows.reduce((total, d) => total + Number(d.amount), 0);

  const avgRate =
    activeAgreements.length > 0
      ? activeAgreements.reduce((total, a) => total + Number(a.rate_percent), 0) / activeAgreements.length
      : 0;

  const payload = {
    kpis: {
      revenueShare: sum(confirmed),
      pendingPayout: sum(pending),
      activeAgreements: activeAgreements.length,
      avgRate,
    },
    agreements: me.agreements.map((a) => ({
      id: a.id,
      scope: a.organization_name ?? "Portfolio-wide",
      basis: a.basis === "net_profit" ? "Net Profit" : "Gross Fee Revenue",
      ratePercent: Number(a.rate_percent),
      cadence: a.payout_cadence === "monthly" ? "Monthly" : "Quarterly",
      start: a.effective_start,
      end: a.effective_end,
      active: isActive(a),
    })),
    disbursements: me.disbursements.map((d) => ({
      date: d.created_at.slice(0, 10),
      amount: Number(d.amount),
      status: d.status,
      txnId: d.mpesa_conversation_id || d.id.slice(0, 8),
    })),
    monthlyRevenue: groupByMonth(me.disbursements, 7),
  };

  const response = NextResponse.json(payload);
  if (auth.refreshedTokens) {
    setAuthCookies(response, auth.refreshedTokens.access, auth.refreshedTokens.refresh);
  }
  return response;
}
