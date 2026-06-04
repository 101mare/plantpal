import type { Plant } from "./types";

export type StatusLevel = "ok" | "soon" | "due" | "overdue";

/** Whole days from the date of `iso` to today — local, day-granular. null if unparseable. */
export function daysSince(iso: string): number | null {
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return null;
  const a = new Date(then.getFullYear(), then.getMonth(), then.getDate()).getTime();
  const now = new Date();
  const b = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  return Math.round((b - a) / 86_400_000);
}

/**
 * Graded watering status (replaces the binary thirsty/not — UX-09):
 *  ok       healthy, due in ≥2 days        (green)
 *  soon     due today or tomorrow          (yellow)
 *  due      overdue 1–3 days               (orange)
 *  overdue  overdue 4+ days                (red)
 */
export function plantStatus(p: Plant): StatusLevel {
  if (p.is_thirsty) return p.days_overdue >= 4 ? "overdue" : "due";
  const since = daysSince(p.last_watered_at) ?? 0;
  return p.interval_days - since <= 1 ? "soon" : "ok";
}

/** Tailwind background classes per level (semantic green→red, always paired with a text label). */
export const STATUS_DOT: Record<StatusLevel, string> = {
  ok: "bg-green-600",
  soon: "bg-yellow-400",
  due: "bg-orange-500",
  overdue: "bg-red-600",
};
