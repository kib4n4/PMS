"use client";

import DashboardLayout from "@/components/DashboardLayout";

export default function AddUnitPage() {
  return (
    <DashboardLayout>
      <div className="space-y-4">
        <h1 className="font-serif text-[28px] font-medium text-ink-900">Add unit</h1>
        <p className="text-sm text-ink-600">Create new units for a property and track occupancy status.</p>
      </div>
    </DashboardLayout>
  );
}
