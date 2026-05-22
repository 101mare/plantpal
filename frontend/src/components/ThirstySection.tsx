import type { Plant } from "../types";

export function ThirstySection({
  plants,
  onWater,
  wateringId,
}: {
  plants: Plant[];
  onWater: (id: number) => void;
  wateringId: number | null;
}) {
  if (plants.length === 0) {
    return (
      <div className="pp-frame mb-6 p-4">
        <h2 className="pp-heading mb-2 text-sm">Thirsty Plants!</h2>
        <p className="text-xs opacity-80">🌿 Alles gewässert!</p>
      </div>
    );
  }
  return (
    <div className="pp-frame mb-6 p-4">
      <h2 className="pp-heading mb-3 text-sm">Thirsty Plants!</h2>
      <div className="flex flex-col gap-3">
        {plants.map((p) => (
          <div
            key={p.id}
            className="flex items-center gap-3 rounded-lg border-2 border-pp-border bg-pp-thirsty p-2"
          >
            <img
              src={p.image_url ?? "/placeholder.png"}
              alt={p.name}
              className="pixelated h-12 w-12 rounded border border-pp-border object-cover"
            />
            <div className="flex-1">
              <div className="text-xs font-bold uppercase">{p.name}</div>
              <div className="text-[10px] opacity-80">Water: {p.interval_days} Days</div>
            </div>
            <button className="pp-btn" onClick={() => onWater(p.id)} disabled={wateringId === p.id}>
              💧 {wateringId === p.id ? "…" : "Water"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
