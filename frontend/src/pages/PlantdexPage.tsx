import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useI18n } from "../i18n";
import type { Plant } from "../types";
import { PlantCard } from "../components/PlantCard";
import { ThirstySection } from "../components/ThirstySection";
import { AddPlantModal } from "../components/AddPlantModal";
import { PlantDetailModal } from "../components/PlantDetailModal";
import { ErrorState, InlineError, announce } from "../components/Feedback";

type Sort = "thirsty" | "name" | "recent";

export function PlantdexPage() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const {
    data: plants,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["plants"],
    queryFn: api.listPlants,
  });
  const [adding, setAdding] = useState(false);
  const [selected, setSelected] = useState<Plant | null>(null);
  const [wateringId, setWateringId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<Sort>("thirsty");
  const [pendingDelete, setPendingDelete] = useState<Set<number>>(new Set());
  const [actionError, setActionError] = useState<unknown>(null);
  const deleteTimers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  // Clear pending delete timers on unmount so a delayed delete can't fire after we leave.
  useEffect(() => {
    const timers = deleteTimers.current;
    return () => {
      timers.forEach((tid) => clearTimeout(tid));
      timers.clear();
    };
  }, []);

  const water = useMutation({
    mutationFn: (id: number) => api.waterPlant(id),
    onMutate: (id) => {
      setActionError(null);
      setWateringId(id);
    },
    onSettled: () => setWateringId(null),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plants"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      // The card silently drops out of the thirsty list; announce it for screen readers.
      announce(t("plant.watered"));
    },
    onError: (err) => setActionError(err),
  });

  function unmarkPending(id: number) {
    setPendingDelete((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }

  function handleUndo(id: number) {
    const tid = deleteTimers.current.get(id);
    if (tid) clearTimeout(tid);
    deleteTimers.current.delete(id);
    unmarkPending(id);
    announce(t("plant.restored"));
  }

  // Soft-delete with undo: keep the plant in `pendingDelete` (survives refetch) and run the real
  // delete after a 5s grace window. While pending, the plant renders in place as an undo card
  // (no floating toast); undo cancels the timer and un-hides. Timers are also cleared on unmount.
  function handleDelete(plant: Plant) {
    setActionError(null);
    setPendingDelete((prev) => new Set(prev).add(plant.id));
    announce(t("plant.deleted")); // screen-reader cue; sighted users see the undo card appear
    const timer = setTimeout(() => {
      deleteTimers.current.delete(plant.id);
      api
        .deletePlant(plant.id)
        .then(() => {
          qc.invalidateQueries({ queryKey: ["plants"] });
          qc.invalidateQueries({ queryKey: ["stats"] });
        })
        .catch((err) => setActionError(err))
        .finally(() => unmarkPending(plant.id));
    }, 5000);
    deleteTimers.current.set(plant.id, timer);
  }

  // Plants not pending deletion — drives the thirsty section and the visible counts.
  const livePlants = useMemo(
    () => (plants ?? []).filter((p) => !pendingDelete.has(p.id)),
    [plants, pendingDelete],
  );
  const thirsty = livePlants.filter((p) => p.is_thirsty);

  // The render list keeps plants that are pending deletion, so each shows in place as an undo
  // card at its original spot. They bypass search/filter so the 5s undo window stays reachable.
  const visible = useMemo(() => {
    let list = plants ?? [];
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (p) =>
          pendingDelete.has(p.id) ||
          p.name.toLowerCase().includes(q) ||
          (p.location_room ?? "").toLowerCase().includes(q),
      );
    }
    const sorted = [...list];
    if (sort === "name") sorted.sort((a, b) => a.name.localeCompare(b.name));
    else if (sort === "recent")
      sorted.sort((a, b) => b.last_watered_at.localeCompare(a.last_watered_at));
    else sorted.sort((a, b) => b.days_overdue - a.days_overdue || a.name.localeCompare(b.name));
    return sorted;
  }, [plants, pendingDelete, search, sort]);

  // Count only live plants for the heading (pending-delete cards shouldn't inflate the totals).
  const liveCount = livePlants.length;
  const visibleLiveCount = visible.filter((p) => !pendingDelete.has(p.id)).length;

  return (
    <div className="mx-auto max-w-3xl p-4">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 tabIndex={-1}>
          <img src="/wordmark.png" alt="PlantPal" className="h-9 w-auto" />
        </h1>
        <nav className="flex gap-2">
          <Link to="/stats" className="pp-btn">
            {t("nav.stats")}
          </Link>
          <Link to="/settings" className="pp-btn">
            {t("nav.settings")}
          </Link>
          <button type="button" className="pp-btn" onClick={() => setAdding(true)}>
            {t("nav.add")}
          </button>
        </nav>
      </header>

      {isLoading ? (
        <p className="pp-heading text-center text-sm">{t("app.loading")}</p>
      ) : isError ? (
        <ErrorState onRetry={() => qc.invalidateQueries({ queryKey: ["plants"] })} />
      ) : (plants ?? []).length === 0 ? (
        <div className="pp-frame p-8 text-center text-sm">
          <img src="/mascot.webp" alt="" className="mx-auto mb-4 w-28" />
          <p className="pp-heading mb-2 text-sm">{t("empty.title")}</p>
          <p className="mb-4 opacity-70">{t("empty.hint")}</p>
          <button type="button" className="pp-btn" onClick={() => setAdding(true)}>
            {t("empty.cta")}
          </button>
        </div>
      ) : (
        <>
          <InlineError error={actionError} className="mb-3 text-center" />
          <ThirstySection plants={thirsty} onWater={water.mutate} wateringId={wateringId} />

          {/* Search + sort share one row; the "thirsty only" filter was dropped — thirsty plants
              already surface in the section above, so it was redundant. */}
          <div className="mb-3 flex items-center gap-2">
            <input
              className="pp-input min-w-0 flex-1"
              placeholder={t("list.search")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <select
              className="pp-input w-auto shrink-0"
              value={sort}
              onChange={(e) => setSort(e.target.value as Sort)}
            >
              <option value="thirsty">{t("list.sort.thirsty")}</option>
              <option value="name">{t("list.sort.name")}</option>
              <option value="recent">{t("list.sort.recent")}</option>
            </select>
          </div>

          <h2 className="pp-heading mb-3 text-sm">
            {t("nav.plantdex")} ({search.trim() ? `${visibleLiveCount}/${liveCount}` : liveCount})
          </h2>
          {visible.length === 0 ? (
            <div className="pp-frame p-6 text-center text-sm">
              <p className="mb-3 opacity-80">{t("list.noResults")}</p>
              <button type="button" className="pp-btn" onClick={() => setSearch("")}>
                {t("list.resetFilters")}
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {visible.map((p) =>
                pendingDelete.has(p.id) ? (
                  <UndoCard key={p.id} name={p.name} onUndo={() => handleUndo(p.id)} />
                ) : (
                  <PlantCard key={p.id} plant={p} onClick={() => setSelected(p)} />
                ),
              )}
            </div>
          )}
        </>
      )}

      {adding && <AddPlantModal onClose={() => setAdding(false)} />}
      {selected && (
        <PlantDetailModal
          plant={selected}
          onClose={() => setSelected(null)}
          onDelete={handleDelete}
        />
      )}
    </div>
  );
}

/** In-place stand-in for a plant card during its 5-second undo window (replaces the old floating
 *  undo toast). The deletion itself is announced via the global live region, so this card is not
 *  a live region — just a labelled undo affordance sitting where the card used to be. */
function UndoCard({ name, onUndo }: { name: string; onUndo: () => void }) {
  const { t } = useI18n();
  return (
    <div className="flex items-center justify-between gap-2 rounded-lg border-2 border-dashed border-pp-border bg-pp-panel-2 p-2 text-xs">
      <span className="min-w-0 flex-1 truncate opacity-80">
        <span aria-hidden="true">🗑</span> {t("plant.deletedName", { name })}
      </span>
      <button
        type="button"
        className="pp-btn shrink-0"
        onClick={onUndo}
        aria-label={`${t("plant.undo")}: ${name}`}
      >
        {t("plant.undo")}
      </button>
    </div>
  );
}
