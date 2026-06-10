import { useI18n } from "../i18n";
import type { Plant } from "../types";
import { statusText, statusShort } from "../status";
import { PixelIcon } from "./PixelIcon";

/**
 * Number-first status band — the "widget" that answers the daily question in one glance
 * (research: glance-critical count as the LARGEST number on screen, one word, no prose;
 * the question gets an explicit answer even when it's "nobody": a calm green line instead
 * of silently disappearing). Rows keep the 1-tap Water action in the thumb zone; a row
 * that was just watered morphs to a ✓ and glides out (success stays silent + announce()).
 */
export function ThirstySection({
  plants,
  exiting,
  freshCollection,
  onWater,
  wateringId,
  onSelect,
}: {
  plants: Plant[];
  /** Just-watered plants (captured pre-water), shown briefly with a ✓ while gliding out. */
  exiting: Plant[];
  /** Every plant was added today: day-1 of the ritual. The band then sets the expectation
   *  ("tomorrow you'll see who's thirsty") instead of a trivially-true "all watered" —
   *  empty-state-as-onboarding (B3), self-removing from day 2 on. */
  freshCollection: boolean;
  onWater: (id: number) => void;
  wateringId: number | null;
  onSelect: (p: Plant) => void;
}) {
  const { t } = useI18n();

  if (plants.length === 0 && exiting.length === 0) {
    return freshCollection ? (
      <div className="pp-frame mb-6 flex items-center gap-2 px-4 py-3">
        <PixelIcon name="drop" size={14} className="shrink-0 text-pp-gold" />
        <span className="text-xs opacity-80">{t("thirsty.firstDay")}</span>
      </div>
    ) : (
      <div className="pp-frame mb-6 flex items-center gap-2 px-4 py-3">
        <PixelIcon name="check" size={14} className="shrink-0 text-pp-border" />
        <span className="text-xs opacity-80">{t("thirsty.allDone")}</span>
      </div>
    );
  }

  // Worst first; exiting rows keep their captured pre-water days_overdue, so the same
  // comparator puts them back in exactly the slot they occupied — no reshuffle mid-morph.
  const rows = [
    ...plants.map((p) => ({ plant: p, exit: false })),
    ...exiting.map((p) => ({ plant: p, exit: true })),
  ].sort(
    (a, b) =>
      b.plant.days_overdue - a.plant.days_overdue || a.plant.name.localeCompare(b.plant.name),
  );

  return (
    <section className="pp-frame mb-6 p-4">
      {/* The heading IS the glance signal: icon + big count + one word ("3 durstig"). */}
      <h2 className="mb-3 flex items-center gap-2">
        <PixelIcon name="drop" size={18} className="shrink-0 text-pp-gold" />
        <span className="text-2xl leading-none" data-testid="thirsty-count">
          {plants.length}
        </span>
        <span className="pp-heading text-xs">{t("thirsty.count")}</span>
      </h2>
      <div className="flex flex-col gap-3">
        {rows.map(({ plant: p, exit }) => (
          <div
            key={p.id}
            className={`flex items-center gap-3 rounded-lg border-2 border-pp-border bg-pp-thirsty p-2 ${
              exit ? "pp-row-exit" : ""
            }`}
          >
            {/* The image+text region opens the detail sheet (edit/delete) — thirsty plants no longer
                appear in the grid below, so this keeps them reachable. The Water button is a SEPARATE
                sibling (not nested), so there are no nested buttons and no stopPropagation needed. The
                48px image (h-12) keeps this tap target >=44px; the img is decorative (button is labelled). */}
            <button
              type="button"
              onClick={() => onSelect(p)}
              disabled={exit}
              className="flex min-w-0 flex-1 items-center gap-3 text-left"
              aria-label={`${p.name} — ${statusText(p, t)}`}
            >
              <img
                src={p.image_url ?? "/placeholder.png"}
                alt=""
                onError={(e) => {
                  const img = e.currentTarget;
                  if (!img.src.endsWith("/placeholder.png")) img.src = "/placeholder.png";
                }}
                className="pixelated h-12 w-12 shrink-0 rounded border border-pp-border object-cover"
              />
              <div className="min-w-0 flex-1">
                <div className="truncate text-xs font-bold uppercase">{p.name}</div>
                {/* Short fixed vocabulary ("2d über"), never a sentence — the long form lives in
                    the aria-label above. Slightly larger+bolder than before: it's glance data. */}
                <div className="mt-0.5 text-[11px] font-bold opacity-90">
                  {exit ? t("plant.watered") : statusShort(p, t)}
                </div>
              </div>
            </button>
            {exit ? (
              <span className="flex min-h-[44px] min-w-[64px] shrink-0 items-center justify-center">
                <PixelIcon name="check" size={16} className="text-pp-gold" />
              </span>
            ) : (
              <button
                type="button"
                className="pp-btn pp-btn--compact shrink-0"
                onClick={() => onWater(p.id)}
                disabled={wateringId === p.id}
              >
                <span className="inline-flex items-center gap-1.5">
                  <PixelIcon name="drop" size={11} />
                  {wateringId === p.id ? "…" : t("plant.water")}
                </span>
              </button>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
