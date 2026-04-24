import { NextRequest, NextResponse } from "next/server";

// Simple base64url decoder that works in the Edge runtime
function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;

    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
    const json = atob(padded);
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // ── Public routes — always allow ──────────────────────────────────────────
  if (
    pathname.startsWith("/login") ||
    pathname.startsWith("/register") ||
    pathname.startsWith("/api/") ||
    pathname.startsWith("/_next/") ||
    pathname === "/favicon.ico"
  ) {
    return NextResponse.next();
  }

  const accessToken = request.cookies.get("access_token")?.value;

  // ── Not authenticated → redirect to login ─────────────────────────────────
  if (!accessToken) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Decode JWT to read role (no verification — FastAPI verifies on API calls)
  const payload = decodeJwtPayload(accessToken);

  // Expired token
  if (payload?.exp && typeof payload.exp === "number" && Date.now() / 1000 > payload.exp) {
    const loginUrl = new URL("/login", request.url);
    const response = NextResponse.redirect(loginUrl);
    response.cookies.set("access_token", "", { maxAge: 0, path: "/" });
    return response;
  }

  const role = typeof payload?.role === "string" ? payload.role : null;

  // ── Role-based guards ─────────────────────────────────────────────────────

  if (pathname.startsWith("/patient/")) {
    if (role === "doctor") {
      return NextResponse.redirect(new URL("/doctor/dashboard", request.url));
    }
  }

  if (pathname.startsWith("/doctor/")) {
    if (role === "patient") {
      return NextResponse.redirect(new URL("/patient/dashboard", request.url));
    }
  }

  // ── Root "/" redirect (in case middleware catches it before page.tsx) ─────
  if (pathname === "/") {
    if (role === "doctor") {
      return NextResponse.redirect(new URL("/doctor/dashboard", request.url));
    }
    return NextResponse.redirect(new URL("/patient/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except static files and Next.js internals.
     * The pattern below excludes:
     *   - _next/static (static files)
     *   - _next/image (image optimization)
     *   - favicon.ico
     */
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
