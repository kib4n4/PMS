"use client";

import { cn } from "@/lib/utils";

import DashboardLayout from "@/components/DashboardLayout";
import KPICard from "@/components/KPICard";
import ChartCard from "@/components/ChartCard";
import DashedRule from "@/components/DashedRule";
import DataTable from "@/components/DataTable";
import {
  WrenchIcon,
  ClipboardListIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
} from "@/components/Icons";

const kpis = [
  {
    title: "Assigned Properties",
    value: 4,
    subtitle: "Across 3 estates",
    trend: { value: 0, label: "unchanged" },
    accent: "blue" as const,
    icon: <ClipboardListIcon className="h-6 w-6" />,
  },
  {
    title: "Open Tickets",
    value: 7,
    subtitle: "3 high priority",
    trend: { value: -3, label: "vs last week" },
    accent: "amber" as const,
    icon: <WrenchIcon className="h-6 w-6" />,
  },
  {
    title: "Avg Response Time",
    value: "2.4h",
    subtitle: "Target: < 4h",
    trend: { value: -12, label: "improved" },
    accent: "emerald" as const,
    icon: <ClockIcon className="h-6 w-6" />,
  },
  {
    title: "Resolution Rate",
    value: "94%",
    subtitle: "First-time fix",
    trend: { value: 2.1, label: "vs last month" },
    accent: "emerald" as const,
    icon: <CheckCircleIcon className="h-6 w-6" />,
  },
];

const ticketQueue = [
  { id: "TKT-301", unit: "A12", category: "Plumbing", priority: "High", status: "Open", tenant: "Jane Mwangi", age: "2h" },
  { id: "TKT-299", unit: "B04", category: "Electrical", priority: "Medium", status: "Assigned", tenant: "John Kamau", age: "4h" },
  { id: "TKT-295", unit: "C07", category: "Structural", priority: "High", status: "In Progress", tenant: "Grace Akinyi", age: "1d" },
  { id: "TKT-290", unit: "D11", category: "Plumbing", priority: "Low", status: "Resolved", tenant: "Sarah Wanjiku", age: "3d" },
  { id: "TKT-288", unit: "A12", category: "Electrical", priority: "Medium", status: "Reopened", tenant: "Jane Mwangi", age: "5d" },
];

const properties = [
  { name: "Sunrise Apartments", units: 24, tickets: 3, completed: 12 },
  { name: "Greenview Estate", units: 18, tickets: 2, completed: 8 },
  { name: "Lakeside Court", units: 12, tickets: 1, completed: 5 },
  { name: "Central Towers", units: 30, tickets: 1, completed: 15 },
];

const weeklyTickets = [
  { day: "Mon", count: 3 },
  { day: "Tue", count: 5 },
  { day: "Wed", count: 2 },
  { day: "Thu", count: 4 },
  { day: "Fri", count: 6 },
  { day: "Sat", count: 1 },
  { day: "Sun", count: 2 },
];

const priorityPill = {
  High: "bg-rust-100 text-rust-800",
  Medium: "bg-amber-100 text-amber-800",
  Low: "bg-mist-100/70 text-ink-700",
};

const statusPill = {
  Open: "bg-amber-100 text-amber-800",
  Assigned: "bg-teal-100 text-teal-800",
  "In Progress": "bg-amber-100 text-amber-800",
  Resolved: "bg-teal-100 text-teal-800",
  Reopened: "bg-rust-100 text-rust-800",
};

export default function CaretakerDashboard() {
  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-ink-900">Caretaker Dashboard</h1>
          <p className="mt-1 text-sm text-ink-600">Assigned properties, ticket queue, and resolution tracking.</p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {kpis.map((kpi) => (
            <KPICard key={kpi.title} {...kpi} />
          ))}
        </div>

        <DashedRule />

        <div className="grid gap-6 lg:grid-cols-3">
          <ChartCard title="Weekly Ticket Volume" className="lg:col-span-2">
            <WeeklyChart data={weeklyTickets} />
          </ChartCard>
          <ChartCard title="Assigned Properties">
            <div className="space-y-3">
              {properties.map((p) => (
                <div key={p.name} className="flex items-center justify-between rounded-lg border border-border p-3">
                  <div>
                    <p className="text-sm font-medium text-ink-900">{p.name}</p>
                    <p className="text-xs text-ink-600">{p.units} units</p>
                  </div>
                  <div className="text-right">
                    <p className="font-mono text-sm font-medium text-ink-900 tabular-nums">{p.tickets} open</p>
                    <p className="text-xs text-ink-600">{p.completed} resolved</p>
                  </div>
                </div>
              ))}
            </div>
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
                key: "priority",
                header: "Priority",
                render: (row: typeof ticketQueue[0]) => (
                  <span
                    className={cn(
                      "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                      priorityPill[row.priority as keyof typeof priorityPill]
                    )}
                  >
                    {row.priority}
                  </span>
                ),
              },
              {
                key: "status",
                header: "Status",
                render: (row: typeof ticketQueue[0]) => {
                  const icons: Record<string, React.ReactNode> = {
                    Open: <ClockIcon className="h-3 w-3" />,
                    Assigned: <ClipboardListIcon className="h-3 w-3" />,
                    "In Progress": <WrenchIcon className="h-3 w-3" />,
                    Resolved: <CheckCircleIcon className="h-3 w-3" />,
                    Reopened: <XCircleIcon className="h-3 w-3" />,
                  };
                  const style = statusPill[row.status as keyof typeof statusPill];
                  return (
                    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium", style)}>
                      {icons[row.status]}
                      {row.status}
                    </span>
                  );
                },
              },
              { key: "age", header: "Age" },
            ]}
            data={ticketQueue}
          />
        </ChartCard>
      </div>
    </DashboardLayout>
  );
}

function WeeklyChart({ data }: { data: { day: string; count: number }[] }) {
  const max = Math.max(...data.map((d) => d.count));
  return (
    <div className="h-64 w-full">
      <div className="flex h-full items-end gap-2">
        {data.map((d) => (
          <div key={d.day} className="flex flex-1 flex-col items-center gap-1">
            <div
              className="w-full rounded-t bg-amber-500 transition-all hover:bg-amber-600"
              style={{ height: `${(d.count / max) * 100}%` }}
              title={`${d.count} tickets`}
            />
            <span className="text-xs text-ink-500">{d.day}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
