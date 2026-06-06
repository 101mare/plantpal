import { useI18n } from "../i18n";
import type { Plant } from "../types";
import { statusText } from "../status";

export function ThirstySection({
  plants,
  onWater,
  wateringId,
}: {
  plants: Plant[];
  onWater: (id: number) => void;
  wateringId: number | null;
}) {
  const { t } = useI18n();
  if (plants.length === 0) {
    // All watered: a slim one-line note instead of a full framed section, to save vertical space.
    return <p className="mb-6 py-1 text-center text-xs opacity-70">{t("thirsty.allWatered")}</p>;
  }
  return (
    <div className="pp-frame mb-6 p-4">
      <h2 className="pp-heading mb-3 text-sm">{t("thirsty.title")}</h2>
      <div className="flex flex-col gap-3">
        {plants.map((p) => (
          <div
            key={p.id}
            className="flex items-center gap-3 rounded-lg border-2 border-pp-border bg-pp-thirsty p-2"
          >
            <img
              src={p.image_url ?? "/placeholder.png"}
              alt={p.name}
              onError={(e) => {
                const img = e.currentTarget;
                if (!img.src.endsWith("/placeholder.png")) img.src = "/placeholder.png";
              }}
              className="pixelated h-12 w-12 rounded border border-pp-border object-cover"
            />
            <div className="min-w-0 flex-1">
              <div className="truncate text-xs font-bold uppercase">{p.name}</div>
              <div className="text-[10px] opacity-80">{statusText(p, t)}</div>
            </div>
            <button
              type="button"
              className="pp-btn"
              onClick={() => onWater(p.id)}
              disabled={wateringId === p.id}
            >
              💧 {wateringId === p.id ? "…" : t("plant.water")}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
