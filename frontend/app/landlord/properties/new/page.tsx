"use client";

import DashboardLayout from "@/components/DashboardLayout";

export default function AddPropertyPage() {
  return (
    <DashboardLayout>
      <div className="space-y-4">
        <h1 className="font-serif text-[28px] font-medium text-ink-900">Add property</h1>
        <p className="text-sm text-ink-600">Create a new property and assign its landlord ownership.</p>
      </div>
    </DashboardLayout>
  );
}
