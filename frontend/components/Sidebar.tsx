"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { cn } from "@/lib/utils";
import { Role, useAuth } from "@/lib/auth-context";
import { BuildingIcon, ShieldIcon, TrendingUpIcon, UsersIcon, WrenchIcon } from "@/components/Icons";

type NavItem = {
  href: string;
  label: string;
  icon: (props: { className?: string }) => JSX.Element;
  roles?: Role[];
  superAdminOnly?: boolean;
  alwaysVisible?: boolean;
};

// Card/nav visibility follows the platform's role hierarchy: a role only
// sees its own dashboard, never another role's — only super admin
// (is_super_admin, not just role === "admin") sees everything.
const navItems: NavItem[] = [
  { href: "/", label: "Dashboard", icon: DashboardIcon, alwaysVisible: true },
  { href: "/landlord", label: "Landlord", icon: BuildingIcon, roles: ["landlord"] },
  { href: "/reseller", label: "Reseller", icon: UsersIcon, roles: ["reseller"] },
  { href: "/investor", label: "Investor", icon: TrendingUpIcon, roles: ["investor"] },
  { href: "/caretaker", label: "Caretaker", icon: WrenchIcon, roles: ["caretaker"] },
  { href: "/admin", label: "Admin", icon: ShieldIcon, superAdminOnly: true },
];

function isVisible(item: NavItem, role: Role | null, isSuperAdmin: boolean): boolean {
  if (isSuperAdmin) return true;
  if (item.alwaysVisible) return true;
  if (item.superAdminOnly) return false;
  return !!role && (item.roles ?? []).includes(role);
}

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, role, isSuperAdmin, logout } = useAuth();

  const visibleItems = navItems.filter((item) => isVisible(item, role, isSuperAdmin));

  return (
    // The cover of the ledger — a deep ink-green spine against the pale
    // paper of the content area, not a default dark-sidebar/light-content
    // split. See design plan.
    <aside className="flex h-screen w-64 flex-col bg-ink-900 text-mist-100">
      <div className="flex h-16 items-center gap-3 border-b border-ink-800/80 px-6">
        <div className="flex h-8 w-8 items-center justify-center rounded-full border border-teal-400/40 bg-teal-500/15">
          <span className="font-serif text-base font-medium text-teal-300">L</span>
        </div>
        <span className="font-serif text-lg font-medium tracking-tight text-mist-50">Ledger</span>
      </div>

      <nav className="flex-1 space-y-0.5 p-3" aria-label="Main navigation">
        {visibleItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-sm border-l-2 px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "border-l-teal-400 bg-ink-800 text-mist-50"
                  : "border-l-transparent text-mist-300 hover:border-l-teal-400/50 hover:bg-ink-800/60 hover:text-mist-100",
              )}
            >
              <item.icon className={cn("h-[18px] w-[18px] shrink-0", isActive ? "text-teal-400" : "text-mist-400")} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-ink-800/80 p-4">
        <div className="flex items-center gap-3 rounded-sm bg-ink-800/50 p-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-teal-400/30 bg-teal-500/10 text-teal-300">
            <UsersIcon className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-mist-100">{user?.username ?? "…"}</p>
            <p className="truncate text-xs text-mist-400 capitalize">
              {isSuperAdmin ? "Super Admin" : role ?? ""}
            </p>
          </div>
          <button
            type="button"
            onClick={async () => {
              await logout();
              router.push("/login");
            }}
            className="shrink-0 text-xs font-medium text-mist-400 transition-colors hover:text-mist-100"
          >
            Log out
          </button>
        </div>
      </div>
    </aside>
  );
}

function DashboardIcon({ className }: { className?: string }) {
  // An open ledger book, ruled page visible — not a generic grid icon.
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.5 5.6c2.4-1 4.9-1 7 .5v11.9c-2.1-1.5-4.6-1.5-7-.5V5.6z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M20.5 5.6c-2.4-1-4.9-1-7 .5v11.9c2.1-1.5 4.6-1.5 7-.5V5.6z" />
      <path strokeLinecap="round" d="M14.2 9.4h4M14.2 12.3h3.4" />
    </svg>
  );
}
