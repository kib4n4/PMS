"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { formatKES } from "@/lib/format";
import { useDashboardData } from "@/lib/use-dashboard-data";

import DashboardLayout from "@/components/DashboardLayout";
import { DashboardLoading, DashboardError } from "@/components/DashboardState";
import KPICard from "@/components/KPICard";
import ChartCard from "@/components/ChartCard";
import DashedRule from "@/components/DashedRule";
import DataTable from "@/components/DataTable";
import { BuildingIcon, UsersIcon, TrendingUpIcon, WrenchIcon } from "@/components/Icons";

type PaymentRow = { id: string; tenant: string; unit: string; amount: number; date: string };
type TicketRow = { id: string; unit: string; category: string; status: string; caretaker: string };
type MonthPoint = { month: string; rent: number; fees: number };
type UnitStatus = "vacant" | "occupied" | "maintenance";

type LandlordDashboardData = {
  kpis: {
    totalProperties: number;
    totalUnits: number;
    occupiedUnits: number;
    revenueMtd: number;
    feesMtd: number;
    openTickets: number;
  };
  occupancy: { occupied: number; vacant: number; maintenance: number; total: number };
  unitStatuses: UnitStatus[];
  monthlyData: MonthPoint[];
  recentPayments: PaymentRow[];
  maintenanceTickets: TicketRow[];
};

const statusPill: Record<string, string> = {
  open: "bg-rust-100 text-rust-800",
  assigned: "bg-amber-100 text-amber-800",
  in_progress: "bg-amber-100 text-amber-800",
  resolved: "bg-teal-100 text-teal-800",
  reopened: "bg-rust-100 text-rust-800",
};

export default function LandlordDashboard() {
  const { data, isLoading, error } = useDashboardData<LandlordDashboardData>("/api/dashboard/landlord");

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="font-serif text-[28px] font-medium text-ink-900">Landlord Dashboard</h1>
          <p className="mt-1 text-sm text-ink-600">Overview of your properties, tenants, and revenue.</p>
        </div>

        {isLoading && <DashboardLoading />}
        {error && <DashboardError message={error} />}
        {data && <LandlordDashboardBody data={data} />}
      </div>
    </DashboardLayout>
  );
}

function LandlordDashboardBody({ data }: { data: LandlordDashboardData }) {
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <div className="sm:col-span-2">
          <KPICard
            variant="hero"
            title="Revenue this month"
            value={formatKES(data.kpis.revenueMtd)}
            subtitle={`Platform fee: ${formatKES(data.kpis.feesMtd)} stamped`}
            accent="emerald"
            icon={<TrendingUpIcon className="h-6 w-6" />}
          />
        </div>
        <KPICard
          title="Properties"
          value={data.kpis.totalProperties}
          subtitle={`${data.kpis.totalUnits} unit${data.kpis.totalUnits === 1 ? "" : "s"}`}
          accent="blue"
          icon={<BuildingIcon className="h-6 w-6" />}
        />
        <KPICard
          title="Occupied"
          value={`${data.kpis.occupiedUnits}/${data.kpis.totalUnits}`}
          accent="blue"
          icon={<UsersIcon className="h-6 w-6" />}
        />
        <KPICard title="Open tickets" value={data.kpis.openTickets} accent="rose" icon={<WrenchIcon className="h-6 w-6" />} />
      </div>

      <DashedRule />

      <div className="grid gap-6 lg:grid-cols-3">
        <ChartCard
          title="Revenue vs Platform Fees"
          description="Monthly — the fee is the thin cap, a small slice of rent collected"
          className="lg:col-span-2"
        >
          <RevenueChart data={data.monthlyData} />
        </ChartCard>
        <ChartCard title="Units" description={`${data.kpis.totalProperties} properties, ${data.kpis.totalUnits} total`}>
          <UnitTally statuses={data.unitStatuses} occupancy={data.occupancy} />
        </ChartCard>
      </div>

      <DashedRule />

      <div className="grid gap-6 lg:grid-cols-2">
        <ChartCard title="Recent Payments">
          <DataTable
            columns={[
              { key: "id", header: "Txn ID" },
              { key: "tenant", header: "Tenant" },
              { key: "unit", header: "Unit" },
              { key: "amount", header: "Amount", render: (row: PaymentRow) => formatKES(row.amount) },
              { key: "date", header: "Date" },
            ]}
            data={data.recentPayments}
            empty={<p className="text-sm">No payments recorded yet.</p>}
          />
        </ChartCard>

        <ChartCard title="Maintenance Tickets">
          <DataTable
            columns={[
              { key: "id", header: "Ticket" },
              { key: "unit", header: "Unit" },
              { key: "category", header: "Category" },
              {
                key: "status",
                header: "Status",
                render: (row: TicketRow) => (
                  <span
                    className={cn(
                      "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                      statusPill[row.status] ?? "bg-mist-100/70 text-ink-700"
                    )}
                  >
                    {row.status.replace("_", " ")}
                  </span>
                ),
              },
              { key: "caretaker", header: "Caretaker" },
            ]}
            data={data.maintenanceTickets}
            empty={<p className="text-sm">No maintenance tickets yet.</p>}
          />
        </ChartCard>
      </div>
    </>
  );
}

function RevenueChart({ data }: { data: MonthPoint[] }) {
  // The one deliberate motion moment for this view: bars grow from zero
  // on mount rather than appearing instantly.
  const [grown, setGrown] = useState(false);
  useEffect(() => {
    const t = requestAnimationFrame(() => setGrown(true));
    return () => cancelAnimationFrame(t);
  }, []);

  const maxTotal = Math.max(1, ...data.map((d) => d.rent + d.fees));

  return (
    <div className="h-64 w-full">
      <div className="flex h-full items-end gap-2">
        {data.map((d) => {
          const rentH = (d.rent / maxTotal) * 100;
          const feeH = Math.max(d.fees > 0 ? 3 : 0, (d.fees / maxTotal) * 100);
          return (
            <div key={d.month} className="flex flex-1 flex-col items-center gap-1">
              <div className="flex h-full w-full flex-col-reverse items-stretch overflow-hidden rounded-t">
                <div
                  className="w-full bg-teal-600 transition-[height] duration-700 ease-out"
                  style={{ height: grown ? `${rentH}%` : "0%" }}
                  title={`Rent: ${formatKES(d.rent)}`}
                />
                <div
                  className="w-full bg-gold-400 transition-[height] duration-700 ease-out"
                  style={{ height: grown ? `${feeH}%` : "0%", transitionDelay: "120ms" }}
                  title={`Platform fee: ${formatKES(d.fees)}`}
                />
              </div>
              <span className="text-xs text-ink-500">{d.month}</span>
            </div>
          );
        })}
      </div>
      <div className="mt-4 flex items-center justify-center gap-6 text-xs text-ink-600">
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 rounded-sm bg-teal-600" />
          <span>Rent collected</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 rounded-sm bg-gold-400" />
          <span>Platform fee</span>
        </div>
      </div>
    </div>
  );
}

const statusColor: Record<UnitStatus, string> = {
  occupied: "bg-teal-600",
  vacant: "bg-mist-300",
  maintenance: "bg-gold-500",
};

function UnitTally({ statuses, occupancy }: { statuses: UnitStatus[]; occupancy: { occupied: number; vacant: number; maintenance: number; total: number } }) {
  if (statuses.length === 0) {
    return <p className="text-sm text-ink-500">No units on record yet.</p>;
  }
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-8 gap-1.5 sm:grid-cols-10">
        {statuses.map((status, i) => (
          <span
            key={i}
            title={status}
            className={cn("aspect-square rounded-[2px]", statusColor[status])}
          />
        ))}
      </div>
      <div className="flex flex-col gap-2 text-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-[2px] bg-teal-600" />
            <span className="text-ink-600">Occupied</span>
          </div>
          <span className="font-medium tabular-nums text-ink-900">{occupancy.occupied}</span>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-[2px] bg-gold-500" />
            <span className="text-ink-600">Maintenance</span>
          </div>
          <span className="font-medium tabular-nums text-ink-900">{occupancy.maintenance}</span>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-[2px] bg-mist-300" />
            <span className="text-ink-600">Vacant</span>
          </div>
          <span className="font-medium tabular-nums text-ink-900">{occupancy.vacant}</span>
        </div>
      </div>
    </div>
  );
}
