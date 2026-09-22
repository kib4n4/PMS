import type { Metadata } from "next";
import { Public_Sans, Fraunces, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

import { AuthProvider } from "@/lib/auth-context";

// UI text — Public Sans (built for forms/official documents; see design
// plan for why that's a deliberate fit here, not a default).
const publicSans = Public_Sans({
  variable: "--font-sans",
  weight: ["400", "500", "600", "700"],
  subsets: ["latin"],
});

// Display/numerals — Fraunces, used for large KES figures and headings.
// Variable weight (applied via font-normal/medium/semibold at each use
// site) so the opsz/SOFT axes stay available across the whole range.
const fraunces = Fraunces({
  variable: "--font-display",
  weight: "variable",
  style: ["normal"],
  subsets: ["latin"],
  axes: ["opsz", "SOFT"],
});

// Kept only for tabular-nums fallback stacks; UI numerals live on the
// sans face now.
const ibmMono = IBM_Plex_Mono({
  variable: "--font-mono",
  weight: ["400", "500"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Ledger — Dashboard",
  description: "Property Management System Dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${publicSans.variable} ${fraunces.variable} ${ibmMono.variable}`}>
      <body className={publicSans.className}>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
