import { describe, expect, it } from "vitest";
import {
  sprossMood,
  vitalityScore,
  stageFromVitality,
  tenureFloorStage,
  growthFraction,
} from "./status";

describe("sprossMood", () => {
  const base = { thirstyCount: 0, longestOverdueDays: 0, consistencyPct: 0, justReturned: false };

  it("greets (neugierig) on return, overriding everything else", () => {
    expect(sprossMood({ ...base, thirstyCount: 9, justReturned: true })).toBe("neugierig");
  });

  it("is welkend at >=5 thirsty or any plant >7 days overdue", () => {
    expect(sprossMood({ ...base, thirstyCount: 5 })).toBe("welkend");
    expect(sprossMood({ ...base, thirstyCount: 1, longestOverdueDays: 8 })).toBe("welkend");
  });

  it("is durstig at 2-4 thirsty", () => {
    expect(sprossMood({ ...base, thirstyCount: 2 })).toBe("durstig");
    expect(sprossMood({ ...base, thirstyCount: 4 })).toBe("durstig");
  });

  it("blooms only when nothing is thirsty AND consistency >= 80%", () => {
    expect(sprossMood({ ...base, thirstyCount: 0, consistencyPct: 80 })).toBe("bluehend");
    expect(sprossMood({ ...base, thirstyCount: 0, consistencyPct: 79 })).toBe("wohl");
  });

  it("defaults to wohl when consistency is still unknown (no downgrade-flash)", () => {
    expect(sprossMood({ thirstyCount: 0, longestOverdueDays: 0, justReturned: false })).toBe(
      "wohl",
    );
    expect(sprossMood({ ...base, thirstyCount: 1 })).toBe("wohl");
  });
});

describe("vitalityScore / stageFromVitality (v2 evolution)", () => {
  const s = (consistency: number, streak: number, total = 3) => ({
    watering_consistency_pct: consistency,
    watering_streak_days: streak,
    total_plants: total,
  });

  it("is 0 with no plants / no stats (Stage 1)", () => {
    expect(vitalityScore(undefined, 0, true)).toBe(0);
    expect(vitalityScore(s(100, 30, 0), 200, true)).toBe(0);
    expect(stageFromVitality(0)).toBe(1);
  });

  it("keeps a day-0 perfectionist at Stage 1 (earned over time via tenure floor)", () => {
    expect(stageFromVitality(vitalityScore(s(100, 0), 0, true))).toBe(1);
  });

  it("defeats the bogus-100 trap: long-tenured low-maintenance collection stays low", () => {
    // every interval > 30d => consistency is a structural 100 but UNRELIABLE; lean on streak (0 here)
    const v = vitalityScore(s(100, 0), 200, false);
    expect(stageFromVitality(v)).toBe(1);
  });

  it("rewards sustained care over months (monotone in consistency, streak and tenure)", () => {
    const early = vitalityScore(s(70, 10), 10, true);
    const mid = vitalityScore(s(85, 30), 30, true);
    const mature = vitalityScore(s(95, 30), 120, true);
    expect(early).toBeLessThan(mid);
    expect(mid).toBeLessThan(mature);
    expect(stageFromVitality(early)).toBeGreaterThanOrEqual(2); // encouraging early
    expect(stageFromVitality(mature)).toBe(6); // prestige only after long excellent care
  });

  it("stageFromVitality maps thresholds correctly and clamps to 1..6", () => {
    expect(stageFromVitality(14)).toBe(1);
    expect(stageFromVitality(15)).toBe(2);
    expect(stageFromVitality(48)).toBe(4);
    expect(stageFromVitality(999)).toBe(6);
  });

  it("tenureFloorStage is conservative (never mints a prestige stage from tenure alone)", () => {
    expect(tenureFloorStage(0)).toBe(1);
    expect(tenureFloorStage(30)).toBe(2);
    expect(tenureFloorStage(400)).toBe(3); // capped at Blattgeist
  });
});

describe("growthFraction (monotonic growth bar)", () => {
  it("is full at stage 6 (no next threshold)", () => {
    expect(growthFraction(90, 6)).toBe(1);
  });
  it("fills within the current band from peak vitality", () => {
    expect(growthFraction(39, 3)).toBeCloseTo(0.5, 1); // stage-3 band [30,48): 39 ≈ halfway
  });
  it("clamps to 0 when peak is below the band (server/tenure-floored stage)", () => {
    expect(growthFraction(20, 3)).toBe(0); // peak 20 < band start 30
  });
});
