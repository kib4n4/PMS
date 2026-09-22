import { NextRequest, NextResponse } from "next/server";

const ACCESS_COOKIE = "pms_access";

// Route-level RBAC gate — the real enforcement lives in DRF permission
// classes (accounts/permissions.py); this is the UX layer that stops a
// wrong-role user from ever rendering someone else's dashboard. Super
// admin (is_super_admin claim) always passes every check.
const ROLE_ROUTES: Record<string, string[] | "super_admin_only"> = {
  "/landlord": ["landlord"],
  "/reseller": ["reseller"],
  "/investor": ["investor"],
  "/caretaker": ["caretaker"],
  "/admin": "super_admin_only",
};

type JwtPayload = { role?: string; is_super_admin?: boolean };

function decodeJwtPayload(token: string): JwtPayload | null {
  try {
    const [, payload] = token.split(".");
    if (!payload) return null;
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
    return JSON.parse(atob(padded));
  } catch {
    return null;
  }
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const matchedRoute = Object.keys(ROLE_ROUTES).find(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
  if (!matchedRoute) {
    return NextResponse.next();
  }

  const token = request.cookies.get(ACCESS_COOKIE)?.value;
  const payload = token ? decodeJwtPayload(token) : null;

  if (!payload) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  const isSuperAdmin = Boolean(payload.is_super_admin);
  const allowed = ROLE_ROUTES[matchedRoute];
  const roleAllowed = isSuperAdmin || (allowed !== "super_admin_only" && allowed.includes(payload.role ?? ""));

  if (!roleAllowed) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/landlord/:path*", "/reseller/:path*", "/investor/:path*", "/caretaker/:path*", "/admin/:path*"],
};
