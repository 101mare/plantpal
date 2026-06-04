import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "../api";
import { useI18n } from "../i18n";
import type { Plant } from "../types";
import { PlantCard } from "../components/PlantCard";
import { ThirstySection } from "../components/ThirstySection";
import { AddPlantModal } from "../components/AddPlantModal";
import { PlantDetailModal } from "../components/PlantDetailModal";
import { ErrorState, InlineError } from "../components/Feedback";

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
  const [thirstyOnly, setThirstyOnly] = useState(false);
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

  // Soft-delete with undo: hide locally via pendingDelete (survives refetch) + delayed real
  // delete. Undo cancels the timer and un-hides; the timer is also cleared on unmount.
  function handleDelete(plant: Plant) {
    setPendingDelete((prev) => new Set(prev).add(plant.id));
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
    toast(t("plant.deleted"), {
      duration: 5000,
      action: {
        label: t("plant.undo"),
        onClick: () => {
          const tid = deleteTimers.current.get(plant.id);
          if (tid) clearTimeout(tid);
          deleteTimers.current.delete(plant.id);
          unmarkPending(plant.id);
          toast.success(t("plant.restored"));
        },
      },
    });
  }

  const all = useMemo(
    () => (plants ?? []).filter((p) => !pendingDelete.has(p.id)),
    [plants, pendingDelete],
  );
  const thirsty = all.filter((p) => p.is_thirsty);

  const visible = useMemo(() => {
    let list = all;
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (p) =>
          p.name.toLowerCase().includes(q) || (p.location_room ?? "").toLowerCase().includes(q),
      );
    }
    if (thirstyOnly) list = list.filter((p) => p.is_thirsty);
    const sorted = [...list];
    if (sort === "name") sorted.sort((a, b) => a.name.localeCompare(b.name));
    else if (sort === "recent")
      sorted.sort((a, b) => b.last_watered_at.localeCompare(a.last_watered_at));
    else sorted.sort((a, b) => b.days_overdue - a.days_overdue || a.name.localeCompare(b.name));
    return sorted;
  }, [all, search, thirstyOnly, sort]);

  return (
    <div className="mx-auto max-w-3xl p-4">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="pp-heading text-lg" tabIndex={-1}>
          🌱 PlantPal
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
      ) : all.length === 0 ? (
        <div className="pp-frame p-8 text-center text-sm">
          <div className="mb-3 text-4xl">🪴</div>
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

          <div className="mb-3 flex flex-wrap items-center gap-2">
            <input
              className="pp-input min-w-[8rem] flex-1"
              placeholder={t("list.search")}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <select
              className="pp-input w-auto"
              value={sort}
              onChange={(e) => setSort(e.target.value as Sort)}
            >
              <option value="thirsty">{t("list.sort.thirsty")}</option>
              <option value="name">{t("list.sort.name")}</option>
              <option value="recent">{t("list.sort.recent")}</option>
            </select>
            <label className="flex items-center gap-1 text-[10px]">
              <input
                type="checkbox"
                checked={thirstyOnly}
                onChange={(e) => setThirstyOnly(e.target.checked)}
              />
              {t("list.filter.thirsty")}
            </label>
          </div>

          <h2 className="pp-heading mb-3 text-sm">
            {t("nav.plantdex")} (
            {search.trim() || thirstyOnly ? `${visible.length}/${all.length}` : all.length})
          </h2>
          {visible.length === 0 ? (
            <div className="pp-frame p-6 text-center text-sm">
              <p className="mb-3 opacity-80">{t("list.noResults")}</p>
              <button
                type="button"
                className="pp-btn"
                onClick={() => {
                  setSearch("");
                  setThirstyOnly(false);
                }}
              >
                {t("list.resetFilters")}
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {visible.map((p) => (
                <PlantCard key={p.id} plant={p} onClick={() => setSelected(p)} />
              ))}
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
