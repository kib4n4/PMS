"use client";

import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth-context";

const SECTION_LABELS: Record<string, string> = {
  "/": "Overview",
  "/landlord": "Landlord",
  "/reseller": "Reseller",
  "/investor": "Investor",
  "/caretaker": "Caretaker",
  "/admin": "Admin",
};

function sectionFor(pathname: string): string {
  const match = Object.keys(SECTION_LABELS)
    .filter((path) => path !== "/")
    .find((path) => pathname === path || pathname.startsWith(`${path}/`));
  return SECTION_LABELS[match ?? pathname] ?? "Dashboard";
}

export default function TopBar() {
  const pathname = usePathname();
  const { role, isSuperAdmin } = useAuth();

  const section = sectionFor(pathname);
  const viewingOtherRole = isSuperAdmin && !!role && section.toLowerCase() !== role;

  return (
    <div className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-surface px-6 lg:px-8">
      <nav className="flex items-center gap-1.5 text-sm" aria-label="Breadcrumb">
        <span className="text-ink-500">Dashboards</span>
        <span className="text-ink-300">/</span>
        <span className="font-medium text-ink-800">{section}</span>
      </nav>

      {isSuperAdmin && (
        <span className="inline-flex items-center gap-1.5 rounded-full border border-teal-200 bg-teal-50 px-2.5 py-1 text-xs font-medium text-teal-700">
          <span className="h-1.5 w-1.5 rounded-full bg-teal-500" />
          {viewingOtherRole ? `Super Admin — viewing ${section}` : "Super Admin"}
        </span>
      )}
    </div>
  );
}
