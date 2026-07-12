/**
 * This is a scaffold, not a built-out dashboard — dashboards per role
 * (Landlord, Reseller, Investor, Caretaker, Admin) are M5 work per the
 * design doc. This page exists so `next dev` runs and the routing
 * structure below reflects the intended app shape.
 *
 * Route plan (build out per milestone):
 *   /landlord   — occupancy, rent roll, arrears, fee-invoice history
 *   /reseller   — referred landlords, commission earned, payout history
 *   /investor   — revenue share earned, payout history, portfolio metrics
 *   /caretaker  — assigned units, ticket queue
 *   /admin      — ops console: onboarding status, reconciliation, overrides
 */
export default function Home() {
  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem" }}>
      <h1>PMS — Dashboard Scaffold</h1>
      <p>
        Backend API and data model are implemented (M0/M1). This frontend
        is a routing scaffold only — dashboards are built out in M5.
      </p>
    </main>
  );
}
