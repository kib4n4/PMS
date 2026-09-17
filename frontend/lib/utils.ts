type ClassValue = string | number | null | undefined | false | ClassValue[];

export function cn(...inputs: ClassValue[]): string {
  const out: string[] = [];
  for (const input of inputs) {
    if (input == null || input === false || input === "") continue;
    if (Array.isArray(input)) {
      out.push(cn(...input));
    } else if (typeof input === "string") {
      out.push(input);
    }
  }
  // de-dup while preserving order (lightweight tailwind-merge replacement)
  const seen = new Set<string>();
  return out
    .flatMap((s) => s.split(/\s+/).filter(Boolean))
    .filter((c) => (seen.has(c) ? false : (seen.add(c), true)))
    .join(" ");
}
