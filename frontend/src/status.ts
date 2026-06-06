import type { Plant } from "./types";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

export type StatusLevel = "ok" | "soon" | "due" | "overdue";

/** Today in Berlin as YYYY-MM-DD. The backend stores naive-Berlin wall-clock timestamps,
 *  so day math must be done in Berlin time, not the viewer's local zone (N37). */
function berlinToday(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Berlin" }).format(new Date());
}

/** Whole days from the calendar date of `iso` to today, both in Berlin. null if unparseable.
 *  `iso` is naive-Berlin wall-clock, so its first 10 chars ARE the Berlin date; anchoring both
 *  ends at UTC midnight makes the count independent of the viewer's timezone (N37). */
export function daysSince(iso: string): number | null {
  const then = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(then.getTime())) return null;
  const today = new Date(`${berlinToday()}T00:00:00Z`);
  return Math.round((today.getTime() - then.getTime()) / 86_400_000);
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

/** Localized status line. A plant due *today* reads "due today", not "0 days overdue" (N25). */
export function statusText(p: Plant, t: Translate): string {
  const level = plantStatus(p);
  if (level === "due" || level === "overdue") {
    return p.days_overdue >= 1 ? t("plant.overdue", { n: p.days_overdue }) : t("status.dueToday");
  }
  return t(level === "soon" ? "status.soon" : "status.ok");
}

/** Tailwind background classes per level (semantic green→red, always paired with a text label). */
export const STATUS_DOT: Record<StatusLevel, string> = {
  ok: "bg-green-600",
  soon: "bg-yellow-400",
  due: "bg-orange-500",
  overdue: "bg-red-600",
};
