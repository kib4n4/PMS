"use client";

import { ReactNode, useEffect } from "react";
import { useRouter } from "next/navigation";

import Sidebar from "./Sidebar";
import TopBar from "./TopBar";
import { useAuth } from "@/lib/auth-context";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace("/login");
    }
  }, [isLoading, user, router]);

  if (isLoading || !user) {
    return (
      <div className="flex h-screen items-center justify-center bg-mist-50">
        <div className="flex items-center gap-3 text-sm text-ink-500">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-ink-200 border-t-teal-500" />
          Loading&hellip;
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden bg-mist-50">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-7xl p-6 lg:p-8">{children}</div>
        </main>
      </div>
    </div>
  );
}
