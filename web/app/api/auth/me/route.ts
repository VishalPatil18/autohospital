import { NextRequest, NextResponse } from "next/server";

interface JwtPayload {
  sub: string;
  email?: string;
  role?: string;
  first_name?: string;
  last_name?: string;
  exp?: number;
}

function decodeJwtPayload(token: string): JwtPayload | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;

    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
    const json = atob(padded);
    return JSON.parse(json) as JwtPayload;
  } catch {
    return null;
  }
}

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function GET(request: NextRequest) {
  const accessToken = request.cookies.get("access_token")?.value;

  if (!accessToken) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  // First try to verify with the backend (authoritative check)
  try {
    const backendRes = await fetch(`${BACKEND_URL}/auth/me`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        Accept: "application/json",
      },
    });

    if (backendRes.ok) {
      const data = await backendRes.json();
      // Normalize field names for the frontend
      return NextResponse.json({
        user: {
          id: data.id ?? data.sub ?? "",
          email: data.email ?? "",
          role: data.role ?? "patient",
          first_name: data.first_name ?? data.firstName ?? "",
          last_name: data.last_name ?? data.lastName ?? "",
        },
      });
    }

    if (backendRes.status === 401) {
      return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
    }
  } catch {
    // Backend unreachable — fall through to local decode
  }

  // Fallback: decode locally (no signature verification)
  const payload = decodeJwtPayload(accessToken);
  if (!payload) {
    return NextResponse.json({ detail: "Invalid token" }, { status: 401 });
  }

  // Check token expiry
  if (payload.exp && Date.now() / 1000 > payload.exp) {
    return NextResponse.json({ detail: "Token expired" }, { status: 401 });
  }

  return NextResponse.json({
    user: {
      id: payload.sub,
      email: payload.email ?? "",
      role: payload.role ?? "patient",
      first_name: payload.first_name ?? "",
      last_name: payload.last_name ?? "",
    },
  });
}
