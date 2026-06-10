import type {
  InviteCreated,
  InviteListItem,
  Me,
  Plant,
  SettingsPatch,
  Stats,
  UserSettings,
} from "./types";

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

/** API origin override for the Capacitor build: the bundled app runs on capacitor://localhost,
 *  so relative /api paths must point at the hosted backend (VITE_API_BASE=https://getplantpal.com
 *  at build time). Empty in the web build → same-origin paths, exactly as before. */
const API_BASE: string = import.meta.env.VITE_API_BASE ?? "";

/** Absolute URL for server-served assets referenced in markup (<img src>): plant.image_url is
 *  a RELATIVE path from the API — in the shell it must point at the backend, not the bundle.
 *  Bundled statics (/placeholder.png, /sprites/…) must NOT go through this. */
export const assetUrl = (path: string): string => API_BASE + path;

/** Native shell (Capacitor): no SameSite cookies on the API origin and document.cookie can't
 *  read a cross-origin CSRF cookie — the shell authenticates via Authorization: Bearer with a
 *  session token handed over by /auth/verify-code (client:"app"). Web builds: inert. */
const NATIVE: boolean =
  typeof window !== "undefined" &&
  Boolean(
    (
      window as { Capacitor?: { isNativePlatform?: () => boolean } }
    ).Capacitor?.isNativePlatform?.(),
  );

let appToken: string | null = null;
try {
  appToken = NATIVE ? localStorage.getItem("pp_app_token") : null;
} catch {
  appToken = null;
}
function setAppToken(token: string | null): void {
  appToken = token;
  try {
    if (token) localStorage.setItem("pp_app_token", token);
    else localStorage.removeItem("pp_app_token");
  } catch {
    /* storage unavailable → in-memory token still works for this run */
  }
}

async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (appToken) headers["Authorization"] = `Bearer ${appToken}`;
  if (method !== "GET") headers["X-CSRF-Token"] = readCookie("plantpal_csrf");

  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const resp = await fetch(API_BASE + path, {
    method,
    headers,
    body: payload,
    credentials: "include",
  });
  if (!resp.ok) throw await toError(resp);
  if (resp.status === 204) return undefined as T;
  const text = await resp.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

type PlantPatch = Partial<
  Pick<Plant, "name" | "interval_days" | "notes" | "water_amount_ml" | "location_room">
>;

export const api = {
  me: () => request<Me>("GET", "/api/me"),
  requestLogin: (email: string) => request("POST", "/auth/request-login", { email }),
  verifyCode: async (email: string, code: string) => {
    const res = await request<{ ok: boolean; session_token?: string }>(
      "POST",
      "/auth/verify-code",
      { email, code, ...(NATIVE ? { client: "app" } : {}) },
    );
    if (res?.session_token) setAppToken(res.session_token);
    return res;
  },
  register: (invite_token: string, email: string) =>
    request("POST", "/auth/register", { invite_token, email }),
  logout: async () => {
    const res = await request("POST", "/auth/logout");
    setAppToken(null);
    return res;
  },

  listPlants: () => request<{ items: Plant[] }>("GET", "/api/plants").then((r) => r.items),
  createPlant: (form: FormData) => request<Plant>("POST", "/api/plants", form),
  updatePlant: (id: number, patch: PlantPatch) =>
    request<Plant>("PATCH", `/api/plants/${id}`, patch),
  deletePlant: (id: number) => request("DELETE", `/api/plants/${id}`),
  waterPlant: (id: number) => request<Plant>("POST", `/api/plants/${id}/water`),
  uploadImage: (id: number, form: FormData) =>
    request<{ image_url: string }>("POST", `/api/plants/${id}/image`, form),

  getSettings: () => request<UserSettings>("GET", "/api/settings"),
  updateSettings: (patch: SettingsPatch) => request("PATCH", "/api/settings", patch),
  getStats: () => request<Stats>("GET", "/api/stats"),
  // v2 Spross: raise the durable server high-water-mark (server applies max(), so it only climbs).
  updateSprossProgress: (stageMax: number, peakVitality: number) =>
    request<{ vitality_stage_max: number; peak_vitality: number }>("POST", "/api/spross/progress", {
      stage_max: stageMax,
      peak_vitality: peakVitality,
    }),
  deleteAccount: async () => {
    const res = await request("DELETE", "/api/account");
    setAppToken(null);
    return res;
  },
  exportUrl: () => "/api/account/export",

  // user invites (quota-checked, multi-use)
  listInvites: () =>
    request<{ items: InviteListItem[] }>("GET", "/api/invites").then((r) => r.items),
  createUserInvite: (max_uses: number, expires_in_days?: number) =>
    request<InviteCreated>("POST", "/api/invites", { max_uses, expires_in_days }),
  revokeInvite: (id: number) => request("POST", `/api/invites/${id}/revoke`),

  // email change
  requestEmailChange: (new_email: string) => request("POST", "/api/account/email", { new_email }),
};
