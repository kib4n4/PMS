"use client";

import DashboardLayout from "@/components/DashboardLayout";

export default function AdminAuditPage() {
  return (
    <DashboardLayout>
      <div className="space-y-4">
        <h1 className="font-serif text-[28px] font-medium text-ink-900">Audit log</h1>
        <p className="text-sm text-ink-600">Audit trail for user actions, approvals, collections, and platform changes.</p>
      </div>
    </DashboardLayout>
  );
}
