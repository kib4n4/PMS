// frontend/lib/authenticated-backend-fetch.ts
// Server-only. Shared "resolve a valid Bearer token for this request,
// silently refreshing once via the refresh cookie if the access token has
// expired" logic — the same dance app/api/auth/me/route.ts already proves
// out, extracted so the dashboard-data proxy routes below don't each
// reimplement it. Route handlers call resolveAccessToken() once, then use
// the returned token for as many backendFetch() calls as they need.

import { NextRequest } from "next/server";
import { backendFetch } from "@/lib/backend";
import { ACCESS_COOKIE, REFRESH_COOKIE } from "@/lib/auth-cookies";

export type ResolvedAccessToken = {
  accessToken: string;
  /** Set only when a refresh actually happened — callers should persist
   * these onto the response with setAuthCookies() so the browser's cookie
   * catches up; the resolved accessToken itself is always safe to use for
   * this request's own backend calls regardless. */
  refreshedTokens: { access: string; refresh: string } | null;
};

export async function resolveAccessToken(request: NextRequest): Promise<ResolvedAccessToken | null> {
  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;
  if (!access) return null;

  const probe = await backendFetch("/api/auth/me/", {
    headers: { Authorization: `Bearer ${access}` },
  });
  if (probe.ok) {
    return { accessToken: access, refreshedTokens: null };
  }
  if (probe.status !== 401 || !refresh) {
    return null;
  }

  const refreshResponse = await backendFetch("/api/auth/token/refresh/", {
    method: "POST",
    body: JSON.stringify({ refresh }),
  });
  if (!refreshResponse.ok) {
    return null;
  }

  const tokens = await refreshResponse.json();
  return {
    accessToken: tokens.access,
    refreshedTokens: { access: tokens.access, refresh: tokens.refresh ?? refresh },
  };
}

export function authHeaders(accessToken: string): HeadersInit {
  return { Authorization: `Bearer ${accessToken}` };
}

/** Parses a backendFetch() JSON response, treating a non-2xx or unparsable
 * body as "no data" rather than throwing — dashboard widgets should
 * degrade to an empty state, not crash the whole page, if one backend
 * call fails. */
export async function safeJson<T>(response: Response, fallback: T): Promise<T> {
  if (!response.ok) return fallback;
  try {
    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}
