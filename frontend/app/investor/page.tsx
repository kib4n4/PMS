"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { formatKES, formatPercent } from "@/lib/format";
import { useDashboardData } from "@/lib/use-dashboard-data";

import DashboardLayout from "@/components/DashboardLayout";
import { DashboardLoading, DashboardError } from "@/components/DashboardState";
import KPICard from "@/components/KPICard";
import ChartCard from "@/components/ChartCard";
import DashedRule from "@/components/DashedRule";
import DataTable from "@/components/DataTable";
import { TrendingUpIcon, DollarSignIcon, PieChartIcon, ClockIcon, CheckCircleIcon, XCircleIcon } from "@/components/Icons";

type Agreement = {
  id: string;
  scope: string;
  basis: string;
  ratePercent: number;
  cadence: string;
  start: string;
  end: string | null;
  active: boolean;
};
type DisbursementRow = { date: string; amount: number; status: string; txnId: string };
type RevenuePoint = { month: string; amount: number };

type InvestorDashboardData = {
  kpis: { revenueShare: number; pendingPayout: number; activeAgreements: number; avgRate: number };
  agreements: Agreement[];
  disbursements: DisbursementRow[];
  monthlyRevenue: RevenuePoint[];
};

const statusPill: Record<string, string> = {
  confirmed: "bg-teal-100 text-teal-800",
  sent: "bg-amber-100 text-amber-800",
  pending: "bg-amber-100 text-amber-800",
  failed: "bg-rust-100 text-rust-800",
};

export default function InvestorDashboard() {
  const { data, isLoading, error } = useDashboardData<InvestorDashboardData>("/api/dashboard/investor");

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="font-serif text-[28px] font-medium text-ink-900">Investor Dashboard</h1>
          <p className="mt-1 text-sm text-ink-600">Revenue share, agreements, and payout tracking.</p>
        </div>

        {isLoading && <DashboardLoading />}
        {error && <DashboardError message={error} />}
        {data && <InvestorDashboardBody data={data} />}
      </div>
    </DashboardLayout>
  );
}

function InvestorDashboardBody({ data }: { data: InvestorDashboardData }) {
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <div className="sm:col-span-2">
          <KPICard
            variant="hero"
            title="Revenue share"
            value={formatKES(data.kpis.revenueShare)}
            subtitle="Confirmed payouts to date"
            accent="emerald"
            icon={<TrendingUpIcon className="h-6 w-6" />}
          />
        </div>
        <KPICard title="Pending payout" value={formatKES(data.kpis.pendingPayout)} accent="amber" icon={<DollarSignIcon className="h-6 w-6" />} />
        <KPICard title="Active agreements" value={data.kpis.activeAgreements} accent="blue" icon={<PieChartIcon className="h-6 w-6" />} />
        <KPICard
          title="Avg share rate"
          value={formatPercent(data.kpis.avgRate)}
          subtitle="Active agreements"
          accent="blue"
          icon={<ClockIcon className="h-6 w-6" />}
        />
      </div>

      <DashedRule />

      <div className="grid gap-6 lg:grid-cols-3">
        <ChartCard title="Revenue Share Trend" description="Monthly confirmed + pending disbursements" className="lg:col-span-2">
          <RevenueChart data={data.monthlyRevenue} />
        </ChartCard>
        <ChartCard title="Agreement Summary">
          {data.agreements.length === 0 ? (
            <p className="text-sm text-ink-500">No revenue-share agreements yet.</p>
          ) : (
            <div className="divide-y divide-dashed divide-border">
              {data.agreements.map((a) => (
                <div key={a.id} className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-ink-900">{a.scope}</p>
                    <p className="text-xs text-ink-600">
                      {a.basis} · {formatPercent(a.ratePercent)} · {a.cadence}
                    </p>
                  </div>
                  <span
                    className={cn(
                      "shrink-0 text-xs font-medium",
                      a.active ? "text-teal-700" : "text-ink-400",
                    )}
                  >
                    {a.active ? "Active" : "Ended"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </ChartCard>
      </div>

      <DashedRule />

      <div className="grid gap-6 lg:grid-cols-2">
        <ChartCard title="Active Agreements">
          <DataTable
            columns={[
              { key: "scope", header: "Scope" },
              { key: "basis", header: "Basis" },
              { key: "ratePercent", header: "Rate", render: (row: Agreement) => formatPercent(row.ratePercent) },
              { key: "cadence", header: "Cadence" },
              { key: "start", header: "Start" },
            ]}
            data={data.agreements}
            empty={<p className="text-sm">No agreements yet.</p>}
          />
        </ChartCard>

        <ChartCard title="Disbursement History">
          <DataTable
            columns={[
              { key: "date", header: "Date" },
              { key: "amount", header: "Amount", render: (row: DisbursementRow) => formatKES(row.amount) },
              {
                key: "status",
                header: "Status",
                render: (row: DisbursementRow) => (
                  <span
                    className={cn(
                      "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                      statusPill[row.status] ?? "bg-mist-100/70 text-ink-700"
                    )}
                  >
                    {row.status === "confirmed" && <CheckCircleIcon className="h-3 w-3" />}
                    {row.status === "failed" && <XCircleIcon className="h-3 w-3" />}
                    {row.status}
                  </span>
                ),
              },
              { key: "txnId", header: "Txn ID" },
            ]}
            data={data.disbursements}
            empty={<p className="text-sm">No disbursements yet.</p>}
          />
        </ChartCard>
      </div>
    </>
  );
}

function RevenueChart({ data }: { data: { month: string; amount: number }[] }) {
  // One deliberate motion moment for this view: bars grow on mount.
  const [grown, setGrown] = useState(false);
  useEffect(() => {
    const t = requestAnimationFrame(() => setGrown(true));
    return () => cancelAnimationFrame(t);
  }, []);
  const max = Math.max(1, ...data.map((d) => d.amount));

  return (
    <div className="h-64 w-full">
      <div className="flex h-full items-end gap-2">
        {data.map((d) => (
          <div key={d.month} className="flex flex-1 flex-col items-center gap-1">
            <div
              className="w-full rounded-t bg-teal-600 transition-[height] duration-700 ease-out hover:bg-teal-700"
              style={{ height: grown ? `${(d.amount / max) * 100}%` : "0%", minHeight: grown && d.amount > 0 ? "2px" : "0" }}
              title={formatKES(d.amount)}
            />
            <span className="text-xs text-ink-500">{d.month}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
