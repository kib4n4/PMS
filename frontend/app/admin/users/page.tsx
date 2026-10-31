"use client";

import DashboardLayout from "@/components/DashboardLayout";

export default function AdminUsersPage() {
  return (
    <DashboardLayout>
      <div className="space-y-4">
        <h1 className="font-serif text-[28px] font-medium text-ink-900">Manage users</h1>
        <p className="text-sm text-ink-600">Platform user management, permission mapping, and account review.</p>
      </div>
    </DashboardLayout>
  );
}
