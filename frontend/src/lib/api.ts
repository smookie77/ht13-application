import type { Availability, EventDetail, Reservation, Ticket, User } from "./types";

/**
 * Base URL of the Django API.
 *
 * NEXT_PUBLIC_ because client components call it too. It is a public URL, not
 * a secret - no credential is ever inlined into the bundle.
 */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly data: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Pulls the first human-readable message out of a DRF error body, which can be
 * `{detail}`, `{field: [msg]}` or a bare list.
 */
export function errorMessage(error: unknown, fallback = "Something went wrong."): string {
  if (!(error instanceof ApiError)) return fallback;
  const data = error.data;
  if (typeof data === "string") return data;
  if (data && typeof data === "object") {
    const record = data as Record<string, unknown>;
    if (typeof record.detail === "string") return record.detail;
    for (const value of Object.values(record)) {
      if (typeof value === "string") return value;
      if (Array.isArray(value) && typeof value[0] === "string") return value[0];
    }
  }
  return error.message || fallback;
}

/**
 * Auth uses an httpOnly session cookie rather than a token in JS, so a XSS bug
 * cannot read the credential. The cost is CSRF, which this token covers - it
 * is read from the API's JSON response, not from document.cookie, so it also
 * works when the SPA and API sit on different domains in production.
 */
let csrfToken: string | null = null;

async function ensureCsrfToken(): Promise<string> {
  if (csrfToken) return csrfToken;
  const response = await fetch(`${API_BASE_URL}/api/auth/csrf/`, {
    credentials: "include",
  });
  if (!response.ok) throw new ApiError("Could not start a session.", response.status);
  csrfToken = (await response.json()).csrfToken;
  return csrfToken!;
}

async function request<T>(
  path: string,
  { method = "GET", body, retryOnCsrfFailure = true }: {
    method?: string;
    body?: unknown;
    retryOnCsrfFailure?: boolean;
  } = {},
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const isUnsafe = method !== "GET" && method !== "HEAD";
  if (isUnsafe) headers["X-CSRFToken"] = await ensureCsrfToken();

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    credentials: "include",
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  // A rotated or expired CSRF token looks like a 403; fetch a fresh one once.
  if (response.status === 403 && isUnsafe && retryOnCsrfFailure) {
    csrfToken = null;
    return request<T>(path, { method, body, retryOnCsrfFailure: false });
  }

  if (response.status === 204) return undefined as T;

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(`${method} ${path} failed`, response.status, data);
  }
  return data as T;
}

// --- Events (also called from Server Components) -----------------------------
// Ticket stock changes by the second, so nothing here is cached. Next 16 leaves
// `fetch` uncached by default, which is exactly what a live counter needs.

export function getEvent(slug: string): Promise<EventDetail> {
  return request<EventDetail>(`/api/events/${slug}/`);
}

export function getAvailability(slug: string): Promise<Availability> {
  return request<Availability>(`/api/events/${slug}/availability/`);
}

// --- Auth --------------------------------------------------------------------

export function register(input: {
  email: string;
  full_name: string;
  password: string;
}): Promise<{ detail: string }> {
  return request("/api/auth/register/", { method: "POST", body: input });
}

export function login(input: { email: string; password: string }): Promise<User> {
  return request("/api/auth/login/", { method: "POST", body: input });
}

export function logout(): Promise<void> {
  return request("/api/auth/logout/", { method: "POST" });
}

export function me(): Promise<User> {
  return request("/api/auth/me/");
}

export function verifyEmail(token: string): Promise<{ detail: string; user: User }> {
  return request("/api/auth/verify/", { method: "POST", body: { token } });
}

export function resendVerification(email: string): Promise<{ detail: string }> {
  return request("/api/auth/resend-verification/", { method: "POST", body: { email } });
}

// --- Reservations ------------------------------------------------------------

export function createReservation(input: {
  ticket_type_id: number;
  quantity?: number;
}): Promise<Reservation> {
  return request("/api/reservations/", { method: "POST", body: input });
}

export function getReservation(publicId: string): Promise<Reservation> {
  return request(`/api/reservations/${publicId}/`);
}

export function listReservations(): Promise<{ results: Reservation[] }> {
  return request("/api/reservations/");
}

export function confirmReservation(publicId: string): Promise<Reservation> {
  return request(`/api/reservations/${publicId}/confirm/`, { method: "POST" });
}

export function cancelReservation(publicId: string): Promise<Reservation> {
  return request(`/api/reservations/${publicId}/cancel/`, { method: "POST" });
}

// --- Tickets -----------------------------------------------------------------

export function listTickets(): Promise<{ results: Ticket[] }> {
  return request("/api/tickets/");
}

/**
 * Absolute URL for the download endpoint. The browser is sent there directly so
 * the session cookie rides along and the API can redirect to a signed storage
 * URL - the bucket itself is never public.
 */
export function ticketDownloadUrl(code: string): string {
  return `${API_BASE_URL}/api/tickets/${code}/download/`;
}

export function checkInTicket(code: string): Promise<Ticket> {
  return request("/api/tickets/check-in/", { method: "POST", body: { code } });
}
