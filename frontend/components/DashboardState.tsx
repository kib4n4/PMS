"use client";

export function DashboardLoading() {
  return (
    <div className="flex h-64 flex-col items-center justify-center gap-3 text-sm text-ink-500">
      <svg className="h-6 w-6 animate-spin text-teal-600" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="8.4" stroke="currentColor" strokeWidth="1.5" strokeOpacity="0.25" />
        <path d="M12 3.6a8.4 8.4 0 018.4 8.4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
      Loading dashboard&hellip;
    </div>
  );
}

export function DashboardError({ message }: { message: string }) {
  return (
    <div className="flex h-64 flex-col items-center justify-center gap-2 border border-dashed border-rust-300 bg-rust-50/40 text-sm">
      <p className="font-medium text-rust-700">Couldn&rsquo;t load this dashboard.</p>
      <p className="text-xs text-ink-500">{message}</p>
    </div>
  );
}
