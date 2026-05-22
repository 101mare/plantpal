import type { Me, Plant, Stats, UserSettings } from "./types";

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

function readCookie(name: string): string {
  const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${name}=([^;]+)`));
  return match ? decodeURIComponent(match[1]) : "";
}

async function toError(resp: Response): Promise<ApiError> {
  let code = "error";
  let message = resp.statusText;
  try {
    const body = await resp.json();
    if (body?.error) {
      code = body.error.code ?? code;
      message = body.error.message ?? message;
    }
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(resp.status, code, message);
}

type Method = "GET" | "POST" | "PATCH" | "DELETE";

async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (method !== "GET") headers["X-CSRF-Token"] = readCookie("plantpal_csrf");

  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const resp = await fetch(path, { method, headers, body: payload, credentials: "include" });
  if (!resp.ok) throw await toError(resp);
  if (resp.status === 204) return undefined as T;
  const text = await resp.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export const api = {
  me: () => request<Me>("GET", "/api/me"),
  requestLogin: (email: string) => request("POST", "/auth/request-login", { email }),
  register: (invite_token: string, email: string) =>
    request("POST", "/auth/register", { invite_token, email }),
  logout: () => request("POST", "/auth/logout"),

  listPlants: () => request<{ items: Plant[] }>("GET", "/api/plants").then((r) => r.items),
  createPlant: (form: FormData) => request<Plant>("POST", "/api/plants", form),
  updatePlant: (
    id: number,
    patch: Partial<Pick<Plant, "name" | "interval_days" | "notes" | "water_amount_ml">>,
  ) => request<Plant>("PATCH", `/api/plants/${id}`, patch),
  deletePlant: (id: number) => request("DELETE", `/api/plants/${id}`),
  waterPlant: (id: number) => request<Plant>("POST", `/api/plants/${id}/water`),
  uploadImage: (id: number, form: FormData) =>
    request<{ image_url: string }>("POST", `/api/plants/${id}/image`, form),

  getSettings: () => request<UserSettings>("GET", "/api/settings"),
  updateSettings: (email_reminders_enabled: boolean) =>
    request("PATCH", "/api/settings", { email_reminders_enabled }),
  getStats: () => request<Stats>("GET", "/api/stats"),
  deleteAccount: () => request("DELETE", "/api/account"),

  createInvite: (email_hint?: string) =>
    request<{ invite_url: string; expires_at: string }>("POST", "/api/admin/invites", {
      email_hint: email_hint ?? null,
    }),
};
