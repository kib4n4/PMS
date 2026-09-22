"use client";

import { cn } from "@/lib/utils";

import DashboardLayout from "@/components/DashboardLayout";
import KPICard from "@/components/KPICard";
import ChartCard from "@/components/ChartCard";
import DashedRule from "@/components/DashedRule";
import DataTable from "@/components/DataTable";
import {
  BuildingIcon,
  UsersIcon,
  ShieldIcon,
  TrendingUpIcon,
  XCircleIcon,
  CheckCircleIcon,
  ClockIcon,
} from "@/components/Icons";

const kpis = [
  {
    title: "Total Users",
    value: 156,
    subtitle: "12 new this week",
    trend: { value: 4.2, label: "vs last week" },
    accent: "blue" as const,
    icon: <UsersIcon className="h-6 w-6" />,
  },
  {
    title: "Active Landlords",
    value: 24,
    subtitle: "3 pending onboarding",
    trend: { value: 8.3, label: "vs last month" },
    accent: "emerald" as const,
    icon: <BuildingIcon className="h-6 w-6" />,
  },
  {
    title: "System Health",
    value: "99.8%",
    subtitle: "Last 30 days uptime",
    trend: { value: 0.1, label: "vs last month" },
    accent: "emerald" as const,
    icon: <ShieldIcon className="h-6 w-6" />,
  },
  {
    title: "Pending Reviews",
    value: 5,
    subtitle: "2 onboarding, 3 payouts",
    trend: { value: -2, label: "vs yesterday" },
    accent: "amber" as const,
    icon: <ClockIcon className="h-6 w-6" />,
  },
];

const onboardingQueue = [
  { landlord: "Sunrise Estates", shortcode: "174379", status: "Awaiting C2B URL", date: "2026-08-15", assignedTo: "Admin" },
  { landlord: "Greenview Homes", shortcode: "174380", status: "Sandbox Testing", date: "2026-08-12", assignedTo: "Admin" },
  { landlord: "Lakeside Apartments", shortcode: "174381", status: "Pending", date: "2026-08-10", assignedTo: "Unassigned" },
];

const recentAuditLogs = [
  { action: "force_disbursement", actor: "admin@dime.co.ke", target: "Disbursement:123", time: "2h ago", reason: "Payout delayed by B2C timeout" },
  { action: "adjust_fee_ledger_entry", actor: "admin@dime.co.ke", target: "FeeLedgerEntry:456", time: "5h ago", reason: "Corrected rounding error in platform fee" },
  { action: "mark_payment_resolved", actor: "admin@dime.co.ke", target: "Payment:789", time: "1d ago", reason: "Manual resolution after Safaricom retry" },
];

const systemMetrics = [
  { metric: "API Uptime", value: "99.98%", trend: "up" },
  { metric: "Avg Response Time", value: "142ms", trend: "down" },
  { metric: "Celery Workers", value: "4/4", trend: "stable" },
  { metric: "DB Connections", value: "12/50", trend: "stable" },
  { metric: "Redis Hit Rate", value: "94.2%", trend: "up" },
  { metric: "Webhook Success", value: "99.1%", trend: "stable" },
];

const onboardingPill = {
  Live: "bg-teal-100 text-teal-800",
  "Sandbox Testing": "bg-teal-100 text-teal-800",
  "Awaiting C2B URL": "bg-amber-100 text-amber-800",
  Pending: "bg-amber-100 text-amber-800",
};

export default function AdminDashboard() {
  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-ink-900">Admin Console</h1>
          <p className="mt-1 text-sm text-ink-600">Platform operations, onboarding, and system health.</p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {kpis.map((kpi) => (
            <KPICard key={kpi.title} {...kpi} />
          ))}
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <ChartCard title="System Metrics" className="lg:col-span-2">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              {systemMetrics.map((m) => (
                <div key={m.metric} className="rounded-lg border border-border p-4">
                  <p className="text-sm text-ink-600">{m.metric}</p>
                  <p className="mt-1 font-mono text-xl font-bold text-ink-900 tabular-nums">{m.value}</p>
                  <div className="mt-2 flex items-center gap-1 text-xs">
                    {m.trend === "up" && <TrendingUpIcon className="h-3 w-3 text-teal-600" />}
                    {m.trend === "down" && <XCircleIcon className="h-3 w-3 text-rust-600" />}
                    {m.trend === "stable" && <CheckCircleIcon className="h-3 w-3 text-ink-500" />}
                    <span
                      className={cn(
                        m.trend === "up"
                          ? "text-teal-600"
                          : m.trend === "down"
                          ? "text-rust-600"
                          : "text-ink-500",
                      )}
                    >
                      {m.trend === "up" ? "Healthy" : m.trend === "down" ? "Degraded" : "Stable"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </ChartCard>
          <ChartCard title="Onboarding Queue">
            <div className="space-y-3">
              {onboardingQueue.map((item) => (
                <div key={item.landlord} className="rounded-lg border border-border p-3">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-ink-900">{item.landlord}</p>
                    <span className="text-xs text-ink-500">{item.shortcode}</span>
                  </div>
                  <div className="mt-2 flex items-center justify-between">
                    <span
                      className={cn(
                        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                        onboardingPill[item.status as keyof typeof onboardingPill] ?? "bg-mist-100/70 text-ink-700"
                      )}
                    >
                      {item.status}
                    </span>
                    <span className="text-xs text-ink-500">{item.date}</span>
                  </div>
                </div>
              ))}
            </div>
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
            data={recentAuditLogs}
          />
        </ChartCard>
      </div>
    </DashboardLayout>
  );
}
