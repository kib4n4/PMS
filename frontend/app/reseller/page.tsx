"use client";

import { cn } from "@/lib/utils";

import DashboardLayout from "@/components/DashboardLayout";
import KPICard from "@/components/KPICard";
import ChartCard from "@/components/ChartCard";
import DashedRule from "@/components/DashedRule";
import DataTable from "@/components/DataTable";
import { UsersIcon, TrendingUpIcon, DollarSignIcon, PieChartIcon, CheckCircleIcon } from "@/components/Icons";

const kpis = [
  {
    title: "Referred Landlords",
    value: 24,
    subtitle: "8 active this month",
    trend: { value: 15.3, label: "vs last month" },
    accent: "blue" as const,
    icon: <UsersIcon className="h-6 w-6" />,
  },
  {
    title: "Commission Earned",
    value: "KES 84.5K",
    subtitle: "Lifetime: KES 420K",
    trend: { value: 22.1, label: "vs last month" },
    accent: "emerald" as const,
    icon: <TrendingUpIcon className="h-6 w-6" />,
  },
  {
    title: "Pending Payout",
    value: "KES 32K",
    subtitle: "Next sweep in 3 days",
    trend: { value: 8.4, label: "vs last payout" },
    accent: "amber" as const,
    icon: <DollarSignIcon className="h-6 w-6" />,
  },
  {
    title: "Avg Commission Rate",
    value: "10%",
    subtitle: "Of platform fee",
    trend: { value: 0, label: "unchanged" },
    accent: "blue" as const,
    icon: <PieChartIcon className="h-6 w-6" />,
  },
];

const referredLandlords = [
  { name: "Sunrise Estates", joined: "2026-03-15", status: "Active", commission: "KES 45K", rate: "10%" },
  { name: "Greenview Homes", joined: "2026-04-02", status: "Active", commission: "KES 28.5K", rate: "10%" },
  { name: "Lakeside Apartments", joined: "2026-05-20", status: "Sandbox", commission: "KES 8K", rate: "10%" },
  { name: "Central Towers", joined: "2026-06-10", status: "Active", commission: "KES 3K", rate: "15%" },
];

const payoutHistory = [
  { date: "2026-07-01", amount: "KES 28.5K", status: "Confirmed", txnId: "TXN-PAY-001" },
  { date: "2026-06-01", amount: "KES 22K", status: "Confirmed", txnId: "TXN-PAY-002" },
  { date: "2026-05-01", amount: "KES 18K", status: "Confirmed", txnId: "TXN-PAY-003" },
  { date: "2026-04-01", amount: "KES 16K", status: "Confirmed", txnId: "TXN-PAY-004" },
];

const monthlyCommissions = [
  { month: "Jan", amount: 12 },
  { month: "Feb", amount: 15 },
  { month: "Mar", amount: 18 },
  { month: "Apr", amount: 16 },
  { month: "May", amount: 22 },
  { month: "Jun", amount: 28 },
  { month: "Jul", amount: 32 },
];

const statusPill = {
  Active: "bg-teal-100 text-teal-800",
  Sandbox: "bg-amber-100 text-amber-800",
  Confirmed: "bg-teal-100 text-teal-800",
};

export default function ResellerDashboard() {
  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-ink-900">Reseller Dashboard</h1>
          <p className="mt-1 text-sm text-ink-600">Track your referrals, commissions, and payout history.</p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {kpis.map((kpi) => (
            <KPICard key={kpi.title} {...kpi} />
          ))}
        </div>

        <DashedRule />

        <div className="grid gap-6 lg:grid-cols-3">
          <ChartCard title="Commission Trend" description="Monthly commissions earned (KES thousands)" className="lg:col-span-2">
            <CommissionChart data={monthlyCommissions} />
          </ChartCard>
          <ChartCard title="Payout Status">
            <div className="flex flex-col items-center justify-center gap-4">
              <div className="relative h-40 w-40">
                <svg viewBox="0 0 36 36" className="h-full w-full -rotate-90">
                  <circle cx="18" cy="18" r="15.915" fill="none" stroke="#cdd7d3" strokeWidth="3" />
                  <circle cx="18" cy="18" r="15.915" fill="none" stroke="#0F6B5C" strokeWidth="3" strokeDasharray="70 30" strokeLinecap="round" />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-2xl font-bold text-ink-900">KES 52K</span>
                  <span className="text-xs text-ink-600">Confirmed</span>
                </div>
              </div>
              <div className="flex w-full flex-col gap-2 text-sm">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="h-2 w-2 rounded-full bg-teal-500" />
                    <span className="text-ink-600">Confirmed</span>
                  </div>
                  <span className="font-mono font-medium text-ink-900 tabular-nums">KES 52K</span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="h-2 w-2 rounded-full bg-amber-500" />
                    <span className="text-ink-600">Pending</span>
                  </div>
                  <span className="font-mono font-medium text-ink-900 tabular-nums">KES 32K</span>
                </div>
              </div>
            </div>
          </ChartCard>
        </div>

        <DashedRule />

        <div className="grid gap-6 lg:grid-cols-2">
          <ChartCard title="Referred Landlords">
            <DataTable
              columns={[
                { key: "name", header: "Landlord" },
                { key: "joined", header: "Joined" },
                {
                  key: "status",
                  header: "Status",
                  render: (row: typeof referredLandlords[0]) => (
                    <span
                      className={cn(
                        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                        statusPill[row.status as keyof typeof statusPill] ?? "bg-mist-100/70 text-ink-700"
                      )}
                    >
                      {row.status}
                    </span>
                  ),
                },
                { key: "commission", header: "Commission" },
                { key: "rate", header: "Rate" },
              ]}
              data={referredLandlords}
            />
          </ChartCard>

          <ChartCard title="Payout History">
            <DataTable
              columns={[
                { key: "date", header: "Date" },
                { key: "amount", header: "Amount" },
                {
                  key: "status",
                  header: "Status",
                  render: (row: typeof payoutHistory[0]) => (
                    <span className="inline-flex items-center gap-1 rounded-full bg-teal-100 px-2 py-0.5 text-xs font-medium text-teal-800">
                      <CheckCircleIcon className="h-3 w-3" />
                      {row.status}
                    </span>
                  ),
                },
                { key: "txnId", header: "Txn ID" },
              ]}
              data={payoutHistory}
            />
          </ChartCard>
        </div>
      </div>
    </DashboardLayout>
  );
}

function CommissionChart({ data }: { data: { month: string; amount: number }[] }) {
  const max = Math.max(...data.map((d) => d.amount));
  return (
    <div className="h-64 w-full">
      <div className="flex h-full items-end gap-2">
        {data.map((d) => (
          <div key={d.month} className="flex flex-1 flex-col items-center gap-1">
            <div
              className="w-full rounded-t bg-gold-400 transition-all hover:bg-gold-500"
              style={{ height: `${(d.amount / max) * 100}%` }}
              title={`KES ${d.amount}K`}
            />
            <span className="text-xs text-ink-500">{d.month}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
