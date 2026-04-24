import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    const backendRes = await fetch(`${BACKEND_URL}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body),
    });

    const data = await backendRes.json();

    if (!backendRes.ok) {
      return NextResponse.json(data, { status: backendRes.status });
    }

    // Build the response object
    const response = NextResponse.json(data, { status: 200 });

    // Forward any Set-Cookie headers from the FastAPI backend
    const setCookieHeader = backendRes.headers.get("set-cookie");
    if (setCookieHeader) {
      response.headers.set("set-cookie", setCookieHeader);
    }

    // If the backend returns a token in the body (e.g. { access_token, token_type })
    // set it as an httpOnly cookie as well so the middleware can read it.
    if (data.access_token) {
      response.cookies.set("access_token", data.access_token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        path: "/",
        // Use the expiry from the token if available; default to 8 hours
        maxAge: 60 * 60 * 8,
      });
    }

    return response;
  } catch (error) {
    console.error("[POST /api/auth/login]", error);
    return NextResponse.json(
      { detail: "Internal server error" },
      { status: 500 }
    );
  }
}
