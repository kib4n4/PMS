// frontend/lib/group-by-month.ts
// Server-only helper for dashboard proxy routes: buckets a list of
// timestamped rows into the last N calendar months (oldest first,
// zero-filled), so a fresh system's mostly-empty history renders as a
// flat/sparse real chart instead of needing a backend aggregate endpoint.

export function groupByMonth<T extends { created_at: string; amount: string }>(rows: T[], months: number) {
  const now = new Date();
  const buckets: { key: string; label: string; amount: number }[] = [];
  for (let i = months - 1; i >= 0; i -= 1) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    buckets.push({
      key: `${d.getFullYear()}-${d.getMonth()}`,
      label: d.toLocaleString("en-US", { month: "short" }),
      amount: 0,
    });
  }
  for (const row of rows) {
    const d = new Date(row.created_at);
    const key = `${d.getFullYear()}-${d.getMonth()}`;
    const bucket = buckets.find((b) => b.key === key);
    if (bucket) bucket.amount += Number(row.amount);
  }
  return buckets.map(({ label, amount }) => ({ month: label, amount }));
}
