import { useI18n } from "../i18n";
import type { Plant } from "../types";
import { statusText } from "../status";

export function ThirstySection({
  plants,
  onWater,
  wateringId,
  onSelect,
}: {
  plants: Plant[];
  onWater: (id: number) => void;
  wateringId: number | null;
  onSelect: (p: Plant) => void;
}) {
  const { t } = useI18n();
  // All watered: render nothing — the Spross mood band above is the single "all good" signal now
  // (it blooms when nothing is thirsty), so a redundant "Alles gewässert!" line was dropped.
  if (plants.length === 0) return null;
  return (
    <div className="pp-frame mb-6 p-4">
      <h2 className="pp-heading mb-3 text-sm">{t("thirsty.title")}</h2>
      <div className="flex flex-col gap-3">
        {plants.map((p) => (
          <div
            key={p.id}
            className="flex items-center gap-3 rounded-lg border-2 border-pp-border bg-pp-thirsty p-2"
          >
            {/* The image+text region opens the detail sheet (edit/delete) — thirsty plants no longer
                appear in the grid below, so this keeps them reachable. The Water button is a SEPARATE
                sibling (not nested), so there are no nested buttons and no stopPropagation needed. The
                48px image (h-12) keeps this tap target >=44px; the img is decorative (button is labelled). */}
            <button
              type="button"
              onClick={() => onSelect(p)}
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
                <div className="text-[10px] opacity-80">{statusText(p, t)}</div>
              </div>
            </button>
            <button
              type="button"
              className="pp-btn shrink-0"
              onClick={() => onWater(p.id)}
              disabled={wateringId === p.id}
            >
              <span aria-hidden="true">💧</span> {wateringId === p.id ? "…" : t("plant.water")}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
