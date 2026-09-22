// frontend/lib/auth.ts
// Client-side calls — always hit this Next.js app's own /api/auth/*
// routes, never Django directly, so the JWTs never touch browser JS.

import { CurrentUser } from "./auth-context";

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || "Something went wrong. Please try again.");
  }
  return data as T;
}

export function loginWithPassword(username: string, password: string) {
  return postJson<{ user: CurrentUser }>("/api/auth/login", { username, password });
}

export function requestOtp(phoneNumber: string) {
  return postJson<{ detail: string; debug_code?: string }>("/api/auth/otp/request", {
    phone_number: phoneNumber,
  });
}

export function verifyOtp(phoneNumber: string, code: string) {
  return postJson<{ user: CurrentUser }>("/api/auth/otp/verify", {
    phone_number: phoneNumber,
    code,
  });
}
