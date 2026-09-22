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
  TrendingUpIcon,
  WrenchIcon,
} from "@/components/Icons";

const kpis = [
  {
    title: "Total Properties",
    value: 12,
    subtitle: "3 active listings",
    trend: { value: 8.2, label: "vs last month" },
    accent: "blue" as const,
    icon: <BuildingIcon className="h-6 w-6" />,
  },
  {
    title: "Occupied Units",
    value: 84,
    subtitle: "92% occupancy rate",
    trend: { value: 3.1, label: "vs last month" },
    accent: "emerald" as const,
    icon: <UsersIcon className="h-6 w-6" />,
  },
  {
    title: "Revenue (MTD)",
    value: "KES 2.4M",
    subtitle: "Platform fee: KES 120K",
    trend: { value: 12.5, label: "vs last month" },
    accent: "amber" as const,
    icon: <TrendingUpIcon className="h-6 w-6" />,
  },
  {
    title: "Open Tickets",
    value: 7,
    subtitle: "2 high priority",
    trend: { value: -2, label: "vs last week" },
    accent: "rose" as const,
    icon: <WrenchIcon className="h-6 w-6" />,
  },
];

const recentPayments = [
  { id: "TXN-001", tenant: "Jane Mwangi", unit: "A12", amount: "KES 45,000", date: "2026-08-19", status: "Confirmed" },
  { id: "TXN-002", tenant: "John Kamau", unit: "B04", amount: "KES 38,000", date: "2026-08-18", status: "Confirmed" },
  { id: "TXN-003", tenant: "Grace Akinyi", unit: "C07", amount: "KES 52,000", date: "2026-08-18", status: "Pending" },
  { id: "TXN-004", tenant: "David Otieno", unit: "A03", amount: "KES 40,000", date: "2026-08-17", status: "Confirmed" },
  { id: "TXN-005", tenant: "Sarah Wanjiku", unit: "D11", amount: "KES 35,000", date: "2026-08-16", status: "Confirmed" },
];

const maintenanceTickets = [
  { id: "TKT-301", unit: "A12", category: "Plumbing", priority: "High", status: "Open", caretaker: "Unassigned" },
  { id: "TKT-298", unit: "B04", category: "Electrical", priority: "Medium", status: "Assigned", caretaker: "James M." },
  { id: "TKT-295", unit: "C07", category: "Structural", priority: "High", status: "In Progress", caretaker: "Mary N." },
  { id: "TKT-290", unit: "D11", category: "Plumbing", priority: "Low", status: "Resolved", caretaker: "James M." },
];

const monthlyData = [
  { month: "Jan", rent: 1.8, fees: 90 },
  { month: "Feb", rent: 1.9, fees: 95 },
  { month: "Mar", rent: 2.1, fees: 105 },
  { month: "Apr", rent: 2.0, fees: 100 },
  { month: "May", rent: 2.2, fees: 110 },
  { month: "Jun", rent: 2.3, fees: 115 },
  { month: "Jul", rent: 2.4, fees: 120 },
];

const priorityPill = {
  High: "bg-rust-100 text-rust-800",
  Medium: "bg-amber-100 text-amber-800",
  Low: "bg-mist-100/70 text-ink-700",
};

export default function LandlordDashboard() {
  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-ink-900">Landlord Dashboard</h1>
          <p className="mt-1 text-sm text-ink-600">Overview of your properties, tenants, and revenue.</p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {kpis.map((kpi) => (
            <KPICard key={kpi.title} {...kpi} />
          ))}
        </div>

        <DashedRule />

        <div className="grid gap-6 lg:grid-cols-3">
          <ChartCard title="Revenue vs Platform Fees" description="Monthly trend (KES thousands)" className="lg:col-span-2">
            <RevenueChart data={monthlyData} />
          </ChartCard>
          <ChartCard title="Occupancy by Property">
            <OccupancyChart />
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
                { key: "amount", header: "Amount" },
                { key: "date", header: "Date" },
                {
                  key: "status",
                  header: "Status",
                  render: (row: typeof recentPayments[0]) => (
                    <span
                      className={cn(
                        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                        row.status === "Confirmed"
                          ? "bg-teal-100 text-teal-800"
                          : "bg-amber-100 text-amber-800"
                      )}
                    >
                      {row.status}
                    </span>
                  ),
                },
              ]}
              data={recentPayments}
            />
          </ChartCard>

          <ChartCard title="Maintenance Tickets">
            <DataTable
              columns={[
                { key: "id", header: "Ticket" },
                { key: "unit", header: "Unit" },
                { key: "category", header: "Category" },
                {
                  key: "priority",
                  header: "Priority",
                  render: (row: typeof maintenanceTickets[0]) => (
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
                { key: "status", header: "Status" },
                { key: "caretaker", header: "Caretaker" },
              ]}
              data={maintenanceTickets}
            />
          </ChartCard>
        </div>
      </div>
    </DashboardLayout>
  );
}

function RevenueChart({ data }: { data: { month: string; rent: number; fees: number }[] }) {
  const maxRent = Math.max(...data.map((d) => d.rent));
  return (
    <div className="h-64 w-full">
      <div className="flex h-full items-end gap-2">
        {data.map((d) => (
          <div key={d.month} className="flex flex-1 flex-col items-center gap-1">
            <div className="flex w-full items-end gap-1">
              <div
                className="w-1/2 rounded-t bg-teal-500 transition-all hover:bg-teal-600"
                style={{ height: `${(d.rent / maxRent) * 100}%` }}
                title={`Rent: KES ${d.rent}M`}
              />
              <div
                className="w-1/2 rounded-t bg-gold-300 transition-all hover:bg-gold-400"
                style={{ height: `${(d.fees / (maxRent * 0.06)) * 100}%` }}
                title={`Fees: KES ${d.fees}K`}
              />
            </div>
            <span className="text-xs text-ink-500">{d.month}</span>
          </div>
        ))}
      </div>
      <div className="mt-4 flex items-center justify-center gap-6 text-xs text-ink-600">
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 rounded bg-teal-500" />
          <span>Rent Collected</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 rounded bg-gold-300" />
          <span>Platform Fees</span>
        </div>
      </div>
    </div>
  );
}

function OccupancyChart() {
  const total = 120;
  const occupied = 92;
  const vacant = total - occupied;
  const maintenance = 8;

  return (
    <div className="flex flex-col items-center justify-center gap-4">
      <div className="relative h-48 w-48">
        <svg viewBox="0 0 36 36" className="h-full w-full -rotate-90">
          <circle cx="18" cy="18" r="15.915" fill="none" stroke="#E3E7E5" strokeWidth="3" />
          <circle cx="18" cy="18" r="15.915" fill="none" stroke="#0F6B5C" strokeWidth="3" strokeDasharray={`${(occupied / total) * 100} ${100 - (occupied / total) * 100}`} strokeLinecap="round" />
          <circle cx="18" cy="18" r="15.915" fill="none" stroke="#C98A2C" strokeWidth="3" strokeDasharray={`${(maintenance / total) * 100} ${100 - (maintenance / total) * 100}`} strokeDashoffset={`-${(occupied / total) * 100}`} strokeLinecap="round" />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold text-ink-900">{Math.round((occupied / total) * 100)}%</span>
          <span className="text-xs text-ink-600">Occupied</span>
        </div>
      </div>
      <div className="flex w-full flex-col gap-2 text-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-teal-500" />
            <span className="text-ink-600">Occupied</span>
          </div>
          <span className="font-mono font-medium text-ink-900 tabular-nums">{occupied} units</span>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-amber-500" />
            <span className="text-ink-600">Maintenance</span>
          </div>
          <span className="font-mono font-medium text-ink-900 tabular-nums">{maintenance} units</span>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-ink-300" />
            <span className="text-ink-600">Vacant</span>
          </div>
          <span className="font-mono font-medium text-ink-900 tabular-nums">{vacant} units</span>
        </div>
      </div>
    </div>
  );
}
