import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(request: NextRequest) {
  try {
    // Forward the request to FastAPI (best-effort; ignore errors)
    const accessToken = request.cookies.get("access_token")?.value;

    await fetch(`${BACKEND_URL}/auth/logout`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        // Forward cookies so the backend can invalidate any server-side session
        cookie: request.headers.get("cookie") ?? "",
      },
    }).catch(() => {
      // ignore backend errors on logout
    });

    // Build a response that clears the access_token cookie
    const response = NextResponse.json({ message: "Logged out" }, { status: 200 });

    response.cookies.set("access_token", "", {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 0,
    });

    return response;
  } catch (error) {
    console.error("[POST /api/auth/logout]", error);
    return NextResponse.json(
      { detail: "Internal server error" },
      { status: 500 }
    );
  }
}
