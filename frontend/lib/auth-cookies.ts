// frontend/lib/auth-cookies.ts
// Server-only. JWTs live in httpOnly cookies set by app/api/auth/*
// route handlers — never in localStorage/sessionStorage, so they're not
// reachable from an XSS payload. Lifetimes mirror SIMPLE_JWT in
// backend/config/settings.py.

import { NextResponse } from "next/server";

export const ACCESS_COOKIE = "pms_access";
export const REFRESH_COOKIE = "pms_refresh";

const ACCESS_MAX_AGE = 60 * 15; // 15 minutes — SIMPLE_JWT.ACCESS_TOKEN_LIFETIME
const REFRESH_MAX_AGE = 60 * 60 * 24 * 7; // 7 days — SIMPLE_JWT.REFRESH_TOKEN_LIFETIME

const isProd = process.env.NODE_ENV === "production";

export function setAuthCookies(response: NextResponse, access: string, refresh: string) {
  response.cookies.set(ACCESS_COOKIE, access, {
    httpOnly: true,
    secure: isProd,
    sameSite: "lax",
    path: "/",
    maxAge: ACCESS_MAX_AGE,
  });
  response.cookies.set(REFRESH_COOKIE, refresh, {
    httpOnly: true,
    secure: isProd,
    sameSite: "lax",
    path: "/",
    maxAge: REFRESH_MAX_AGE,
  });
}

export function clearAuthCookies(response: NextResponse) {
  response.cookies.set(ACCESS_COOKIE, "", { path: "/", maxAge: 0 });
  response.cookies.set(REFRESH_COOKIE, "", { path: "/", maxAge: 0 });
}
