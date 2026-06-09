import { useI18n } from "../i18n";
import type { Plant } from "../types";
import { plantStatus, statusText, STATUS_DOT } from "../status";

export function PlantCard({ plant, onClick }: { plant: Plant; onClick: () => void }) {
  const { t } = useI18n();
  const level = plantStatus(plant);
  const statusLabel = statusText(plant, t);

  return (
    <button
      type="button"
      onClick={onClick}
      className="relative flex items-center gap-3 rounded-lg border-2 border-pp-border bg-pp-card p-2 text-left text-pp-card-ink"
      aria-label={`${plant.name} — ${statusLabel}`}
    >
      <img
        src={plant.image_url ?? "/placeholder.png"}
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
        {/* A11Y: status as visible TEXT (not colour alone) for the non-ok states (colour-blind users).
            Sits directly under the name — the only daily-relevant secondary info. The set-and-forget
            interval moved to the detail sheet (Progressive Disclosure). */}
        {level !== "ok" && <div className="mt-1 truncate text-[11px] font-bold">{statusLabel}</div>}
        {plant.location_room && (
          <div className="mt-0.5 truncate text-[10px] opacity-70">
            <span aria-hidden="true">📍</span> {plant.location_room}
          </div>
        )}
      </div>
      {level === "ok" ? (
        <span
          className={`absolute bottom-1 right-1 h-3 w-3 rounded-full ${STATUS_DOT.ok}`}
          aria-hidden="true"
        />
      ) : (
        <span
          className={`absolute bottom-1 right-1 flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[9px] font-bold text-white ${STATUS_DOT[level]}`}
          aria-hidden="true"
        >
          {plant.days_overdue >= 1 && <span>{plant.days_overdue}d</span>}
          💧
        </span>
      )}
    </button>
  );
}
