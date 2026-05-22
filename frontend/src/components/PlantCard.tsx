import type { Plant } from "../types";

export function PlantCard({ plant, onClick }: { plant: Plant; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="relative flex items-center gap-3 rounded-lg border-2 border-pp-border bg-pp-card p-2 text-left text-pp-card-ink"
    >
      <img
        src={plant.image_url ?? "/placeholder.png"}
        alt={plant.name}
        className="pixelated h-14 w-14 flex-shrink-0 rounded border border-pp-border bg-pp-panel-2 object-cover"
      />
      <div className="min-w-0 flex-1">
        <div className="truncate text-xs font-bold uppercase">{plant.name}</div>
        <div className="mt-1 text-[10px] opacity-80">Water: {plant.interval_days} Days</div>
      </div>
      {plant.is_thirsty && (
        <span
          title="Braucht Wasser"
          className="absolute bottom-1 right-1 text-base"
          aria-label="thirsty"
        >
          💧
        </span>
      )}
    </button>
  );
}
