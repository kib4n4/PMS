import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";
import { setAuthCookies } from "@/lib/auth-cookies";
import { authHeaders, resolveAccessToken, safeJson } from "@/lib/authenticated-backend-fetch";

type Unit = { id: string; label: string; status: string };
type Property = { id: string; name: string; address: string; units: Unit[] };
type Assignment = { id: string; property: Property; effective_start: string; effective_end: string | null };
type CaretakerMeResponse = { id: string; full_name: string; assignments: Assignment[] };

type MaintenanceTicket = {
  id: string;
  unit_label: string;
  property_name: string;
  tenant_name: string;
  category: string;
  status: string;
  created_at: string;
  resolved_at: string | null;
};

/** GET /api/dashboard/caretaker — combines /api/caretakers/me/ (assigned
 * properties) and /api/maintenance/tickets/ (already caretaker-scoped by
 * the backend). No "priority" or "avg response time" fields here — the
 * MaintenanceTicket model has no priority field and no first-response
 * timestamp, so the old mock's "High/Medium/Low" and "2.4h avg response"
 * were both invented; this uses only what's real (created_at/resolved_at). */
export async function GET(request: NextRequest) {
  const auth = await resolveAccessToken(request);
  if (!auth) {
    return NextResponse.json({ detail: "Not authenticated." }, { status: 401 });
  }
  const headers = authHeaders(auth.accessToken);

  const [meRes, ticketsRes] = await Promise.all([
    backendFetch("/api/caretakers/me/", { headers }),
    backendFetch("/api/maintenance/tickets/", { headers }),
  ]);

  const me = await safeJson<CaretakerMeResponse>(meRes, { id: "", full_name: "", assignments: [] });
  const tickets = await safeJson<MaintenanceTicket[]>(ticketsRes, []);

  const resolvedTickets = tickets.filter((t) => t.status === "resolved" && t.resolved_at);
  const openTickets = tickets.filter((t) => t.status !== "resolved");

  const resolutionHours = resolvedTickets.map(
    (t) => (new Date(t.resolved_at as string).getTime() - new Date(t.created_at).getTime()) / (1000 * 60 * 60)
  );
  const avgResolutionHours =
    resolutionHours.length > 0 ? resolutionHours.reduce((a, b) => a + b, 0) / resolutionHours.length : null;
  const resolutionRate = tickets.length > 0 ? (resolvedTickets.length / tickets.length) * 100 : null;

  const properties = me.assignments
    .filter((a) => !a.effective_end)
    .map((a) => {
      const propertyTickets = tickets.filter((t) => t.property_name === a.property.name);
      return {
        id: a.property.id,
        name: a.property.name,
        units: a.property.units.length,
        openTickets: propertyTickets.filter((t) => t.status !== "resolved").length,
        resolvedTickets: propertyTickets.filter((t) => t.status === "resolved").length,
      };
    });

  const payload = {
    kpis: {
      assignedProperties: properties.length,
      openTickets: openTickets.length,
      avgResolutionHours,
      resolutionRate,
    },
    properties,
    weeklyTickets: groupByDayOfWeek(tickets),
    ticketQueue: tickets.slice(0, 10).map((t) => ({
      id: t.id.slice(0, 8),
      unit: t.unit_label,
      tenant: t.tenant_name,
      category: t.category || "General",
      status: t.status,
      age: formatAge(t.created_at),
    })),
  };

  const response = NextResponse.json(payload);
  if (auth.refreshedTokens) {
    setAuthCookies(response, auth.refreshedTokens.access, auth.refreshedTokens.refresh);
  }
  return response;
}

function groupByDayOfWeek(tickets: { created_at: string }[]) {
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const counts = new Array(7).fill(0);
  const weekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
  for (const t of tickets) {
    const created = new Date(t.created_at);
    if (created.getTime() < weekAgo) continue;
    const jsDay = created.getDay(); // 0=Sun..6=Sat
    const index = jsDay === 0 ? 6 : jsDay - 1; // 0=Mon..6=Sun
    counts[index] += 1;
  }
  return days.map((day, i) => ({ day, count: counts[i] }));
}

function formatAge(createdAt: string): string {
  const ms = Date.now() - new Date(createdAt).getTime();
  const hours = Math.floor(ms / (1000 * 60 * 60));
  if (hours < 1) return "<1h";
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}
