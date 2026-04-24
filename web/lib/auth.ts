// Server-side auth utilities for use in Server Components and Route Handlers.
// Note: JWT verification is handled by the FastAPI backend. This module only
// performs a local base64url decode of the JWT payload for quick role reads.

export interface JwtPayload {
  sub: string;
  email?: string;
  role?: string;
  first_name?: string;
  last_name?: string;
  exp?: number;
  iat?: number;
}

export interface CurrentUser {
  id: string;
  email: string;
  role: "patient" | "doctor";
  firstName: string;
  lastName: string;
}

/**
 * Decode a JWT payload (middle section) without verifying the signature.
 * This is safe only when used in trusted server-side code where the token
 * has already been validated by the FastAPI backend.
 */
function decodeJwtPayload(token: string): JwtPayload | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;

    // Base64url → Base64 → decode
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");

    // In the Node.js / Edge runtime, atob is available
    const json = atob(padded);
    return JSON.parse(json) as JwtPayload;
  } catch {
    return null;
  }
}

/**
 * Read and decode the access_token cookie. Returns the current user or null.
 *
 * Usage in a Server Component:
 *   import { cookies } from "next/headers";
 *   const user = getCurrentUser(cookies());
 */
export function getCurrentUser(
  cookieStore: { get: (name: string) => { value: string } | undefined }
): CurrentUser | null {
  const tokenCookie = cookieStore.get("access_token");
  if (!tokenCookie?.value) return null;

  const payload = decodeJwtPayload(tokenCookie.value);
  if (!payload) return null;

  // Check token expiry
  if (payload.exp && Date.now() / 1000 > payload.exp) return null;

  return {
    id: payload.sub,
    email: payload.email ?? "",
    role: (payload.role as "patient" | "doctor") ?? "patient",
    firstName: payload.first_name ?? "",
    lastName: payload.last_name ?? "",
  };
}
