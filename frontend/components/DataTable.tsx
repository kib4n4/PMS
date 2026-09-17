"use client";

import { ReactNode } from "react";

import { cn } from "@/lib/utils";

type Column<T> = {
  key: string;
  header: string;
  render?: (row: T) => ReactNode;
};

const MONO_KEYS = new Set(["id", "txnId", "date", "time", "amount", "shortcode", "rate", "start", "end"]);

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
      <div className="flex flex-col items-center justify-center py-12 text-ink-500">
        {empty ?? <p className="text-sm">No records found.</p>}
      </div>
    );
  }

  return (
    <div className={cn("overflow-x-auto", className)}>
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-border">
            {columns.map((col) => (
              <th
                key={col.key}
                className="px-4 py-3 text-xs font-medium uppercase tracking-wide text-ink-600"
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {data.map((row, idx) => (
            <tr key={idx} className="hover:bg-mist-100/50">
              {columns.map((col) => {
                const mono = MONO_KEYS.has(col.key);
                return (
                  <td
                    key={col.key}
                    className={cn(
                      "px-4 py-3 align-top text-ink-800",
                      mono && "font-mono tabular-nums",
                    )}
                  >
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
