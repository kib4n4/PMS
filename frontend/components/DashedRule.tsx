import { cn } from "@/lib/utils";

export default function DashedRule({ className }: { className?: string }) {
  return <div className={cn("border-t-2 border-dashed border-border", className)} aria-hidden="true" />;
}
