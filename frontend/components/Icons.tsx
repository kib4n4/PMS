// Ledger icon set — one shared grammar: rubber-stamp seals for status,
// ledger tally marks for counts/growth. Deliberately not an
// outline-icon-library swap; every shape below is drawn to mean
// something specific to a ledger/property/M-Pesa product. Exported
// names and the { className } prop are preserved exactly — only the
// markup inside each component changed.

export function BuildingIcon({ className }: { className?: string }) {
  // A single gabled roofline over a base rule — "property," grounded.
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 20h16" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 20V10.5L12 6l6 4.5V20" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M10 20v-5h4v5" />
    </svg>
  );
}

export function UsersIcon({ className }: { className?: string }) {
  // Headcount as a ledger tally, not a person silhouette.
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" d="M4 18h16" />
      <path strokeLinecap="round" d="M6.5 18V10M12 18V6.5M17.5 18V12" />
    </svg>
  );
}

export function TrendingUpIcon({ className }: { className?: string }) {
  // Ascending tally bars — growth and a ledger column at once.
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" stroke="none">
      <rect x="5" y="13" width="3.1" height="5.5" rx="0.6" />
      <rect x="10.45" y="9" width="3.1" height="9.5" rx="0.6" />
      <rect x="15.9" y="5" width="3.1" height="13.5" rx="0.6" />
    </svg>
  );
}

export function WrenchIcon({ className }: { className?: string }) {
  // Wrench with a verification tick — repair, then confirmed.
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M14.7 5.8a3.6 3.6 0 00-4.66 4.66L4.5 16v3h3l5.54-5.54a3.6 3.6 0 004.66-4.66l-2.55 2.55-2.1-2.1 2.55-2.55z"
      />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.3 15.6l1.9 1.9 3-3.6" />
    </svg>
  );
}

export function ShieldIcon({ className }: { className?: string }) {
  // A ribboned official seal — government-stamp register, not a shield.
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <circle cx="12" cy="9.5" r="6" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 9.6l1.9 1.9 3.3-3.7" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.8 14.8L7.2 21l4.8-2.1 4.8 2.1-1.6-6.2" />
    </svg>
  );
}

export function ArrowUpRightIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 17L17 7M9 7h8v8" />
    </svg>
  );
}

export function DollarSignIcon({ className }: { className?: string }) {
  // A coin, not a $ sign — this product deals in shillings.
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <circle cx="12" cy="12" r="7.5" />
      <circle cx="12" cy="12" r="4" strokeDasharray="1.6 2.1" />
    </svg>
  );
}

export function PieChartIcon({ className }: { className?: string }) {
  // A 2x2 ledger block, not a pie/donut — see design plan.
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <rect x="4" y="4" width="7" height="7" rx="1" />
      <rect x="13" y="4" width="7" height="7" rx="1" />
      <rect x="4" y="13" width="7" height="7" rx="1" />
      <rect x="13" y="13" width="7" height="7" rx="1" />
    </svg>
  );
}

export function MailIcon({ className }: { className?: string }) {
  // An envelope with a small wax-seal mark.
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <rect x="3.5" y="5.5" width="17" height="13" rx="1.5" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 7l8 6 8-6" />
      <circle cx="12" cy="14.4" r="1.3" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function ClipboardListIcon({ className }: { className?: string }) {
  // A ruled ledger sheet on a clip, one line ticked off.
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <rect x="6" y="4.5" width="12" height="16.5" rx="1.5" />
      <path fill="currentColor" stroke="none" d="M9 3.2h6v2.1H9z" />
      <path strokeLinecap="round" d="M8.5 10h7M8.5 13.2h7" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.5 16.4l1.3 1.2 2-2.3" />
    </svg>
  );
}

export function CheckCircleIcon({ className }: { className?: string }) {
  // "Confirmed" stamp — a rubber-stamp double ring with a check.
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <circle cx="12" cy="12" r="8.4" />
      <circle cx="12" cy="12" r="5.8" opacity="0.45" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.7 12.2l2.3 2.3 4.3-4.7" />
    </svg>
  );
}

export function XCircleIcon({ className }: { className?: string }) {
  // "Void" stamp — same ring family as Confirmed, marked instead of ticked.
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <circle cx="12" cy="12" r="8.4" />
      <circle cx="12" cy="12" r="5.8" opacity="0.45" />
      <path strokeLinecap="round" d="M9.6 9.6l4.8 4.8m0-4.8l-4.8 4.8" />
    </svg>
  );
}

export function ClockIcon({ className }: { className?: string }) {
  // "Pending" stamp — half-filled, mid-impression, same ring family.
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
      <circle cx="12" cy="12" r="8.4" />
      <path fill="currentColor" stroke="none" opacity="0.55" d="M3.6 12a8.4 8.4 0 0016.8 0H12z" />
    </svg>
  );
}
