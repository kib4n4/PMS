"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BuildingIcon, UsersIcon, TrendingUpIcon, WrenchIcon, ShieldIcon } from "@/components/Icons";

const roles = [
  { href: "/landlord", label: "Landlord", description: "Properties, tenants, rent, and occupancy", icon: <BuildingIcon className="h-7 w-7" /> },
  { href: "/reseller", label: "Reseller", description: "Referrals, commissions, and payouts", icon: <UsersIcon className="h-7 w-7" /> },
  { href: "/investor", label: "Investor", description: "Revenue share, agreements, and disbursements", icon: <TrendingUpIcon className="h-7 w-7" /> },
  { href: "/caretaker", label: "Caretaker", description: "Assigned properties and ticket queue", icon: <WrenchIcon className="h-7 w-7" /> },
  { href: "/admin", label: "Admin", description: "Platform ops, onboarding, and audit trail", icon: <ShieldIcon className="h-7 w-7" /> },
];

// A slight per-tab baseline stagger — physical binder index tabs are
// never perfectly flush, so neither are these.
const OFFSETS = ["sm:translate-y-0", "sm:translate-y-3", "sm:translate-y-1", "sm:translate-y-4", "sm:translate-y-1.5"];

export default function Home() {
  // Presentation-only entrance stagger — no data/state beyond "has this
  // mounted yet." Respects prefers-reduced-motion globally (globals.css).
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-mist-50 p-8">
      <div className="mx-auto max-w-5xl text-center">
        <p className="mb-3 text-sm text-ink-500">Property management, kept like a book</p>
        <h1 className="mb-4 font-serif text-6xl font-medium tracking-tight text-ink-900">Ledger</h1>
        <p className="mx-auto mb-16 max-w-md text-[15px] text-ink-600">
          Turns M-Pesa confirmations into auditable financial records — for landlords, tenants,
          resellers, investors, and caretakers.
        </p>

        <div className="grid gap-5 sm:grid-cols-3 lg:grid-cols-5">
          {roles.map((role, i) => (
            <Link
              key={role.href}
              href={role.href}
              className={`group flex flex-col items-center gap-3 rounded-t-lg border border-b-[3px] border-border border-b-teal-600 bg-surface px-5 pb-6 pt-7 text-left shadow-ledger transition-all duration-500 hover:-translate-y-0.5 hover:border-teal-300 hover:border-b-teal-600 hover:shadow-md ${OFFSETS[i]} ${
                mounted ? "translate-y-0 opacity-100" : "translate-y-3 opacity-0"
              }`}
              style={{ transitionDelay: mounted ? `${i * 70}ms` : "0ms" }}
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-full border border-teal-200 bg-teal-50 text-teal-700 transition-colors group-hover:bg-teal-100">
                {role.icon}
              </div>
              <div className="text-center">
                <h2 className="font-serif text-lg font-medium text-ink-900">{role.label}</h2>
                <p className="mt-1 text-xs leading-relaxed text-ink-600">{role.description}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </main>
  );
}
