import { describe, expect, it } from "vitest";
import { ratchetSpross, defaultSprossStore, evaluateProgress } from "./sprossState";

describe("ratchetSpross (monotonic identity + bloom gating)", () => {
  const store = (over: Partial<ReturnType<typeof defaultSprossStore>> = {}) => ({
    ...defaultSprossStore(),
    ...over,
  });

  it("INVARIANT: stageMax never decreases, whatever the live stage says", () => {
    const prev = store({ stageMax: 5, stageSeen: 5, peakVitality: 70 });
    // live computed all the way down to Stage 1 (e.g. consistency decayed after a lapse)
    const { store: next, bloom } = ratchetSpross(prev, 5, 1, 200, true);
    expect(next.stageMax).toBe(5); // identity holds — no felt downgrade
    expect(next.peakVitality).toBe(70);
    expect(bloom).toBe(false);
  });

  it("blooms once on a genuine increase, then never re-blooms for the same stage", () => {
    const prev = store({ stageMax: 2, stageSeen: 2, peakVitality: 20 });
    const a = ratchetSpross(prev, 40, 3, 60, true);
    expect(a.store.stageMax).toBe(3);
    expect(a.bloom).toBe(true);
    // a refetch run with the just-written store must not re-bloom
    const b = ratchetSpross(a.store, 40, 3, 60, true);
    expect(b.bloom).toBe(false);
  });

  it("NEVER blooms on first hydrate (storeExisted=false) — no fake celebration / no race bloom", () => {
    const { store: next, bloom } = ratchetSpross(null, 70, 5, 90, false);
    expect(bloom).toBe(false);
    expect(next.stageMax).toBe(5);
    expect(next.stageSeen).toBe(5); // marked seen silently so a later genuine level-up still blooms
  });

  it("re-seed floor stops a long-tended account reappearing as a Keimling after storage loss", () => {
    // store lost (null), live vitality crashed to Stage 1 (streak=0 post-lapse), but tenure is 200d
    const { store: next } = ratchetSpross(null, 8, 1, 200, false);
    expect(next.stageMax).toBe(3); // tenure floor (Blattgeist), not Keimling
  });

  it("does not apply the tenure floor once a store exists (honest live growth from there)", () => {
    const prev = store({ stageMax: 1, stageSeen: 1 });
    const { store: next } = ratchetSpross(prev, 8, 1, 200, true);
    expect(next.stageMax).toBe(1);
  });

  it("server high-water-mark restores the real stage after storage loss — no downgrade, no bloom", () => {
    // local store gone (null), live vitality crashed to Stage 1, but the SERVER says Stage 5
    const { store: next, bloom, needsServerSync } = ratchetSpross(null, 8, 1, 5, false, 5, 60);
    expect(next.stageMax).toBe(5); // durable server floor wins → never a felt downgrade
    expect(next.peakVitality).toBe(60);
    expect(bloom).toBe(false); // fresh device: show the stage, don't fake-celebrate it
    expect(needsServerSync).toBe(false); // already in sync with the server
  });

  it("flags needsServerSync only when local/live climbs past the server", () => {
    const prev = store({ stageMax: 2, stageSeen: 2, peakVitality: 20 });
    const up = ratchetSpross(prev, 50, 4, 60, true, 2, 20); // live Stage 4 > server 2
    expect(up.store.stageMax).toBe(4);
    expect(up.needsServerSync).toBe(true);
    const inSync = ratchetSpross(up.store, 50, 4, 60, true, 4, 50); // server caught up
    expect(inSync.needsServerSync).toBe(false);
  });
});

describe("evaluateProgress (milestones + skin unlocks)", () => {
  const ctx = {
    stageMax: 1,
    consistencyPct: 0,
    streakDays: 0,
    thirstyCount: 0,
    totalPlants: 0,
    petCount: 0,
    greeting: false,
  };

  it("dates a genuinely-reached milestone with today + unlocks its skin (storeExisted)", () => {
    const r = evaluateProgress(defaultSprossStore(), { ...ctx, stageMax: 3 }, true, "2026-06-09");
    expect(r.milestones.stufe_3).toBe("2026-06-09");
    expect(r.skins).toContain("tau"); // stufe_3 unlocks it
  });

  it("seeds a server-restored milestone with an EMPTY date — no fabricated 'today'", () => {
    const r = evaluateProgress(defaultSprossStore(), { ...ctx, stageMax: 5 }, false, "2026-06-09");
    expect(r.milestones.stufe_3).toBe("");
    expect(r.milestones.stufe_5).toBe("");
    expect(r.skins).toEqual(expect.arrayContaining(["tau", "amethyst"]));
  });

  it("is append-only: keeps a milestone even after its condition no longer holds", () => {
    const prev = { ...defaultSprossStore(), milestones: { streak_7: "2026-01-01" } };
    const r = evaluateProgress(prev, { ...ctx, streakDays: 0 }, true, "2026-06-09");
    expect(r.milestones.streak_7).toBe("2026-01-01");
  });

  it("unlocks koralle at 100 pets", () => {
    const r = evaluateProgress(defaultSprossStore(), { ...ctx, petCount: 100 }, true, "2026-06-09");
    expect(r.milestones.pflege_100).toBe("2026-06-09");
    expect(r.skins).toContain("koralle");
  });
});
