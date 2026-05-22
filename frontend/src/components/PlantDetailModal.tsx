import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError } from "../api";
import type { Plant } from "../types";
import { Backdrop } from "./AddPlantModal";

export function PlantDetailModal({ plant, onClose }: { plant: Plant; onClose: () => void }) {
  const qc = useQueryClient();

  const del = useMutation({
    mutationFn: () => api.deletePlant(plant.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plants"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      toast.success("Pflanze entfernt");
      onClose();
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Fehler."),
  });

  const water = useMutation({
    mutationFn: () => api.waterPlant(plant.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plants"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      toast.success("Gegossen 💧");
      onClose(); // avoid showing a stale plant after watering
    },
  });

  return (
    <Backdrop onClose={onClose}>
      <div className="flex flex-col items-center gap-3">
        <img
          src={plant.image_url ?? "/placeholder.png"}
          alt={plant.name}
          className="pixelated h-36 w-36 rounded-lg border-2 border-pp-border object-cover"
        />
        <h2 className="pp-heading text-sm">{plant.name}</h2>
        <dl className="w-full text-xs leading-relaxed">
          <Row k="Intervall" v={`${plant.interval_days} Tage`} />
          <Row k="Zuletzt gegossen" v={plant.last_watered_at.replace("T", " ")} />
          <Row k="Status" v={plant.is_thirsty ? `💧 durstig (${plant.days_overdue}d)` : "✅ ok"} />
          {plant.water_amount_ml != null && (
            <Row k="Wassermenge" v={`${plant.water_amount_ml} ml`} />
          )}
          {plant.notes && <Row k="Notizen" v={plant.notes} />}
        </dl>
        <div className="mt-2 flex w-full gap-2">
          <button
            className="pp-btn flex-1"
            onClick={() => water.mutate()}
            disabled={water.isPending}
          >
            💧 Gießen
          </button>
          <button className="pp-btn flex-1" onClick={() => del.mutate()} disabled={del.isPending}>
            🗑 Löschen
          </button>
        </div>
      </div>
    </Backdrop>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-2 border-b border-pp-border/40 py-1">
      <dt className="opacity-70">{k}</dt>
      <dd className="text-right">{v}</dd>
    </div>
  );
}
