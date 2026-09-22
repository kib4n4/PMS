"use client";

import { cn } from "@/lib/utils";

import DashboardLayout from "@/components/DashboardLayout";
import KPICard from "@/components/KPICard";
import ChartCard from "@/components/ChartCard";
import DashedRule from "@/components/DashedRule";
import DataTable from "@/components/DataTable";
import {
  TrendingUpIcon,
  DollarSignIcon,
  PieChartIcon,
  ClockIcon,
  CheckCircleIcon,
} from "@/components/Icons";

const kpis = [
  {
    title: "Revenue Share",
    value: "KES 156K",
    subtitle: "Portfolio-wide",
    trend: { value: 18.2, label: "vs last quarter" },
    accent: "emerald" as const,
    icon: <TrendingUpIcon className="h-6 w-6" />,
  },
  {
    title: "Pending Payout",
    value: "KES 45K",
    subtitle: "Next disbursement in 5 days",
    trend: { value: 5.6, label: "vs last quarter" },
    accent: "amber" as const,
    icon: <DollarSignIcon className="h-6 w-6" />,
  },
  {
    title: "Active Agreements",
    value: 3,
    subtitle: "2 portfolio-wide, 1 org-specific",
    trend: { value: 0, label: "unchanged" },
    accent: "blue" as const,
    icon: <PieChartIcon className="h-6 w-6" />,
  },
  {
    title: "Next Disbursement",
    value: "Aug 31",
    subtitle: "KES 45K scheduled",
    trend: { value: 0, label: "on track" },
    accent: "blue" as const,
    icon: <ClockIcon className="h-6 w-6" />,
  },
];

const agreements = [
  { investor: "Alice Muthoni", basis: "Net Profit", rate: "5%", scope: "Portfolio-wide", cadence: "Monthly", start: "2026-01-01", end: "2027-01-01" },
  { investor: "Alice Muthoni", basis: "Gross Fee Revenue", rate: "3%", scope: "Dime Consultants", cadence: "Quarterly", start: "2026-01-01", end: null },
  { investor: "Bob Ochieng", basis: "Net Profit", rate: "8%", scope: "Portfolio-wide", cadence: "Monthly", start: "2025-06-01", end: "2026-06-01" },
];

const disbursements = [
  { date: "2026-07-31", amount: "KES 42K", status: "Confirmed", txnId: "TXN-DISB-001", recipient: "Alice Muthoni" },
  { date: "2026-06-30", amount: "KES 38K", status: "Confirmed", txnId: "TXN-DISB-002", recipient: "Alice Muthoni" },
  { date: "2026-05-31", amount: "KES 35K", status: "Confirmed", txnId: "TXN-DISB-003", recipient: "Alice Muthoni" },
  { date: "2026-04-30", amount: "KES 31K", status: "Confirmed", txnId: "TXN-DISB-004", recipient: "Alice Muthoni" },
];

const quarterlyRevenue = [
  { quarter: "Q1 2025", amount: 85 },
  { quarter: "Q2 2025", amount: 102 },
  { quarter: "Q3 2025", amount: 118 },
  { quarter: "Q4 2025", amount: 134 },
  { quarter: "Q1 2026", amount: 145 },
  { quarter: "Q2 2026", amount: 156 },
];

export default function InvestorDashboard() {
  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-ink-900">Investor Dashboard</h1>
          <p className="mt-1 text-sm text-ink-600">Revenue share, agreements, and payout tracking.</p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {kpis.map((kpi) => (
            <KPICard key={kpi.title} {...kpi} />
          ))}
        </div>

        <DashedRule />

        <div className="grid gap-6 lg:grid-cols-3">
          <ChartCard title="Revenue Share Trend" description="Quarterly earnings (KES thousands)" className="lg:col-span-2">
            <RevenueChart data={quarterlyRevenue} />
          </ChartCard>
          <ChartCard title="Agreement Summary">
            <div className="space-y-4">
              <div className="flex items-center justify-between rounded-lg bg-mist-50 p-4">
                <div>
                  <p className="text-sm font-medium text-ink-900">Portfolio-wide</p>
                  <p className="text-xs text-ink-600">Net Profit 5%</p>
                </div>
                <span className="text-sm font-semibold text-teal-600">Active</span>
              </div>
              <div className="flex items-center justify-between rounded-lg bg-mist-50 p-4">
                <div>
                  <p className="text-sm font-medium text-ink-900">Dime Consultants</p>
                  <p className="text-xs text-ink-600">Gross Fee 3%, Quarterly</p>
                </div>
                <span className="text-sm font-semibold text-teal-600">Active</span>
              </div>
              <div className="flex items-center justify-between rounded-lg bg-mist-50 p-4">
                <div>
                  <p className="text-sm font-medium text-ink-900">Expired Agreement</p>
                  <p className="text-xs text-ink-600">Ended 2026-06-01</p>
                </div>
                <span className="text-sm font-semibold text-ink-500">Ended</span>
              </div>
            </div>
          </ChartCard>
        </div>

        <DashedRule />

        <div className="grid gap-6 lg:grid-cols-2">
          <ChartCard title="Active Agreements">
            <DataTable
              columns={[
                { key: "investor", header: "Investor" },
                { key: "basis", header: "Basis" },
                { key: "rate", header: "Rate" },
                { key: "scope", header: "Scope" },
                { key: "cadence", header: "Cadence" },
                { key: "start", header: "Start" },
              ]}
              data={agreements}
            />
          </ChartCard>

          <ChartCard title="Disbursement History">
            <DataTable
              columns={[
                { key: "date", header: "Date" },
                { key: "recipient", header: "Recipient" },
                { key: "amount", header: "Amount" },
                {
                  key: "status",
                  header: "Status",
                  render: (row: typeof disbursements[0]) => (
                    <span className="inline-flex items-center gap-1 rounded-full bg-teal-100 px-2 py-0.5 text-xs font-medium text-teal-800">
                      <CheckCircleIcon className="h-3 w-3" />
                      {row.status}
                    </span>
                  ),
                },
                { key: "txnId", header: "Txn ID" },
              ]}
              data={disbursements}
            />
          </ChartCard>
        </div>
      </div>
    </DashboardLayout>
  );
}

function RevenueChart({ data }: { data: { quarter: string; amount: number }[] }) {
  const max = Math.max(...data.map((d) => d.amount));
  return (
    <div className="h-64 w-full">
      <div className="flex h-full items-end gap-2">
        {data.map((d) => (
          <div key={d.quarter} className="flex flex-1 flex-col items-center gap-1">
            <div
              className="w-full rounded-t bg-teal-500 transition-all hover:bg-teal-600"
              style={{ height: `${(d.amount / max) * 100}%` }}
              title={`KES ${d.amount}K`}
            />
            <span className="text-xs text-ink-500">{d.quarter}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
