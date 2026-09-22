import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";
import { ACCESS_COOKIE, REFRESH_COOKIE, clearAuthCookies } from "@/lib/auth-cookies";

export async function POST(request: NextRequest) {
  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;

  if (access && refresh) {
    await backendFetch("/api/auth/logout/", {
      method: "POST",
      headers: { Authorization: `Bearer ${access}` },
      body: JSON.stringify({ refresh }),
    }).catch(() => {});
  }

  const response = NextResponse.json({ ok: true });
  clearAuthCookies(response);
  return response;
}
