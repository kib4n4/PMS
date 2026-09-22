import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";
import { setAuthCookies } from "@/lib/auth-cookies";
import { authHeaders, resolveAccessToken, safeJson } from "@/lib/authenticated-backend-fetch";

type OnboardingQueueItem = { landlord_id: string; landlord_name: string; shortcode: string; status: string; updated_at: string };
type AuditLogEntry = {
  action: string;
  actor: string | null;
  target_object_type: string;
  target_object_id: string;
  reason: string;
  created_at: string;
};

type AdminOverviewResponse = {
  total_users: number;
  active_landlords: number;
  pending_onboarding: number;
  open_maintenance_tickets: number;
  users_by_role: Record<string, number>;
  landlords_by_onboarding_status: Record<string, number>;
  onboarding_queue: OnboardingQueueItem[];
  recent_audit_log: AuditLogEntry[];
};

/** GET /api/dashboard/admin — shapes /api/admin/overview/. No "System
 * Health"/uptime/latency metrics here (this app doesn't track any of
 * that) — replaced with real platform figures: role/onboarding-status
 * breakdowns, the actual onboarding queue, and the real audit log. */
export async function GET(request: NextRequest) {
  const auth = await resolveAccessToken(request);
  if (!auth) {
    return NextResponse.json({ detail: "Not authenticated." }, { status: 401 });
  }

  const backendResponse = await backendFetch("/api/admin/overview/", { headers: authHeaders(auth.accessToken) });
  if (!backendResponse.ok) {
    return NextResponse.json({ detail: "Failed to load admin overview." }, { status: backendResponse.status });
  }
  const overview = await safeJson<AdminOverviewResponse>(backendResponse, {
    total_users: 0,
    active_landlords: 0,
    pending_onboarding: 0,
    open_maintenance_tickets: 0,
    users_by_role: {},
    landlords_by_onboarding_status: {},
    onboarding_queue: [],
    recent_audit_log: [],
  });

  const payload = {
    kpis: {
      totalUsers: overview.total_users,
      activeLandlords: overview.active_landlords,
      pendingOnboarding: overview.pending_onboarding,
      openMaintenanceTickets: overview.open_maintenance_tickets,
    },
    usersByRole: overview.users_by_role,
    landlordsByStatus: overview.landlords_by_onboarding_status,
    onboardingQueue: overview.onboarding_queue.map((item) => ({
      landlord: item.landlord_name,
      shortcode: item.shortcode,
      status: item.status,
      date: item.updated_at.slice(0, 10),
    })),
    recentAuditLog: overview.recent_audit_log.map((entry) => ({
      action: entry.action,
      actor: entry.actor ?? "System",
      target: `${entry.target_object_type}:${entry.target_object_id}`,
      reason: entry.reason,
      time: formatRelativeTime(entry.created_at),
    })),
  };

  const response = NextResponse.json(payload);
  if (auth.refreshedTokens) {
    setAuthCookies(response, auth.refreshedTokens.access, auth.refreshedTokens.refresh);
  }
  return response;
}

function formatRelativeTime(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const hours = Math.floor(ms / (1000 * 60 * 60));
  if (hours < 1) return "<1h ago";
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}
