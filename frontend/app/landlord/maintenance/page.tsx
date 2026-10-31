"use client";

import DashboardLayout from "@/components/DashboardLayout";

export default function MaintenanceQueuePage() {
  return (
    <DashboardLayout>
      <div className="space-y-4">
        <h1 className="font-serif text-[28px] font-medium text-ink-900">Maintenance queue</h1>
        <p className="text-sm text-ink-600">Review tenant maintenance tickets and assign or dispatch caretakers.</p>
      </div>
    </DashboardLayout>
  );
}
