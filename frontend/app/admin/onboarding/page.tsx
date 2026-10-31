"use client";

import DashboardLayout from "@/components/DashboardLayout";

export default function AdminOnboardingPage() {
  return (
    <DashboardLayout>
      <div className="space-y-4">
        <h1 className="font-serif text-[28px] font-medium text-ink-900">Onboarding queue</h1>
        <p className="text-sm text-ink-600">Review landlord onboarding progress, Daraja setup, and activation status.</p>
      </div>
    </DashboardLayout>
  );
}
