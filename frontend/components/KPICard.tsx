import { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface KPICardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: { value: number; label: string };
  icon?: ReactNode;
  accent?: "blue" | "emerald" | "amber" | "rose";
}

const iconTeal: Record<NonNullable<KPICardProps["accent"]>, string> = {
  blue: "text-teal-600",
  emerald: "text-teal-600",
  amber: "text-amber-600",
  rose: "text-rust-600",
};

export default function KPICard({ title, value, subtitle, trend, icon, accent }: KPICardProps) {
  const dir = trend ? (trend.value > 0 ? "up" : trend.value < 0 ? "down" : "flat") : null;
  const trendColor = dir === "up" ? "text-teal-700" : dir === "down" ? "text-rust-700" : "text-amber-700";
  const iconColor = iconTeal[accent ?? "blue"];

  return (
    <div className="rounded-xl">
      <div
        className="relative rounded-xl border-2 border-dashed border-border bg-surface p-5 shadow-ledger"
        style={{
          clipPath:
            "polygon(10px 0, calc(100% - 10px) 0, 100% 10px, 100% calc(100% - 10px), calc(100% - 10px) 100%, 10px 100%, 0 calc(100% - 10px), 0 10px)",
        }}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium uppercase tracking-wide text-ink-600">{title}</p>
            <p className="mt-1 font-mono text-2xl font-semibold text-ink-900 tabular-nums">{value}</p>
            {subtitle && <p className="mt-0.5 text-xs text-ink-600">{subtitle}</p>}
          </div>
          {icon && <div className={cn("flex-shrink-0", iconColor)}>{icon}</div>}
        </div>

        {trend && (
          <div className="mt-3 flex items-center gap-1.5">
            <TrendArrow direction={dir ?? "flat"} />
            <span className={cn("text-xs font-medium tabular-nums", trendColor)}>
              {trend.value > 0 && "+"}
              {trend.value}%
            </span>
            <span className="text-xs text-ink-600">{trend.label}</span>
          </div>
        )}
      </div>
    </div>
  );
}

function TrendArrow({ direction }: { direction: "up" | "down" | "flat" }) {
  if (direction === "up") {
    return (
      <svg className="h-3.5 w-3.5 text-teal-600" viewBox="0 0 14 14" fill="currentColor">
        <path d="M4 10V4l4 3 4-3v6H4z" />
      </svg>
    );
  }
  if (direction === "down") {
    return (
      <svg className="h-3.5 w-3.5 text-rust-600" viewBox="0 0 14 14" fill="currentColor">
        <path d="M10 4v6l-4-3-4 3V4h8z" />
      </svg>
    );
  }
  return <span className="h-3.5 w-3.5 rounded-full bg-amber-400" />;
}
