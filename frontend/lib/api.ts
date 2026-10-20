// Typed fetch wrapper for the NetLinks API. Adds the demo role headers from the current identity.
// The headers are a demo simplification: the API enforces role permissions server-side, and
// production would use Cognito tokens instead.

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export interface ApiIdentity {
  role: string;
  sme_slug: string | null;
}

let currentIdentity: ApiIdentity | null = null;

/** Called by the identity provider whenever the demo role changes. */
export function setApiIdentity(identity: ApiIdentity | null): void {
  currentIdentity = identity;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

const STATUS_PREFIX: Record<number, string> = {
  401: "Not signed in with a demo role",
  403: "Not allowed for this role",
  409: "Conflict",
  413: "File too large",
  422: "Please check the input",
  503: "Service unavailable",
};

function detailText(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : String(d)))
      .join("; ");
  }
  return "";
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (currentIdentity) {
    headers["X-Demo-Role"] = currentIdentity.role;
    if (currentIdentity.sme_slug) headers["X-Demo-Sme-Id"] = currentIdentity.sme_slug;
  }
  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { method, headers, body: payload, cache: "no-store" });
  } catch {
    throw new ApiError(0, `Cannot reach the NetLinks API at ${API_URL}. Is the backend running?`);
  }
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data ? detailText((data as { detail: unknown }).detail) : "";
    const prefix = STATUS_PREFIX[res.status] || `Request failed (${res.status})`;
    throw new ApiError(res.status, detail ? `${prefix}: ${detail}` : prefix);
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
};

export function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}
