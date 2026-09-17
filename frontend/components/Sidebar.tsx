import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Dashboard", icon: DashboardIcon, roles: ["admin", "landlord", "reseller", "investor", "caretaker"] },
  { href: "/landlord", label: "Landlord", icon: BuildingIcon, roles: ["admin", "landlord"] },
  { href: "/reseller", label: "Reseller", icon: UsersIcon, roles: ["admin", "reseller"] },
  { href: "/investor", label: "Investor", icon: TrendingUpIcon, roles: ["admin", "investor"] },
  { href: "/caretaker", label: "Caretaker", icon: WrenchIcon, roles: ["admin", "caretaker"] },
  { href: "/admin", label: "Admin", icon: ShieldIcon, roles: ["admin"] },
];

export default function Sidebar({ userRole = "landlord" }: { userRole?: string }) {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-64 flex-col border-r border-ink-800 bg-ink-900 text-mist-200">
      <div className="flex h-16 items-center gap-3 border-b border-ink-800 px-6">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-500">
          <BuildingIcon className="h-5 w-5 text-white" />
        </div>
        <span className="text-lg font-semibold text-mist-50">Ledger</span>
      </div>

      <nav className="flex-1 space-y-1 p-3" aria-label="Main navigation">
        {navItems
          .filter((item) => item.roles.includes(userRole))
          .map((item) => {
            const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-md border-l-2 border-transparent px-3 py-2 text-sm font-medium transition-all",
                  isActive
                    ? "border-l-teal-500 bg-ink-800 text-mist-50"
                    : "text-mist-300 hover:border-l-teal-500 hover:bg-ink-800/70 hover:text-mist-100",
                )}
              >
                <item.icon className={cn("h-5 w-5", isActive ? "text-teal-500" : "text-mist-300")} />
                {item.label}
              </Link>
            );
          })}
      </nav>

      <div className="border-t border-ink-800 p-4">
        <div className="flex items-center gap-3 rounded-lg bg-ink-800/70 p-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-teal-500/20 text-teal-400">
            <UsersIcon className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-mist-100">Demo User</p>
            <p className="truncate text-xs text-mist-400 capitalize">{userRole}</p>
          </div>
        </div>
      </div>
    </aside>
  );
}

function DashboardIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
    </svg>
  );
}

function BuildingIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 17.25h.008v.008H6.75v-.008zm0-3h.008v.008H6.75V14.25zm0-3h.008v.008H6.75v-.008zm0-3h.008v.008H6.75V8.25zm9 9h.008v.008H15.75v-.008zm0-3h.008v.008H15.75V14.25zm0-3h.008v.008H15.75v-.008zm0-3h.008v.008H15.75V8.25zm3.75 9h.008v.008H19.5v-.008zm0-3h.008v.008H19.5V14.25zm0-3h.008v.008H19.5v-.008zM4.5 19.5h15a2.25 2.25 0 002.25-2.25V6a2.25 2.25 0 00-2.25-2.25H4.5A2.25 2.25 0 002.25 6v11.25A2.25 2.25 0 004.5 19.5z" />
    </svg>
  );
}

function UsersIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.001 9.001 0 001.424-4.95m-9.05-4.95a9.001 9.001 0 011.424-4.95M15 19.128v.003a9.001 9.001 0 01-2.424.003m2.424-.003a9.001 9.001 0 012.424-.003M9 19.128v.003a9.001 9.001 0 01-2.424.003m2.424-.003a9.001 9.001 0 012.424-.003M9 19.128a9.001 9.001 0 01-1.424-4.95m9.05 4.95a9.001 9.001 0 01-1.424-4.95m-9.05 4.95a9.001 9.001 0 00-1.424 4.95m9.05-4.95a9.001 9.001 0 00-1.424 4.95M12 12.75a3.75 3.75 0 100-7.5 3.75 3.75 0 000 7.5z" />
    </svg>
  );
}

function TrendingUpIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" />
    </svg>
  );
}

function WrenchIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M11.42 15.17l-5.108-5.108a2.25 2.25 0 01-.586-1.591V6.75a2.25 2.25 0 012.25-2.25h2.344a2.25 2.25 0 011.591.586l5.108 5.108m-1.591 1.591l-5.108 5.108a2.25 2.25 0 01-1.591.586H6.75a2.25 2.25 0 01-2.25-2.25v-2.344a2.25 2.25 0 01.586-1.591l5.108-5.108m1.591 1.591l5.108 5.108a2.25 2.25 0 01.586 1.591V18a2.25 2.25 0 01-2.25 2.25h-2.344a2.25 2.25 0 01-1.591-.586l-5.108-5.108m1.591-1.591l5.108-5.108" />
    </svg>
  );
}

function ShieldIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
    </svg>
  );
}
