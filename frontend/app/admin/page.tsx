"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { useDashboardData } from "@/lib/use-dashboard-data";

import DashboardLayout from "@/components/DashboardLayout";
import { DashboardLoading, DashboardError } from "@/components/DashboardState";
import KPICard from "@/components/KPICard";
import ChartCard from "@/components/ChartCard";
import DashedRule from "@/components/DashedRule";
import DataTable from "@/components/DataTable";
import { BuildingIcon, UsersIcon, WrenchIcon, ClockIcon } from "@/components/Icons";

type OnboardingRow = { landlord: string; shortcode: string; status: string; date: string };
type AuditLogRow = { action: string; actor: string; target: string; reason: string; time: string };

type AdminDashboardData = {
  kpis: { totalUsers: number; activeLandlords: number; pendingOnboarding: number; openMaintenanceTickets: number };
  usersByRole: Record<string, number>;
  landlordsByStatus: Record<string, number>;
  onboardingQueue: OnboardingRow[];
  recentAuditLog: AuditLogRow[];
};

const onboardingPill: Record<string, string> = {
  live: "bg-teal-100 text-teal-800",
  sandbox_testing: "bg-teal-100 text-teal-800",
  awaiting_c2b_url_registration: "bg-amber-100 text-amber-800",
  pending: "bg-amber-100 text-amber-800",
  suspended: "bg-rust-100 text-rust-800",
};

const roleLabels: Record<string, string> = {
  admin: "Admin", landlord: "Landlord", tenant: "Tenant",
  reseller: "Reseller", investor: "Investor", caretaker: "Caretaker",
};

function statusLabel(status: string): string {
  return status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function AdminDashboard() {
  const { data, isLoading, error } = useDashboardData<AdminDashboardData>("/api/dashboard/admin");

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="font-serif text-[28px] font-medium text-ink-900">Admin Console</h1>
          <p className="mt-1 text-sm text-ink-600">Platform operations, onboarding, and audit trail.</p>
        </div>

        {isLoading && <DashboardLoading />}
        {error && <DashboardError message={error} />}
        {data && <AdminDashboardBody data={data} />}
      </div>
    </DashboardLayout>
  );
}

function AdminDashboardBody({ data }: { data: AdminDashboardData }) {
  const roleEntries = Object.entries(data.usersByRole);

  // One deliberate motion moment for this view: role tiles stamp in
  // one-by-one rather than all appearing at once.
  const [stamped, setStamped] = useState(false);
  useEffect(() => {
    const t = requestAnimationFrame(() => setStamped(true));
    return () => cancelAnimationFrame(t);
  }, []);

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <div className="sm:col-span-2">
          <KPICard variant="hero" title="Total users" value={data.kpis.totalUsers} accent="blue" icon={<UsersIcon className="h-6 w-6" />} />
        </div>
        <KPICard title="Active landlords" value={data.kpis.activeLandlords} subtitle="Daraja: Live" accent="emerald" icon={<BuildingIcon className="h-6 w-6" />} />
        <KPICard title="Pending onboarding" value={data.kpis.pendingOnboarding} accent="amber" icon={<ClockIcon className="h-6 w-6" />} />
        <KPICard title="Open tickets" value={data.kpis.openMaintenanceTickets} subtitle="Platform-wide" accent="rose" icon={<WrenchIcon className="h-6 w-6" />} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <ChartCard title="Users by Role" className="lg:col-span-2">
          {roleEntries.length === 0 ? (
            <p className="text-sm text-ink-500">No users yet.</p>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {roleEntries.map(([role, count], i) => (
                <div
                  key={role}
                  className={cn(
                    "rounded-lg border border-border p-4 transition-all duration-400 ease-out",
                    stamped ? "translate-y-0 opacity-100" : "translate-y-1.5 opacity-0",
                  )}
                  style={{ transitionDelay: stamped ? `${i * 60}ms` : "0ms" }}
                >
                  <p className="text-sm text-ink-600">{roleLabels[role] ?? role}</p>
                  <p className="mt-1 font-serif text-2xl font-medium tabular-nums text-ink-900">{count}</p>
                </div>
              ))}
            </div>
          )}
        </ChartCard>
        <ChartCard title="Onboarding Queue">
          {data.onboardingQueue.length === 0 ? (
            <p className="text-sm text-ink-500">No landlords awaiting onboarding.</p>
          ) : (
            <div className="divide-y divide-dashed divide-border">
              {data.onboardingQueue.map((item) => (
                <div key={`${item.landlord}-${item.shortcode}`} className="py-3 first:pt-0 last:pb-0">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-ink-900">{item.landlord}</p>
                    <span className="text-xs text-ink-500">{item.shortcode}</span>
                  </div>
                  <div className="mt-1.5 flex items-center justify-between">
                    <span
                      className={cn(
                        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                        onboardingPill[item.status] ?? "bg-mist-100/70 text-ink-700"
                      )}
                    >
                      {statusLabel(item.status)}
                    </span>
                    <span className="text-xs text-ink-500">{item.date}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </ChartCard>
      </div>

      <DashedRule />

      <ChartCard title="Recent Audit Log">
        <DataTable
          columns={[
            { key: "action", header: "Action" },
            { key: "actor", header: "Actor" },
            { key: "target", header: "Target" },
            { key: "reason", header: "Reason" },
            { key: "time", header: "Time" },
          ]}
          data={data.recentAuditLog}
          empty={<p className="text-sm">No audit log entries yet.</p>}
        />
      </ChartCard>
    </>
  );
}
