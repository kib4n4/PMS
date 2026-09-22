"use client";

import { ReactNode } from "react";

import { cn } from "@/lib/utils";

export default function ChartCard({
  title,
  description,
  children,
  className,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-border border-l-2 border-l-teal-600/40 bg-surface p-6 shadow-ledger",
        className,
      )}
    >
      <div className="mb-4">
        <h3 className="text-[15px] font-semibold text-ink-900">{title}</h3>
        {description && <p className="mt-1 text-sm text-ink-600">{description}</p>}
      </div>
      {children}
    </div>
  );
}
