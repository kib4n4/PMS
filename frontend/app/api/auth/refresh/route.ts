import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";
import { REFRESH_COOKIE, clearAuthCookies, setAuthCookies } from "@/lib/auth-cookies";

export async function POST(request: NextRequest) {
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;
  if (!refresh) {
    return NextResponse.json({ detail: "Not authenticated." }, { status: 401 });
  }

  const backendResponse = await backendFetch("/api/auth/token/refresh/", {
    method: "POST",
    body: JSON.stringify({ refresh }),
  });
  const data = await backendResponse.json().catch(() => ({}));

  if (!backendResponse.ok) {
    const response = NextResponse.json(data, { status: backendResponse.status });
    clearAuthCookies(response);
    return response;
  }

  const response = NextResponse.json({ ok: true });
  setAuthCookies(response, data.access, data.refresh ?? refresh);
  return response;
}
