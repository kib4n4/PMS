"use client";

import { FormEvent, Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { BuildingIcon } from "@/components/Icons";
import { useAuth } from "@/lib/auth-context";
import { loginWithPassword, requestOtp, verifyOtp } from "@/lib/auth";

const ROLE_HOME: Record<string, string> = {
  landlord: "/landlord",
  reseller: "/reseller",
  investor: "/investor",
  caretaker: "/caretaker",
  admin: "/admin",
  tenant: "/",
};

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { refresh } = useAuth();

  const [mode, setMode] = useState<"password" | "otp">("password");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [code, setCode] = useState("");
  const [otpRequested, setOtpRequested] = useState(false);
  const [debugCode, setDebugCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function afterLogin(user: { role: string; is_super_admin: boolean }) {
    await refresh();
    const next = searchParams.get("next");
    const destination = next || (user.is_super_admin ? "/admin" : ROLE_HOME[user.role] ?? "/");
    router.push(destination);
  }

  async function handlePasswordSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const { user } = await loginWithPassword(username, password);
      await afterLogin(user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleOtpRequest(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const result = await requestOtp(phoneNumber);
      setOtpRequested(true);
      setDebugCode(result.debug_code ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send a code.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleOtpVerify(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const { user } = await verifyOtp(phoneNumber, code);
      await afterLogin(user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid or expired code.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-mist-50 p-6">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-surface p-8 shadow-ledger">
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-500">
            <BuildingIcon className="h-6 w-6 text-white" />
          </div>
          <div>
            <p className="text-lg font-semibold text-ink-900">Ledger</p>
            <p className="text-xs text-ink-500">Sign in to your account</p>
          </div>
        </div>

        <div className="mb-6 flex gap-1 rounded-lg bg-mist-100/70 p-1 text-sm font-medium">
          <button
            type="button"
            onClick={() => {
              setMode("password");
              setError(null);
            }}
            className={`flex-1 rounded-md py-1.5 transition-colors ${
              mode === "password" ? "bg-surface text-ink-900 shadow-sm" : "text-ink-500"
            }`}
          >
            Username
          </button>
          <button
            type="button"
            onClick={() => {
              setMode("otp");
              setError(null);
            }}
            className={`flex-1 rounded-md py-1.5 transition-colors ${
              mode === "otp" ? "bg-surface text-ink-900 shadow-sm" : "text-ink-500"
            }`}
          >
            Phone (OTP)
          </button>
        </div>

        {error && <p className="mb-4 rounded-lg bg-rust-50 px-3 py-2 text-sm text-rust-700">{error}</p>}

        {mode === "password" ? (
          <form onSubmit={handlePasswordSubmit} className="space-y-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-ink-600">Username</label>
              <input
                required
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full rounded-lg border border-border px-3 py-2 text-sm text-ink-900 focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-ink-600">Password</label>
              <input
                required
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-border px-3 py-2 text-sm text-ink-900 focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
            </div>
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-lg bg-teal-500 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-600 disabled:opacity-60"
            >
              {isSubmitting ? "Signing in…" : "Sign in"}
            </button>
          </form>
        ) : otpRequested ? (
          <form onSubmit={handleOtpVerify} className="space-y-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-ink-600">6-digit code</label>
              <input
                required
                autoFocus
                inputMode="numeric"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                className="w-full rounded-lg border border-border px-3 py-2 text-center text-lg tracking-[0.5em] text-ink-900 focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
              {debugCode && (
                <p className="mt-2 text-xs text-amber-700">
                  Dev mode — delivery channel not wired yet. Your code:{" "}
                  <span className="font-mono font-semibold">{debugCode}</span>
                </p>
              )}
            </div>
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-lg bg-teal-500 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-600 disabled:opacity-60"
            >
              {isSubmitting ? "Verifying…" : "Verify & sign in"}
            </button>
            <button
              type="button"
              onClick={() => {
                setOtpRequested(false);
                setCode("");
                setDebugCode(null);
              }}
              className="w-full text-center text-xs text-ink-500 hover:text-ink-700"
            >
              Use a different number
            </button>
          </form>
        ) : (
          <form onSubmit={handleOtpRequest} className="space-y-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-ink-600">Phone number</label>
              <input
                required
                autoFocus
                type="tel"
                placeholder="+2547XXXXXXXX"
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
                className="w-full rounded-lg border border-border px-3 py-2 text-sm text-ink-900 focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
            </div>
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-lg bg-teal-500 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-600 disabled:opacity-60"
            >
              {isSubmitting ? "Sending…" : "Send code"}
            </button>
          </form>
        )}

        <p className="mt-6 text-center text-xs text-ink-400">
          <Link href="/" className="hover:text-ink-600">
            Back to role overview
          </Link>
        </p>
      </div>
    </main>
  );
}
