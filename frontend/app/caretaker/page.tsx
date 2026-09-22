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
import { WrenchIcon, ClipboardListIcon, ClockIcon, CheckCircleIcon, XCircleIcon } from "@/components/Icons";

type PropertyRow = { id: string; name: string; units: number; openTickets: number; resolvedTickets: number };
type TicketRow = { id: string; unit: string; tenant: string; category: string; status: string; age: string };
type DayPoint = { day: string; count: number };

type CaretakerDashboardData = {
  kpis: {
    assignedProperties: number;
    openTickets: number;
    avgResolutionHours: number | null;
    resolutionRate: number | null;
  };
  properties: PropertyRow[];
  weeklyTickets: DayPoint[];
  ticketQueue: TicketRow[];
};

const statusPill: Record<string, string> = {
  open: "bg-amber-100 text-amber-800",
  assigned: "bg-teal-100 text-teal-800",
  in_progress: "bg-amber-100 text-amber-800",
  resolved: "bg-teal-100 text-teal-800",
  reopened: "bg-rust-100 text-rust-800",
};

const statusIcon: Record<string, React.ReactNode> = {
  open: <ClockIcon className="h-3 w-3" />,
  assigned: <ClipboardListIcon className="h-3 w-3" />,
  in_progress: <WrenchIcon className="h-3 w-3" />,
  resolved: <CheckCircleIcon className="h-3 w-3" />,
  reopened: <XCircleIcon className="h-3 w-3" />,
};

export default function CaretakerDashboard() {
  const { data, isLoading, error } = useDashboardData<CaretakerDashboardData>("/api/dashboard/caretaker");

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="font-serif text-[28px] font-medium text-ink-900">Caretaker Dashboard</h1>
          <p className="mt-1 text-sm text-ink-600">Assigned properties, ticket queue, and resolution tracking.</p>
        </div>

        {isLoading && <DashboardLoading />}
        {error && <DashboardError message={error} />}
        {data && <CaretakerDashboardBody data={data} />}
      </div>
    </DashboardLayout>
  );
}

function CaretakerDashboardBody({ data }: { data: CaretakerDashboardData }) {
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <div className="sm:col-span-2">
          <KPICard
            variant="hero"
            title="Open tickets"
            value={data.kpis.openTickets}
            subtitle={`Across ${data.kpis.assignedProperties} assigned propert${data.kpis.assignedProperties === 1 ? "y" : "ies"}`}
            accent="amber"
            icon={<WrenchIcon className="h-6 w-6" />}
          />
        </div>
        <KPICard title="Assigned properties" value={data.kpis.assignedProperties} accent="blue" icon={<ClipboardListIcon className="h-6 w-6" />} />
        <KPICard
          title="Avg resolution time"
          value={data.kpis.avgResolutionHours === null ? "—" : `${data.kpis.avgResolutionHours.toFixed(1)}h`}
          subtitle="Report to resolved"
          accent="emerald"
          icon={<ClockIcon className="h-6 w-6" />}
        />
        <KPICard
          title="Resolution rate"
          value={data.kpis.resolutionRate === null ? "—" : `${Math.round(data.kpis.resolutionRate)}%`}
          accent="emerald"
          icon={<CheckCircleIcon className="h-6 w-6" />}
        />
      </div>

      <DashedRule />

      <div className="grid gap-6 lg:grid-cols-3">
        <ChartCard title="Weekly Ticket Volume" description="Tickets reported in the last 7 days" className="lg:col-span-2">
          <WeeklyChart data={data.weeklyTickets} />
        </ChartCard>
        <ChartCard title="Assigned Properties">
          {data.properties.length === 0 ? (
            <p className="text-sm text-ink-500">No active property assignments.</p>
          ) : (
            <div className="divide-y divide-dashed divide-border">
              {data.properties.map((p) => (
                <div key={p.id} className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-ink-900">{p.name}</p>
                    <p className="text-xs text-ink-600">{p.units} units</p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="text-sm font-medium tabular-nums text-ink-900">{p.openTickets} open</p>
                    <p className="text-xs text-ink-600">{p.resolvedTickets} resolved</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </ChartCard>
      </div>

      <ChartCard title="Ticket Queue">
        <DataTable
          columns={[
            { key: "id", header: "Ticket" },
            { key: "unit", header: "Unit" },
            { key: "tenant", header: "Tenant" },
            { key: "category", header: "Category" },
            {
              key: "status",
              header: "Status",
              render: (row: TicketRow) => (
                <span
                  className={cn(
                    "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium capitalize",
                    statusPill[row.status] ?? "bg-mist-100/70 text-ink-700"
                  )}
                >
                  {statusIcon[row.status]}
                  {row.status.replace("_", " ")}
                </span>
              ),
            },
            { key: "age", header: "Age" },
          ]}
          data={data.ticketQueue}
          empty={<p className="text-sm">No tickets assigned to you yet.</p>}
        />
      </ChartCard>
    </>
  );
}

function WeeklyChart({ data }: { data: DayPoint[] }) {
  // One deliberate motion moment for this view: bars grow on mount.
  const [grown, setGrown] = useState(false);
  useEffect(() => {
    const t = requestAnimationFrame(() => setGrown(true));
    return () => cancelAnimationFrame(t);
  }, []);
  const max = Math.max(1, ...data.map((d) => d.count));

  return (
    <div className="h-64 w-full">
      <div className="flex h-full items-end gap-2">
        {data.map((d) => (
          <div key={d.day} className="flex flex-1 flex-col items-center gap-1">
            <div
              className="w-full rounded-t bg-gold-500 transition-[height] duration-700 ease-out hover:bg-gold-600"
              style={{ height: grown ? `${(d.count / max) * 100}%` : "0%", minHeight: grown && d.count > 0 ? "2px" : "0" }}
              title={`${d.count} tickets`}
            />
            <span className="text-xs text-ink-500">{d.day}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
