import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Proxies doctor chat SSE from FastAPI so the browser can use same-origin
 * /api/chat/doctor with httpOnly cookie → Bearer forwarded to backend.
 */
export async function POST(request: NextRequest) {
  const accessToken = request.cookies.get("access_token")?.value;

  if (!accessToken) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }

  const body = await request.text();

  const backendRes = await fetch(`${BACKEND_URL}/api/chat/doctor`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
      Accept: "text/event-stream",
    },
    body,
  });

  if (!backendRes.ok || !backendRes.body) {
    const text = await backendRes.text();
    try {
      return NextResponse.json(JSON.parse(text) as object, { status: backendRes.status });
    } catch {
      return NextResponse.json(
        { detail: text || "Upstream error" },
        { status: backendRes.status }
      );
    }
  }

  return new NextResponse(backendRes.body, {
    status: backendRes.status,
    headers: {
      "Content-Type": backendRes.headers.get("content-type") ?? "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
      Connection: "keep-alive",
    },
  });
}
