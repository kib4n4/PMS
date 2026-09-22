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
import { UsersIcon, TrendingUpIcon, DollarSignIcon, PieChartIcon, CheckCircleIcon, ClockIcon, XCircleIcon } from "@/components/Icons";

type ReferredLandlordRow = { id: string; name: string; joined: string; ratePercent: number | null; perpetual: boolean | null };
type PayoutRow = { date: string; amount: number; status: string; txnId: string };
type CommissionPoint = { month: string; amount: number };

type ResellerDashboardData = {
  kpis: { referredLandlords: number; commissionEarned: number; pendingPayout: number; avgCommissionRate: number };
  referredLandlords: ReferredLandlordRow[];
  payoutHistory: PayoutRow[];
  monthlyCommissions: CommissionPoint[];
  payoutStatus: { confirmed: number; pending: number };
};

const statusPill: Record<string, string> = {
  confirmed: "bg-teal-100 text-teal-800",
  sent: "bg-amber-100 text-amber-800",
  pending: "bg-amber-100 text-amber-800",
  failed: "bg-rust-100 text-rust-800",
};

export default function ResellerDashboard() {
  const { data, isLoading, error } = useDashboardData<ResellerDashboardData>("/api/dashboard/reseller");

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="font-serif text-[28px] font-medium text-ink-900">Reseller Dashboard</h1>
          <p className="mt-1 text-sm text-ink-600">Track your referrals, commissions, and payout history.</p>
        </div>

        {isLoading && <DashboardLoading />}
        {error && <DashboardError message={error} />}
        {data && <ResellerDashboardBody data={data} />}
      </div>
    </DashboardLayout>
  );
}

function ResellerDashboardBody({ data }: { data: ResellerDashboardData }) {
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <div className="sm:col-span-2">
          <KPICard
            variant="hero"
            title="Commission earned"
            value={formatKES(data.kpis.commissionEarned)}
            subtitle="Confirmed payouts to date"
            accent="emerald"
            icon={<TrendingUpIcon className="h-6 w-6" />}
          />
        </div>
        <KPICard title="Referred landlords" value={data.kpis.referredLandlords} accent="blue" icon={<UsersIcon className="h-6 w-6" />} />
        <KPICard title="Pending payout" value={formatKES(data.kpis.pendingPayout)} accent="amber" icon={<DollarSignIcon className="h-6 w-6" />} />
        <KPICard
          title="Avg commission rate"
          value={formatPercent(data.kpis.avgCommissionRate)}
          subtitle="Active rules"
          accent="blue"
          icon={<PieChartIcon className="h-6 w-6" />}
        />
      </div>

      <DashedRule />

      <div className="grid gap-6 lg:grid-cols-3">
        <ChartCard title="Commission Trend" description="Monthly confirmed + pending commissions" className="lg:col-span-2">
          <CommissionChart data={data.monthlyCommissions} />
        </ChartCard>
        <ChartCard title="Payout Status">
          <PayoutStatusBar confirmed={data.payoutStatus.confirmed} pending={data.payoutStatus.pending} />
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
                key: "ratePercent",
                header: "Rate",
                render: (row: ReferredLandlordRow) => (row.ratePercent === null ? "—" : formatPercent(row.ratePercent)),
              },
              {
                key: "perpetual",
                header: "Duration",
                render: (row: ReferredLandlordRow) =>
                  row.perpetual === null ? "—" : row.perpetual ? "Perpetual" : "Time-boxed",
              },
            ]}
            data={data.referredLandlords}
            empty={<p className="text-sm">No landlords referred yet.</p>}
          />
        </ChartCard>

        <ChartCard title="Payout History">
          <DataTable
            columns={[
              { key: "date", header: "Date" },
              { key: "amount", header: "Amount", render: (row: PayoutRow) => formatKES(row.amount) },
              {
                key: "status",
                header: "Status",
                render: (row: PayoutRow) => (
                  <span
                    className={cn(
                      "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                      statusPill[row.status] ?? "bg-mist-100/70 text-ink-700"
                    )}
                  >
                    {row.status === "confirmed" && <CheckCircleIcon className="h-3 w-3" />}
                    {(row.status === "pending" || row.status === "sent") && <ClockIcon className="h-3 w-3" />}
                    {row.status === "failed" && <XCircleIcon className="h-3 w-3" />}
                    {row.status}
                  </span>
                ),
              },
              { key: "txnId", header: "Txn ID" },
            ]}
            data={data.payoutHistory}
            empty={<p className="text-sm">No payouts yet.</p>}
          />
        </ChartCard>
      </div>
    </>
  );
}

function CommissionChart({ data }: { data: { month: string; amount: number }[] }) {
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
              className="w-full rounded-t bg-gold-500 transition-[height] duration-700 ease-out hover:bg-gold-600"
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

function PayoutStatusBar({ confirmed, pending }: { confirmed: number; pending: number }) {
  const total = confirmed + pending;
  const confirmedPct = total > 0 ? (confirmed / total) * 100 : 0;
  const pendingPct = total > 0 ? (pending / total) * 100 : 0;

  return (
    <div className="flex flex-col justify-center gap-5">
      <div>
        <p className="font-serif text-2xl font-medium tabular-nums text-ink-900">{formatKES(confirmed)}</p>
        <p className="text-xs text-ink-600">confirmed of {formatKES(total)} total</p>
      </div>

      <div className="h-3 w-full overflow-hidden rounded-full bg-mist-200">
        {total > 0 && (
          <div className="flex h-full w-full">
            <div className="h-full bg-teal-600" style={{ width: `${confirmedPct}%` }} />
            <div className="h-full bg-gold-500" style={{ width: `${pendingPct}%` }} />
          </div>
        )}
      </div>

      <div className="flex flex-col gap-2 text-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-[2px] bg-teal-600" />
            <span className="text-ink-600">Confirmed ({confirmedPct.toFixed(0)}%)</span>
          </div>
          <span className="font-medium tabular-nums text-ink-900">{formatKES(confirmed)}</span>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-[2px] bg-gold-500" />
            <span className="text-ink-600">Pending ({pendingPct.toFixed(0)}%)</span>
          </div>
          <span className="font-medium tabular-nums text-ink-900">{formatKES(pending)}</span>
        </div>
      </div>
    </div>
  );
}
