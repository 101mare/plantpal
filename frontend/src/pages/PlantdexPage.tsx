import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError } from "../api";
import type { Plant } from "../types";
import { PlantCard } from "../components/PlantCard";
import { ThirstySection } from "../components/ThirstySection";
import { AddPlantModal } from "../components/AddPlantModal";
import { PlantDetailModal } from "../components/PlantDetailModal";

export function PlantdexPage() {
  const qc = useQueryClient();
  const { data: plants, isLoading } = useQuery({ queryKey: ["plants"], queryFn: api.listPlants });
  const [adding, setAdding] = useState(false);
  const [selected, setSelected] = useState<Plant | null>(null);
  const [wateringId, setWateringId] = useState<number | null>(null);

  const water = useMutation({
    mutationFn: (id: number) => api.waterPlant(id),
    onMutate: (id) => setWateringId(id),
    onSettled: () => setWateringId(null),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plants"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Konnte nicht gießen."),
  });

  const thirsty = (plants ?? []).filter((p) => p.is_thirsty);

  return (
    <div className="mx-auto max-w-3xl p-4">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="pp-heading text-lg">🌱 PlantPal</h1>
        <nav className="flex gap-2">
          <Link to="/stats" className="pp-btn">
            Stats
          </Link>
          <Link to="/settings" className="pp-btn">
            Settings
          </Link>
          <button className="pp-btn" onClick={() => setAdding(true)}>
            Add Plant
          </button>
        </nav>
      </header>

      {isLoading ? (
        <p className="pp-heading text-center text-sm">Lade Plantdex…</p>
      ) : (
        <>
          <ThirstySection plants={thirsty} onWater={water.mutate} wateringId={wateringId} />

          <h2 className="pp-heading mb-3 text-sm">My Plantdex ({plants?.length ?? 0})</h2>
          {plants && plants.length > 0 ? (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {plants.map((p) => (
                <PlantCard key={p.id} plant={p} onClick={() => setSelected(p)} />
              ))}
            </div>
          ) : (
            <div className="pp-frame p-8 text-center text-sm">
              <p className="mb-2">Noch keine Pflanzen.</p>
              <p className="opacity-70">Klicke „Add Plant“, um deine erste Pflanze einzutragen.</p>
            </div>
          )}
        </>
      )}

      {adding && <AddPlantModal onClose={() => setAdding(false)} />}
      {selected && <PlantDetailModal plant={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
