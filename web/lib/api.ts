const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── Core request utility ─────────────────────────────────────────────────────

async function apiRequest<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${path}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  const res = await fetch(url, {
    ...options,
    headers,
    credentials: "include",
  });

  if (!res.ok) {
    let message = `Request failed: ${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      message = body.detail || body.message || message;
    } catch {
      // ignore parse errors
    }
    throw new Error(message);
  }

  // 204 No Content
  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

// ─── Typed helpers ────────────────────────────────────────────────────────────

export function get<T = unknown>(path: string): Promise<T> {
  return apiRequest<T>(path, { method: "GET" });
}

export function post<T = unknown>(path: string, body?: unknown): Promise<T> {
  return apiRequest<T>(path, {
    method: "POST",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

export function patch<T = unknown>(path: string, body?: unknown): Promise<T> {
  return apiRequest<T>(path, {
    method: "PATCH",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

export function postForm<T = unknown>(path: string, formData: FormData): Promise<T> {
  return apiRequest<T>(path, {
    method: "POST",
    // Let the browser set the Content-Type boundary for multipart/form-data
    headers: {},
    body: formData,
  });
}

export default apiRequest;
