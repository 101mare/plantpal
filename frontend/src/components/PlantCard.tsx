import { useI18n } from "../i18n";
import type { Plant } from "../types";
import { plantStatus, STATUS_DOT } from "../status";

export function PlantCard({ plant, onClick }: { plant: Plant; onClick: () => void }) {
  const { t } = useI18n();
  const level = plantStatus(plant);
  const statusLabel =
    level === "due" || level === "overdue"
      ? t("plant.overdue", { n: plant.days_overdue })
      : t(level === "soon" ? "status.soon" : "status.ok");

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
        onError={(e) => {
          (e.target as HTMLImageElement).src = "/placeholder.png";
        }}
        className="pixelated h-14 w-14 flex-shrink-0 rounded border border-pp-border bg-pp-panel-2 object-cover"
      />
      <div className="min-w-0 flex-1">
        <div className="truncate text-xs font-bold uppercase">{plant.name}</div>
        <div className="mt-1 text-[10px]">{t("plant.everyDays", { n: plant.interval_days })}</div>
        {plant.location_room && (
          <div className="truncate text-[10px]">
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
          {(level === "due" || level === "overdue") && <span>{plant.days_overdue}d</span>}
          💧
        </span>
      )}
    </button>
  );
}
