import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useI18n } from "../i18n";
import { useAppShell } from "../appShell";
import { ErrorState } from "../components/Feedback";
import { Spross } from "../components/Spross";
import { growthFraction, berlinToday, STAGE_THRESHOLDS, type Stage } from "../status";
import {
  loadSprossStore,
  saveSprossStore,
  defaultSprossStore,
  evaluateProgress,
  MILESTONES,
  SKINS,
  type SprossStore,
} from "../sprossState";

/**
 * Companion home. The accessible spine for all progression: the mascot stays decorative
 * (aria-hidden) and every gain is legible as TEXT. Shows ONLY ratcheted/peak values + static
 * thresholds — never live consistency/streak (which drop after a lapse and would read as a downgrade).
 * Milestones are DETECTED on the Plantdex (which has ['plants'] + the session greeting); here we only
 * read them — except tap-to-pet, which can cross the 100-pet milestone right here.
 */
export function SprossPage() {
  const { t } = useI18n();
  const { setSpross } = useAppShell();
  const qc = useQueryClient();
  const {
    data: stats,
    isLoading,
    isError,
  } = useQuery({ queryKey: ["stats"], queryFn: api.getStats });
  const [store, setStore] = useState<SprossStore>(() => loadSprossStore() ?? defaultSprossStore());
  const [storeExisted] = useState(() => loadSprossStore() !== null);
  const [petNonce, setPetNonce] = useState(0);

  const stageMax = Math.max(store.stageMax, stats?.vitality_stage_max ?? 1) as Stage;
  const peak = Math.max(store.peakVitality, stats?.peak_vitality ?? 0);
  const vacation = store.vacation.on;
  // The companion home is the IDENTITY view: a calm, content hero — NOT live-thirst-driven (that
  // belongs on the daily Plantdex band and would read as a downgrade here). Vacation just rests it.
  const mood = "wohl" as const;

  function pet() {
    setPetNonce((n) => n + 1);
    const petCount = store.petCount + 1;
    const next = evaluateProgress(
      { ...store, petCount },
      {
        stageMax,
        consistencyPct: stats?.watering_consistency_pct ?? 0,
        streakDays: stats?.watering_streak_days ?? 0,
        thirstyCount: stats?.thirsty_count ?? 0,
        totalPlants: stats?.total_plants ?? 0,
        petCount,
        greeting: false,
      },
      storeExisted, // mount-time truth → a fresh server-restore can't fabricate today-dated trophies
      berlinToday(),
    );
    saveSprossStore(next);
    setStore(next);
  }

  function pickSkin(id: string | null) {
    const next = { ...store, activeSkin: id };
    saveSprossStore(next);
    setStore(next);
    setSpross((p) => ({ ...p, skin: id })); // mirror to the TabBar's central sprite immediately
  }

  const isBrandNew = (stats?.total_plants ?? 0) === 0 && stageMax === 1;
  const nextThreshold = stageMax < 6 ? STAGE_THRESHOLDS[stageMax] : null;
  const stageName = t(`spross.stage.${stageMax}`);

  return (
    <div className="mx-auto max-w-md p-4">
      {/* No back button — the persistent TabBar is the sole primary navigation (Instagram-style). */}
      <header className="mb-6">
        <h1 className="pp-heading text-lg" tabIndex={-1}>
          {t("spross.title")}
        </h1>
      </header>

      {isLoading ? (
        <p className="pp-heading text-center text-sm">{t("app.loading")}</p>
      ) : isError ? (
        <ErrorState onRetry={() => qc.invalidateQueries({ queryKey: ["stats"] })} />
      ) : (
        <>
          <div className="pp-frame mb-4 flex flex-col items-center gap-3 p-5 text-center">
            <Spross
              mood={mood}
              stage={stageMax}
              skin={vacation ? undefined : store.activeSkin}
              rest={vacation}
              reactNonce={petNonce}
              onPet={pet}
              ariaLabel={t("spross.pet")}
              className="h-36 w-36"
            />
            {/* One-time nudge that the sprite is interactive; self-removes after the first pet. */}
            {!isBrandNew && store.petCount === 0 && (
              <p className="text-[11px] uppercase opacity-50" aria-hidden="true">
                {t("spross.tap")}
              </p>
            )}
            {isBrandNew ? (
              <p className="text-sm opacity-80">{t("spross.empty")}</p>
            ) : (
              <>
                <p className="pp-heading text-sm">{stageName}</p>
                {/* Tight progress group: stageName | this group | vacation read as 3 hero units. */}
                <div className="flex w-full flex-col items-center gap-1">
                  <div
                    className="h-3 w-full overflow-hidden rounded-full border border-pp-border bg-pp-panel-2"
                    aria-hidden="true"
                  >
                    <div
                      className="h-full bg-pp-gold"
                      style={{ width: `${Math.round(growthFraction(peak, stageMax) * 100)}%` }}
                    />
                  </div>
                  {/* The bar is aria-hidden, so surface the value that drives it as text. */}
                  <p className="text-[11px] uppercase opacity-80">
                    {t("spross.vitality", { n: peak })}
                  </p>
                  <p className="text-[11px] uppercase opacity-60">
                    {nextThreshold !== null
                      ? t("spross.nextAt", { n: nextThreshold })
                      : t("spross.maxStage")}
                  </p>
                </div>
                {vacation && <p className="text-xs text-pp-gold">{t("spross.vacationActive")}</p>}
              </>
            )}
          </div>

          {/* Vacation toggle lives beside the companion it visibly rests (relocated from Settings —
              identical read/write, no logic change). Always rendered to preserve feature parity. */}
          <section className="pp-frame mb-4 p-4 text-xs">
            <label className="flex min-h-[44px] items-center justify-between gap-3">
              {t("settings.vacation")}
              <input
                type="checkbox"
                className="h-7 w-7"
                checked={vacation}
                onChange={(e) => {
                  const on = e.target.checked;
                  const next = {
                    ...store,
                    vacation: { on, since: on ? berlinToday() : store.vacation.since },
                  };
                  saveSprossStore(next);
                  setStore(next);
                  // Mirror into the central TabBar sprite so the dormant look shows immediately.
                  setSpross((p) => ({ ...p, vacation: on }));
                }}
              />
            </label>
            <p className="mt-2 text-[11px] opacity-70">{t("settings.vacationHint")}</p>
          </section>

          {store.skins.length > 0 && (
            <section className="pp-frame mb-4 p-4">
              <h2 className="pp-heading mb-3 text-sm">{t("spross.skins")}</h2>
              <div className="flex flex-wrap gap-2">
                <SkinButton
                  active={store.activeSkin === null}
                  label={t("spross.skinNone")}
                  onClick={() => pickSkin(null)}
                />
                {SKINS.filter((s) => store.skins.includes(s.id)).map((s) => (
                  <SkinButton
                    key={s.id}
                    active={store.activeSkin === s.id}
                    label={t(`spross.skin.${s.id}`)}
                    onClick={() => pickSkin(s.id)}
                  />
                ))}
              </div>
            </section>
          )}

          {/* No Day-1 wall: the trophy case only appears once at least one milestone is earned. */}
          {Object.keys(store.milestones).length > 0 && (
            <section className="pp-frame p-4">
              <h2 className="pp-heading mb-3 text-sm">{t("spross.trophies")}</h2>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {MILESTONES.map((m) => {
                  const unlocked = m.id in store.milestones;
                  const date = store.milestones[m.id];
                  return (
                    <div
                      key={m.id}
                      className={`flex min-w-0 flex-col items-center gap-1 rounded-lg border-2 p-2 text-center text-[11px] ${
                        unlocked
                          ? "border-pp-border bg-pp-panel-2"
                          : "border-dashed border-pp-border opacity-50"
                      }`}
                    >
                      <span className="text-lg" aria-hidden="true">
                        {unlocked ? "🏆" : "🔒"}
                      </span>
                      {/* Always name the goal (grey/dashed when locked) so it reads as a target to pull
                          toward, not a wall of mystery boxes. Long German names wrap (min-w-0);
                          sr-only keeps the "locked" state for VoiceOver. */}
                      <span className="hyphens-auto break-words leading-tight">
                        {t(`spross.ms.${m.id}`)}
                      </span>
                      {unlocked ? (
                        date && <span className="opacity-80">{date}</span>
                      ) : (
                        <span className="sr-only">{t("spross.locked")}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function SkinButton({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`pp-btn ${active ? "ring-2 ring-pp-gold ring-offset-2 ring-offset-pp-panel" : "opacity-70"}`}
    >
      {label}
    </button>
  );
}
