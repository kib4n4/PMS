import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";
import { ACCESS_COOKIE, REFRESH_COOKIE, clearAuthCookies, setAuthCookies } from "@/lib/auth-cookies";

function fetchMe(accessToken: string) {
  return backendFetch("/api/auth/me/", {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

/**
 * GET /api/auth/me — the frontend's single source of truth for "who is
 * logged in." Transparently refreshes once on an expired access token
 * (using the refresh cookie) before giving up, so a page load right at
 * the 15-minute access-token boundary doesn't bounce the user to /login.
 */
export async function GET(request: NextRequest) {
  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;

  if (!access) {
    return NextResponse.json({ detail: "Not authenticated." }, { status: 401 });
  }

  const meResponse = await fetchMe(access);
  if (meResponse.ok) {
    return NextResponse.json(await meResponse.json());
  }

  if (meResponse.status !== 401 || !refresh) {
    const response = NextResponse.json({ detail: "Not authenticated." }, { status: 401 });
    clearAuthCookies(response);
    return response;
  }

  const refreshResponse = await backendFetch("/api/auth/token/refresh/", {
    method: "POST",
    body: JSON.stringify({ refresh }),
  });
  if (!refreshResponse.ok) {
    const response = NextResponse.json({ detail: "Not authenticated." }, { status: 401 });
    clearAuthCookies(response);
    return response;
  }

  const tokens = await refreshResponse.json();
  const retried = await fetchMe(tokens.access);
  if (!retried.ok) {
    const response = NextResponse.json({ detail: "Not authenticated." }, { status: 401 });
    clearAuthCookies(response);
    return response;
  }

  const user = await retried.json();
  const response = NextResponse.json(user);
  setAuthCookies(response, tokens.access, tokens.refresh ?? refresh);
  return response;
}
