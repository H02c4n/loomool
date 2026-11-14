import type { Cart } from "./types";

export class ApiError extends Error {
  status: number;
  body: string;
  constructor(status: number, body: string) {
    super(`API ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

const INTERNAL_API =
  process.env.INTERNAL_API_BASE_URL ?? "http://backend:8000";
const PUBLIC_API =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function apiBase(): string {
  return typeof window === "undefined" ? INTERNAL_API : PUBLIC_API;
}

export interface GetOpts {
  cookies?: string;
  cache?: RequestCache;
  next?: { revalidate?: number };
}

export async function apiGet<T>(
  path: string,
  params?: Record<string, string | number | undefined>,
  opts: GetOpts = {}
): Promise<T> {
  const url = new URL(path, apiBase());
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== "") url.searchParams.set(k, String(v));
    }
  }
  const res = await fetch(url.toString(), {
    headers: {
      Accept: "application/json",
      ...(opts.cookies ? { Cookie: opts.cookies } : {}),
    },
    cache: opts.cache,
    next: opts.next,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body);
  }
  return (await res.json()) as T;
}

export async function apiMutate<T>(
  method: "POST" | "PATCH" | "DELETE",
  path: string,
  body?: unknown
): Promise<T | null> {
  const url = new URL(path, apiBase());
  const csrf = await ensureCsrf();
  const res = await fetch(url.toString(), {
    method,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(csrf ? { "X-CSRFToken": csrf } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let msg = `API ${res.status}`;
    try {
      const j = (await res.json()) as Record<string, unknown>;
      if (typeof j.detail === "string") {
        msg = j.detail;
      } else {
        // Field-level errors: { password: ["Too short", ...] }
        for (const [key, val] of Object.entries(j)) {
          if (Array.isArray(val) && val.length > 0 && typeof val[0] === "string") {
            msg = `${key}: ${val[0]}`;
            break;
          }
        }
      }
    } catch {
      /* not JSON */
    }
    throw new Error(msg);
  }
  if (res.status === 204) return null;
  return (await res.json()) as T;
}

let csrfPrimed = false;

export async function ensureCsrf(): Promise<string | null> {
  const existing = getCookie("csrftoken");
  if (existing) return existing;
  if (csrfPrimed) return null;
  csrfPrimed = true;
  try {
    await fetch(`${apiBase()}/api/v1/auth/csrf/`, {
      credentials: "include",
    });
  } catch {
    /* ignore — caller will fail with 403 */
  }
  return getCookie("csrftoken");
}

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(
    new RegExp(`(?:^|; )${name}=([^;]*)`)
  );
  return match ? decodeURIComponent(match[1]) : null;
}

export async function fetchCart(): Promise<Cart> {
  const res = await fetch(`${apiBase()}/api/v1/shop/cart/`, {
    credentials: "include",
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`cart ${res.status}`);
  return (await res.json()) as Cart;
}
