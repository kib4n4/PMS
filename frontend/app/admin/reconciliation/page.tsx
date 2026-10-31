"use client";

import DashboardLayout from "@/components/DashboardLayout";

export default function AdminReconciliationPage() {
  return (
    <DashboardLayout>
      <div className="space-y-4">
        <h1 className="font-serif text-[28px] font-medium text-ink-900">Fee reconciliation</h1>
        <p className="text-sm text-ink-600">Review platform fee collections and reconcile monthly adjustments.</p>
      </div>
    </DashboardLayout>
  );
}
