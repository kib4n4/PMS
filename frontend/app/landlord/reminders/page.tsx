"use client";

import DashboardLayout from "@/components/DashboardLayout";

export default function RentRemindersPage() {
  return (
    <DashboardLayout>
      <div className="space-y-4">
        <h1 className="font-serif text-[28px] font-medium text-ink-900">Send reminders</h1>
        <p className="text-sm text-ink-600">Review upcoming due rents and send automated WhatsApp or email reminders.</p>
      </div>
    </DashboardLayout>
  );
}
