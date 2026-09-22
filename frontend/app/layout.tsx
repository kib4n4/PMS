import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

import { AuthProvider } from "@/lib/auth-context";

const ibmSans = IBM_Plex_Sans({
  variable: "--font-sans",
  weight: ["400", "500", "600", "700"],
  subsets: ["latin"],
});

const ibmMono = IBM_Plex_Mono({
  variable: "--font-mono",
  weight: ["400", "500", "600", "700"],
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
    <html lang="en" className={`${ibmSans.variable} ${ibmMono.variable}`}>
      <body className={ibmSans.className}>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
