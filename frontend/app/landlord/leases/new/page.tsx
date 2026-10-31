"use client";

import DashboardLayout from "@/components/DashboardLayout";

export default function CreateLeasePage() {
  return (
    <DashboardLayout>
      <div className="space-y-4">
        <h1 className="font-serif text-[28px] font-medium text-ink-900">Create lease</h1>
        <p className="text-sm text-ink-600">Assign a tenant to a unit, define rent terms, and set billing details.</p>
      </div>
    </DashboardLayout>
  );
}
