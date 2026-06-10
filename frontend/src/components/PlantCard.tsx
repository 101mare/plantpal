import { assetUrl } from "../api";
import { useI18n } from "../i18n";
import type { Plant } from "../types";
import { plantStatus, statusText, statusShort, STATUS_DOT } from "../status";
import { PixelIcon } from "./PixelIcon";

export function PlantCard({ plant, onClick }: { plant: Plant; onClick: () => void }) {
  const { t } = useI18n();
  const level = plantStatus(plant);

  return (
    <button
      type="button"
      onClick={onClick}
      className="relative flex items-center gap-3 rounded-lg border-2 border-pp-border bg-pp-card p-2 text-left text-pp-card-ink"
      aria-label={`${plant.name} — ${statusText(plant, t)}`}
    >
      <img
        src={plant.image_url ? assetUrl(plant.image_url) : "/placeholder.png"}
        alt=""
        loading="lazy"
        decoding="async"
        onError={(e) => {
          const img = e.currentTarget;
          if (!img.src.endsWith("/placeholder.png")) img.src = "/placeholder.png"; // re-trigger-safe
        }}
        className="pixelated h-14 w-14 flex-shrink-0 rounded border border-pp-border bg-pp-panel-2 object-cover"
      />
      <div className="min-w-0 flex-1">
        <div className="truncate text-xs font-bold uppercase">{plant.name}</div>
        {/* A11Y: status as visible TEXT (not colour alone) for the non-ok states (colour-blind
            users) — short fixed vocabulary ("2d über"), the sentence form lives in the aria-label.
            The room moved to the detail sheet: the card carries only the daily-relevant signal
            (photo + name + water status), per the glanceability research. */}
        {level !== "ok" && (
          <div className="mt-1 truncate text-[11px] font-bold">{statusShort(plant, t)}</div>
        )}
      </div>
      {level === "ok" ? (
        <span
          className={`absolute bottom-1 right-1 h-3 w-3 rounded-full ${STATUS_DOT.ok}`}
          aria-hidden="true"
        />
      ) : (
        <span
          className={`absolute bottom-1 right-1 flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[9px] font-bold text-white ${STATUS_DOT[level]}`}
          aria-hidden="true"
        >
          {plant.days_overdue >= 1 && <span>{plant.days_overdue}d</span>}
          <PixelIcon name="drop" size={9} />
        </span>
      )}
    </button>
  );
}
