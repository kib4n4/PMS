"use client";

import { ReactNode } from "react";

import { cn } from "@/lib/utils";

type Column<T> = {
  key: string;
  header: string;
  render?: (row: T) => ReactNode;
};

// Right-align + tabular figures for anything numeric/id-shaped — no
// monospace face needed, Public Sans carries tabular-nums itself.
const NUMERIC_KEYS = new Set(["amount", "rate", "ratePercent"]);
const TABULAR_KEYS = new Set(["id", "txnId", "date", "time", "shortcode", "start", "end"]);

export default function DataTable<T>({
  columns,
  data,
  empty,
  className,
}: {
  columns: Column<T>[];
  data: T[];
  empty?: ReactNode;
  className?: string;
}) {
  if (data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 border-t border-dashed border-border py-12 text-ink-500">
        {empty ?? <p className="text-sm">No records found.</p>}
      </div>
    );
  }

  return (
    <div className={cn("overflow-x-auto", className)}>
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-border">
            {columns.map((col) => {
              const numeric = NUMERIC_KEYS.has(col.key);
              return (
                <th
                  key={col.key}
                  className={cn(
                    "px-4 py-3 text-[13px] font-semibold text-ink-600",
                    numeric && "text-right",
                  )}
                >
                  {col.header}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {data.map((row, idx) => (
            <tr key={idx} className="group relative border-b border-dashed border-border/80 last:border-b-0">
              {columns.map((col, colIdx) => {
                const numeric = NUMERIC_KEYS.has(col.key);
                const tabular = numeric || TABULAR_KEYS.has(col.key);
                return (
                  <td
                    key={col.key}
                    className={cn(
                      "relative px-4 py-3 align-top text-ink-800",
                      tabular && "tabular-nums",
                      numeric && "text-right font-medium",
                    )}
                  >
                    {colIdx === 0 && (
                      // Ledger check-mark: appears on the row's leading
                      // edge on hover, like a bookkeeper's pencil tick
                      // against a reconciled line.
                      <span
                        aria-hidden="true"
                        className="pointer-events-none absolute left-0 top-1/2 h-4 w-0.5 -translate-x-2 -translate-y-1/2 rounded-full bg-teal-500 opacity-0 transition-opacity group-hover:opacity-100"
                      />
                    )}
                    {col.render
                      ? col.render(row)
                      : String((row as Record<string, unknown>)[col.key] ?? "")}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
