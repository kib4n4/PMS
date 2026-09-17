import { ReactNode } from "react";
import Sidebar from "./Sidebar";

export default function DashboardLayout({
  children,
  userRole = "landlord",
}: {
  children: ReactNode;
  userRole?: string;
}) {
  return (
    <div className="flex h-screen overflow-hidden bg-mist-50">
      <Sidebar userRole={userRole} />
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-7xl p-6 lg:p-8">{children}</div>
      </main>
    </div>
  );
}
