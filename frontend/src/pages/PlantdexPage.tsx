import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useI18n } from "../i18n";
import type { Plant, Stats } from "../types";
import { PlantCard } from "../components/PlantCard";
import { PixelIcon } from "../components/PixelIcon";
import { ThirstySection } from "../components/ThirstySection";
import { PlantDetailModal } from "../components/PlantDetailModal";
import { ErrorState, InlineError, announce } from "../components/Feedback";
import { Spross } from "../components/Spross";
import { useAppShell } from "../appShell";
import {
  sprossMood,
  berlinToday,
  daysSince,
  vitalityScore,
  stageFromVitality,
  oldestPlantAgeDays,
  type Stage,
} from "../status";
import { loadSprossStore, saveSprossStore, ratchetSpross, evaluateProgress } from "../sprossState";

type Sort = "thirsty" | "name" | "recent";

export function PlantdexPage() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const {
    data: plants,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["plants"],
    queryFn: api.listPlants,
  });
  // Shares the ['stats'] cache with StatsPage; already invalidated on water/delete, so it stays
  // fresh. Only watering_consistency_pct is read (for the "blühend" upgrade); undefined until loaded.
  const { data: stats } = useQuery({ queryKey: ["stats"], queryFn: api.getStats });
  // The Add-Plant sheet + the central Spross tab live in the persistent AppShell now; this page
  // opens the sheet via openAdd() and pushes its live mood/stage/skin/vacation + reaction nonces
  // into the shared mirror so the tab sprite reflects the collection from anywhere in the app.
  const { openAdd, setSpross } = useAppShell();
  const [selected, setSelected] = useState<Plant | null>(null);
  const [wateringId, setWateringId] = useState<number | null>(null);
  // Just-watered plants (object captured pre-water): the band keeps them for ~1s as a quiet
  // ✓-morph that glides out, instead of the row vanishing on the refetch frame.
  const [exitingPlants, setExitingPlants] = useState<Plant[]>([]);
  const exitTimers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<Sort>("thirsty");
  const [pendingDelete, setPendingDelete] = useState<Set<number>>(new Set());
  const [actionError, setActionError] = useState<unknown>(null);
  const [waterNonce, setWaterNonce] = useState(0); // bumped on water → one-shot Spross joy-wiggle
  const [greeting, setGreeting] = useState(false); // transient ">3 days away" welcome-back
  // v2 evolution: ratcheted stage (only ever climbs) + one-shot level-up bloom. storeExisted is the
  // mount-time truth (read once, before any write) so the plants/stats query race can't fake a bloom.
  const [sprossStage, setSprossStage] = useState<Stage>(
    () => (loadSprossStore()?.stageMax ?? 2) as Stage,
  );
  const [bloomNonce, setBloomNonce] = useState(0);
  const [riseNonce, setRiseNonce] = useState(0); // one-shot "straighten up" when the last thirsty plant is watered
  const [sprossSkin, setSprossSkin] = useState<string | null>(
    () => loadSprossStore()?.activeSkin ?? null,
  );
  const [vacation, setVacation] = useState(() => loadSprossStore()?.vacation.on ?? false);
  const [storeExisted] = useState(() => loadSprossStore() !== null);
  const deleteTimers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());
  // Ids whose real DELETE already started (timer fired) — undo can no longer cancel these.
  const committingRef = useRef<Set<number>>(new Set());

  // Clear pending delete + row-exit timers on unmount so they can't fire after we leave.
  useEffect(() => {
    const timers = deleteTimers.current;
    const exits = exitTimers.current;
    return () => {
      timers.forEach((tid) => clearTimeout(tid));
      timers.clear();
      exits.forEach((tid) => clearTimeout(tid));
      exits.clear();
    };
  }, []);

  // Welcome-back: if the app was last opened >3 Berlin-days ago, greet once (Spross turns curious +
  // a fading caption), then decay to the real health mood. The write is idempotent (StrictMode-safe);
  // localStorage may throw in private mode, so it's guarded.
  useEffect(() => {
    try {
      const prev = localStorage.getItem("pp:lastSeen");
      const gap = prev ? daysSince(prev) : null;
      if (gap !== null && gap > 3) setGreeting(true);
      localStorage.setItem("pp:lastSeen", berlinToday());
    } catch {
      /* no localStorage → just skip the greeting */
    }
  }, []);
  useEffect(() => {
    if (!greeting) return;
    const id = setTimeout(() => setGreeting(false), 6000);
    return () => clearTimeout(id);
  }, [greeting]);

  // v2: evolve Spross from the user's own care history (vitality → ratcheted stage). Gated on BOTH
  // queries being loaded (else the race re-seeds wrong); re-runs on refetch are safe (max() is
  // idempotent, the bloom only fires on a genuine stage increase the user hasn't been shown yet).
  useEffect(() => {
    if (plants === undefined || stats === undefined) return;
    const oldestAge = oldestPlantAgeDays(plants);
    // If every plant's interval > 30d, the server's 30-day consistency window is empty and returns a
    // bogus 100 — treat consistency as unreliable so a low-maintenance collection can't mint a high stage.
    const consistencyReliable = plants.some((p) => p.interval_days <= 30);
    const live = vitalityScore(stats, oldestAge, consistencyReliable);
    const { store, bloom, needsServerSync } = ratchetSpross(
      loadSprossStore(),
      live,
      stageFromVitality(live),
      oldestAge,
      storeExisted,
      stats.vitality_stage_max,
      stats.peak_vitality,
    );
    // Detect milestones + unlock skins on the SAME store (this page has plants + the session
    // greeting; /spross only reads). One object, saved once — no clobbering.
    const next = evaluateProgress(
      store,
      {
        stageMax: store.stageMax,
        consistencyPct: stats.watering_consistency_pct,
        streakDays: stats.watering_streak_days,
        thirstyCount: stats.thirsty_count,
        totalPlants: stats.total_plants,
        petCount: store.petCount,
        greeting,
      },
      storeExisted,
      berlinToday(),
    );
    saveSprossStore(next);
    setSprossStage(next.stageMax as Stage);
    setSprossSkin(next.activeSkin);
    setVacation(next.vacation.on);
    if (bloom) setBloomNonce((n) => n + 1);
    // Persist the new high-water-mark to the server (durable across devices / storage loss). The
    // server applies max(), so it only ever climbs; best-effort (a failed request just re-syncs on
    // the next open). On success we patch the ['stats'] cache so we don't re-POST the same value.
    if (needsServerSync) {
      api
        .updateSprossProgress(store.stageMax, store.peakVitality)
        .then((res) =>
          qc.setQueryData<Stats | undefined>(["stats"], (old) =>
            old
              ? {
                  ...old,
                  vitality_stage_max: res.vitality_stage_max,
                  peak_vitality: res.peak_vitality,
                }
              : old,
          ),
        )
        .catch(() => {});
    }
  }, [plants, stats, storeExisted, greeting, qc]);

  const water = useMutation({
    mutationFn: (id: number) => api.waterPlant(id),
    onMutate: (id) => {
      setActionError(null);
      setWateringId(id);
    },
    onSettled: () => setWateringId(null),
    onSuccess: (_data, id) => {
      // Capture the pre-water row so the band can morph it to a ✓ and glide it out quietly
      // (the refetch below would otherwise pop it off on the next frame).
      const justWatered = (plants ?? []).find((p) => p.id === id);
      if (justWatered && justWatered.is_thirsty) {
        setExitingPlants((prev) => [...prev.filter((p) => p.id !== id), justWatered]);
        const tid = setTimeout(() => {
          exitTimers.current.delete(id);
          setExitingPlants((prev) => prev.filter((p) => p.id !== id));
        }, 1000);
        exitTimers.current.set(id, tid);
      }
      qc.invalidateQueries({ queryKey: ["plants"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      // The card silently drops out of the thirsty list; announce it for screen readers.
      announce(t("plant.watered"));
      // Spross's reaction (joy-wiggle vs. recovery "rise") is derived from the thirsty-count
      // transition below, so the two animations are mutually exclusive and never collide.
    },
    onError: (err) => setActionError(err),
  });

  function unmarkPending(id: number) {
    setPendingDelete((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }

  function handleUndo(id: number) {
    // Timer already fired and the DELETE is in flight — too late to undo; don't falsely announce
    // "restored" while the plant is actually being deleted (review finding #6).
    if (committingRef.current.has(id)) return;
    const tid = deleteTimers.current.get(id);
    if (tid) clearTimeout(tid);
    deleteTimers.current.delete(id);
    unmarkPending(id);
    announce(t("plant.restored"));
  }

  // Soft-delete with undo: keep the plant in `pendingDelete` (survives refetch) and run the real
  // delete after a 5s grace window. While pending, the plant renders in place as an undo card
  // (no floating toast); undo cancels the timer and un-hides. Timers are also cleared on unmount.
  function handleDelete(plant: Plant) {
    setActionError(null);
    setPendingDelete((prev) => new Set(prev).add(plant.id));
    announce(t("plant.deleted")); // screen-reader cue; sighted users see the undo card appear
    const timer = setTimeout(() => {
      deleteTimers.current.delete(plant.id);
      committingRef.current.add(plant.id); // delete is now in flight — undo can't cancel it anymore
      api
        .deletePlant(plant.id)
        .then(() => {
          qc.invalidateQueries({ queryKey: ["plants"] });
          qc.invalidateQueries({ queryKey: ["stats"] });
        })
        .catch((err) => setActionError(err))
        .finally(() => {
          committingRef.current.delete(plant.id);
          unmarkPending(plant.id);
        });
    }, 5000);
    deleteTimers.current.set(plant.id, timer);
  }

  // Plants not pending deletion — drives the thirsty section and the visible counts.
  const livePlants = useMemo(
    () => (plants ?? []).filter((p) => !pendingDelete.has(p.id)),
    [plants, pendingDelete],
  );
  // Exclude rows mid ✓-glide-out: between water-success and the refetch the plant is still
  // is_thirsty in the cache and would render twice (live + exiting).
  const thirsty = livePlants.filter(
    (p) => p.is_thirsty && !exitingPlants.some((x) => x.id === p.id),
  );

  // Spross's mood = collective health, from live plants (NOT stats.thirsty_count, so a plant in its
  // 5s undo window can't skew it) + the consistency_pct from the shared ['stats'] cache.
  const longestOverdueDays = useMemo(
    () => livePlants.reduce((m, p) => Math.max(m, p.days_overdue), 0),
    [livePlants],
  );
  let mood = sprossMood({
    thirstyCount: thirsty.length,
    longestOverdueDays,
    consistencyPct: stats?.watering_consistency_pct,
    justReturned: greeting,
  });
  if (vacation && (mood === "durstig" || mood === "welkend")) mood = "wohl"; // Urlaub: Distress dämpfen

  // Spross's reaction to a watering, derived from the thirsty-count transition so joy-wiggle and the
  // recovery "rise" are mutually exclusive (never two transforms on one sprite). Rise wins when the
  // last thirsty plant is satisfied (relief, as fast as the decline).
  const prevThirstyRef = useRef(thirsty.length);
  useEffect(() => {
    const now = thirsty.length;
    const prev = prevThirstyRef.current;
    prevThirstyRef.current = now;
    if (vacation) return; // no reaction animations while resting
    if (prev > 0 && now === 0) setRiseNonce((n) => n + 1);
    else if (now < prev) setWaterNonce((n) => n + 1);
  }, [thirsty.length, vacation]);

  // Push the live mood-mirror into the AppShell so the central Spross TAB reflects the collection
  // (and replays the same water/rise/bloom reactions the old band did). MUST be its own effect: the
  // render-derived `mood` (above) and the nonces are NOT in the ratchet effect's deps, so folding
  // this in would push a stale mood. Functional setSpross keeps the setter stable out of the deps.
  useEffect(() => {
    setSpross((p) => ({
      ...p,
      mood,
      stage: sprossStage,
      skin: sprossSkin,
      vacation,
      reactNonce: waterNonce,
      riseNonce,
      bloomNonce,
    }));
  }, [mood, sprossStage, sprossSkin, vacation, waterNonce, riseNonce, bloomNonce, setSpross]);

  // The render list keeps plants that are pending deletion, so each shows in place as an undo
  // card at its original spot. They bypass search/filter so the 5s undo window stays reachable.
  const visible = useMemo(() => {
    let list = plants ?? [];
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (p) =>
          pendingDelete.has(p.id) ||
          p.name.toLowerCase().includes(q) ||
          (p.location_room ?? "").toLowerCase().includes(q),
      );
    }
    const sorted = [...list];
    if (sort === "name") sorted.sort((a, b) => a.name.localeCompare(b.name));
    else if (sort === "recent")
      sorted.sort((a, b) => b.last_watered_at.localeCompare(a.last_watered_at));
    else sorted.sort((a, b) => b.days_overdue - a.days_overdue || a.name.localeCompare(b.name));
    return sorted;
  }, [plants, pendingDelete, search, sort]);

  const searching = search.trim().length > 0;
  // Thirsty plants surface once, in the section above; the grid shows "the rest". While searching,
  // every match belongs in the results (thirsty included). Pending-delete cards always stay in the
  // grid so their 5s undo window remains reachable. Mid ✓-glide rows (exiting) are still owned by
  // the band — without this filter the just-watered plant would appear twice until the refetch
  // (band exit row + grid card), since `thirsty` already excludes it (Codex P1).
  const gridPlants = useMemo(() => {
    if (searching) return visible;
    const thirstyIds = new Set(thirsty.map((p) => p.id));
    const exitingIds = new Set(exitingPlants.map((p) => p.id));
    return visible.filter(
      (p) => pendingDelete.has(p.id) || (!thirstyIds.has(p.id) && !exitingIds.has(p.id)),
    );
  }, [visible, searching, thirsty, exitingPlants, pendingDelete]);

  return (
    <div className="mx-auto max-w-3xl p-4">
      {/* Header is now just the wordmark — the old icon-nav (Statistik/Einstellungen/Pflanze +) and
          the Spross mood-band moved into the persistent bottom TabBar (Instagram-style navigation). */}
      <header className="mb-4">
        <h1 tabIndex={-1}>
          <img src="/wordmark.png" alt="PlantPal" width={735} height={160} className="h-9 w-auto" />
        </h1>
      </header>

      {isLoading ? (
        <p className="pp-heading text-center text-sm">{t("app.loading")}</p>
      ) : isError ? (
        <ErrorState onRetry={() => qc.invalidateQueries({ queryKey: ["plants"] })} />
      ) : (plants ?? []).length === 0 ? (
        <div className="pp-frame p-8 text-center text-sm">
          <Spross mood="neugierig" stage={sprossStage} size={96} className="mb-4" />
          <p className="pp-heading mb-2 text-sm">{t("empty.title")}</p>
          <p className="mb-4 opacity-70">{t("empty.hint")}</p>
          <button type="button" className="pp-btn" onClick={openAdd}>
            {t("empty.cta")}
          </button>
        </div>
      ) : (
        <>
          <InlineError error={actionError} className="mb-3 text-center pp-halo" />

          {/* The Spross mood-band moved into the persistent TabBar's central tab (the live mirror is
              pushed from the sync effect above). The band below answers the daily question with a
              number-first header — and explicitly answers "nobody" with a calm all-watered line
              instead of vanishing. While searching, the grid carries every match instead. */}
          {!searching && (
            <ThirstySection
              plants={thirsty}
              exiting={exitingPlants}
              freshCollection={
                livePlants.length > 0 &&
                livePlants.every((p) => (daysSince(p.created_at) ?? 1) === 0)
              }
              onWater={water.mutate}
              wateringId={wateringId}
              onSelect={setSelected}
            />
          )}

          {/* Catalog zone. Hidden entirely when there's nothing left to show and we're not searching
              (no orphan heading, no false "no results"); the "no results" box appears only on a search. */}
          {(gridPlants.length > 0 || searching) && (
            <>
              <h2 className="pp-heading mt-8 mb-3 text-sm">{t("nav.plantdex")}</h2>

              {/* Search + sort are library tools, not daily tools: they live with the catalog
                  (under its heading) and only appear once the collection is big enough to need
                  them (≥6) — below that they'd be louder than the content they filter. */}
              {(livePlants.length >= 6 || searching) && (
                <div className="mb-3 flex items-center gap-2">
                  <input
                    className="pp-input min-w-0 flex-1"
                    placeholder={t("list.search")}
                    aria-label={t("list.search")}
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                  {/* width:auto inline — .pp-input sets width:100%, which beats a `w-auto` class in
                      the cascade and would collapse the search field. Inline style wins, keeping the
                      select at content width so the search field can take the rest of the row. */}
                  <select
                    className="pp-input shrink-0"
                    style={{ width: "auto" }}
                    value={sort}
                    onChange={(e) => setSort(e.target.value as Sort)}
                  >
                    <option value="thirsty">{t("list.sort.thirsty")}</option>
                    <option value="name">{t("list.sort.name")}</option>
                    <option value="recent">{t("list.sort.recent")}</option>
                  </select>
                </div>
              )}

              {gridPlants.length === 0 ? (
                searching ? (
                  <div className="pp-frame p-6 text-center text-sm">
                    <p className="mb-3 opacity-80">{t("list.noResults")}</p>
                    <button type="button" className="pp-btn" onClick={() => setSearch("")}>
                      {t("list.resetFilters")}
                    </button>
                  </div>
                ) : null
              ) : (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {gridPlants.map((p) =>
                    pendingDelete.has(p.id) ? (
                      <UndoCard key={p.id} name={p.name} onUndo={() => handleUndo(p.id)} />
                    ) : (
                      <PlantCard key={p.id} plant={p} onClick={() => setSelected(p)} />
                    ),
                  )}
                </div>
              )}
            </>
          )}
        </>
      )}

      {selected && (
        <PlantDetailModal
          plant={selected}
          onClose={() => setSelected(null)}
          onDelete={handleDelete}
        />
      )}
    </div>
  );
}

/** In-place stand-in for a plant card during its 5-second undo window (replaces the old floating
 *  undo toast). The deletion itself is announced via the global live region, so this card is not
 *  a live region — just a labelled undo affordance sitting where the card used to be. */
function UndoCard({ name, onUndo }: { name: string; onUndo: () => void }) {
  const { t } = useI18n();
  return (
    <div className="flex items-center justify-between gap-2 rounded-lg border-2 border-dashed border-pp-border bg-pp-panel-2 p-2 text-xs">
      <span className="min-w-0 flex-1 truncate opacity-80">
        <PixelIcon name="trash" size={11} className="mr-1 inline" />
        {t("plant.deletedName", { name })}
      </span>
      <button
        type="button"
        className="pp-btn shrink-0"
        onClick={onUndo}
        aria-label={`${t("plant.undo")}: ${name}`}
        ref={(el) => {
          // After a delete the trigger card is gone and focus falls to <body>; pull it onto this
          // undo button so keyboard/SR users land on the recovery action — but never steal focus
          // if they've already tabbed elsewhere (UX/A11Y).
          if (el && document.activeElement === document.body) el.focus();
        }}
      >
        {t("plant.undo")}
      </button>
    </div>
  );
}
