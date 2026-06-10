import type { Plant } from "./types";

type Translate = (key: string, vars?: Record<string, string | number>) => string;

export type StatusLevel = "ok" | "soon" | "due" | "overdue";

/** Today in Berlin as YYYY-MM-DD. The backend stores naive-Berlin wall-clock timestamps,
 *  so day math must be done in Berlin time, not the viewer's local zone (N37). */
export function berlinToday(): string {
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
    if (p.days_overdue === 1) return t("plant.overdueOne"); // "1 Tag", nicht "1 Tage"
    return p.days_overdue >= 1 ? t("plant.overdue", { n: p.days_overdue }) : t("status.dueToday");
  }
  return t(level === "soon" ? "status.soon" : "status.ok");
}

/** Compact glance label for band rows + card badges: a number or one word, never a sentence
 *  ("heute" | "2d über"). Fixed vocabulary at a fixed slot; the long statusText stays for
 *  aria-labels. The "d" unit is a deliberate cross-language convention (de+en). */
export function statusShort(p: Plant, t: Translate): string {
  const level = plantStatus(p);
  if (level === "due" || level === "overdue") {
    return p.days_overdue >= 1
      ? t("status.overShort", { n: p.days_overdue })
      : t("status.todayShort");
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

/** Spross's mood = the COLLECTIVE plant-health signal (the gamification "mirror"). One of the five
 *  frames in every sprite sheet. Pure + UI-free so it sits next to plantStatus() and is unit-tested. */
export type SprossMood = "wohl" | "bluehend" | "durstig" | "welkend" | "neugierig";

/**
 * Map the whole-collection state to a Spross mood. Order matters:
 *  - justReturned wins (transient "welcome back" greeting, decays to the real mood).
 *  - distress (welkend) before mild thirst (durstig) before the calm baseline.
 *  - bluehend only when nothing is thirsty AND care has been consistent — it can only ever
 *    UPGRADE in quietly; default to "wohl" while consistency is still unknown (no downgrade-flash).
 */
export function sprossMood(i: {
  thirstyCount: number;
  longestOverdueDays: number;
  consistencyPct?: number;
  justReturned: boolean;
}): SprossMood {
  if (i.justReturned) return "neugierig";
  if (i.thirstyCount >= 5 || i.longestOverdueDays > 7) return "welkend";
  if (i.thirstyCount >= 2) return "durstig";
  if (i.thirstyCount === 0 && (i.consistencyPct ?? 0) >= 80) return "bluehend";
  return "wohl";
}

// --- v2 evolution: a frontend "vitality" proxy -> stage 1..6. Pure + unit-tested; 100% from the
//     existing /api/stats fields + plant ages (created_at). No backend. The displayed stage is
//     ratcheted (high-water-mark) in sprossState.ts so it only ever climbs. ---

export type Stage = 1 | 2 | 3 | 4 | 5 | 6;

/** Vitality thresholds: the highest threshold <= v wins -> stage (index+1). All knobs tunable. */
export const STAGE_THRESHOLDS = [0, 15, 30, 48, 65, 83];
const CARE_W = 0.7;
const PRESENCE_W = 0.3;
const STREAK_CAP = 30;
const TENURE_FLOOR = 0.2;
const TENURE_DAYS = 120;

const clampPct = (n: number) => Math.max(0, Math.min(100, n));

/** Oldest plant's age in days (the tenure signal). Reuses daysSince(created_at). */
export function oldestPlantAgeDays(plants: { created_at: string }[]): number {
  let max = 0;
  for (const p of plants) max = Math.max(max, daysSince(p.created_at) ?? 0);
  return max;
}

/**
 * 0..100 "vitality" = MULTIPLICATIVE care-quality × tenure, so care beats collecting (a hoarder with
 * low consistency stays low) AND growth is earned over time (a day-0 perfectionist can't sprint to
 * the top because tenure ≈ floor). `consistencyReliable=false` means every plant's interval > 30d,
 * so the server's 30-day consistency window is structurally empty and returns a bogus 100 — we then
 * drop consistency and lean on the streak, defeating the "bogus-100 mints a high stage" trap.
 */
export function vitalityScore(
  stats:
    | { watering_consistency_pct: number; watering_streak_days: number; total_plants: number }
    | undefined,
  oldestAgeDays: number,
  consistencyReliable: boolean,
): number {
  if (!stats || stats.total_plants === 0) return 0;
  const care = clampPct(stats.watering_consistency_pct) / 100;
  const presence = Math.min(stats.watering_streak_days / STREAK_CAP, 1);
  const careQ = consistencyReliable ? CARE_W * care + PRESENCE_W * presence : presence;
  const tenure = TENURE_FLOOR + (1 - TENURE_FLOOR) * Math.min(oldestAgeDays / TENURE_DAYS, 1);
  return Math.round(clampPct(100 * careQ * tenure));
}

/** Map vitality 0..100 to a stage 1..6 (highest threshold <= v wins). */
export function stageFromVitality(v: number): Stage {
  let stage: Stage = 1;
  for (let i = 0; i < STAGE_THRESHOLDS.length; i++) {
    if (v >= STAGE_THRESHOLDS[i]) stage = (i + 1) as Stage;
  }
  return stage;
}

/** Conservative re-seed floor: a long-tended account that lost its local store (iOS PWA storage
 *  eviction, cleared cache, new device) must NOT reappear as a Keimling. Capped at Blattgeist (3)
 *  so tenure alone never mints a prestige stage. Only applied on first hydrate. */
export function tenureFloorStage(oldestAgeDays: number): Stage {
  if (oldestAgeDays >= 120) return 3;
  if (oldestAgeDays >= 30) return 2;
  return 1;
}

/** Vitality band of a stage: [start, end). `end` is null at stage 6 (no next threshold). */
export function stageBand(stage: Stage): { start: number; end: number | null } {
  return { start: STAGE_THRESHOLDS[stage - 1], end: stage < 6 ? STAGE_THRESHOLDS[stage] : null };
}

/** Monotonic growth-bar fill (0..1) from PEAK vitality within the current stage band. Stage 6 = full.
 *  Clamped, so a server/tenure-floored stage above the peak's natural band never underflows. */
export function growthFraction(peakVitality: number, stage: Stage): number {
  const { start, end } = stageBand(stage);
  if (end === null) return 1;
  return Math.max(0, Math.min(1, (peakVitality - start) / (end - start)));
}
