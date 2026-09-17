"use client";

import Link from "next/link";
import { BuildingIcon, UsersIcon, TrendingUpIcon, WrenchIcon, ShieldIcon } from "@/components/Icons";

const roles = [
  { href: "/landlord", label: "Landlord", description: "Properties, tenants, rent, and occupancy", icon: <BuildingIcon className="h-8 w-8" /> },
  { href: "/reseller", label: "Reseller", description: "Referrals, commissions, and payouts", icon: <UsersIcon className="h-8 w-8" /> },
  { href: "/investor", label: "Investor", description: "Revenue share, agreements, and disbursements", icon: <TrendingUpIcon className="h-8 w-8" /> },
  { href: "/caretaker", label: "Caretaker", description: "Assigned properties and ticket queue", icon: <WrenchIcon className="h-8 w-8" /> },
  { href: "/admin", label: "Admin", description: "Platform ops, onboarding, and system health", icon: <ShieldIcon className="h-8 w-8" /> },
];

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-mist-50 p-8">
      <div className="mx-auto max-w-4xl text-center">
        <div className="mb-8 flex items-center justify-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-teal-500">
            <BuildingIcon className="h-7 w-7 text-white" />
          </div>
          <h1 className="text-4xl font-bold text-ink-900">Ledger</h1>
        </div>
        <p className="mb-12 text-lg text-ink-600">
          Ledger — turn M-Pesa confirmations into auditable financial records.
        </p>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {roles.map((role) => (
            <Link
              key={role.href}
              href={role.href}
              className="group flex flex-col items-center gap-4 rounded-2xl border border-border bg-surface p-8 shadow-ledger transition-all hover:border-teal-300 hover:shadow-md"
            >
              <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-mist-100/70 text-ink-600 transition-colors group-hover:bg-teal-50 group-hover:text-teal-600">
                {role.icon}
              </div>
              <div>
                <h2 className="text-lg font-semibold text-ink-900">{role.label}</h2>
                <p className="mt-1 text-sm text-ink-600">{role.description}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
