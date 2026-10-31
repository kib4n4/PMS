type ActionVariant = "primary" | "secondary" | "ghost";

type RoleAction = {
  label: string;
  onClick?: () => void;
  variant?: ActionVariant;
  disabled?: boolean;
};

export default function RoleActionBar({ actions }: { actions: RoleAction[] }) {
  if (!actions.length) return null;

  const variantStyles: Record<ActionVariant, string> = {
    primary: "border-teal-600 bg-teal-600 text-white hover:bg-teal-500",
    secondary: "border-border bg-surface text-ink-700 hover:border-teal-300 hover:bg-teal-50",
    ghost: "border-transparent bg-transparent text-ink-600 hover:bg-mist-100 hover:text-ink-900",
  };

  return (
    <div className="flex flex-wrap gap-3">
      {actions.map((action) => (
        <button
          key={action.label}
          type="button"
          onClick={action.onClick}
          disabled={action.disabled}
          className={[
            "inline-flex items-center justify-center rounded-md border px-3.5 py-2 text-sm font-medium transition-colors",
            "focus:outline-none focus:ring-2 focus:ring-teal-500/30 focus:ring-offset-2 focus:ring-offset-mist-50",
            action.disabled ? "cursor-not-allowed border-border bg-mist-100 text-ink-400" : variantStyles[action.variant ?? "secondary"],
          ].join(" ")}
        >
          {action.label}
        </button>
      ))}
    </div>
  );
}
