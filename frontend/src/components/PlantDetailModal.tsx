import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useI18n } from "../i18n";
import type { Plant } from "../types";
import { Backdrop, Field } from "./AddPlantModal";
import { InlineError, announce } from "./Feedback";
import { daysSince, plantStatus } from "../status";

export function PlantDetailModal({
  plant,
  onClose,
  onDelete,
}: {
  plant: Plant;
  onClose: () => void;
  onDelete: (p: Plant) => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [imgBust, setImgBust] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);

  const water = useMutation({
    mutationFn: () => api.waterPlant(plant.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plants"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      // No toast — closing the modal reveals the now-fresh card; announce for screen readers.
      announce(t("plant.watered"));
      onClose();
    },
  });

  const uploadImg = useMutation({
    mutationFn: (file: File) => {
      const f = new FormData();
      f.set("image", file);
      return api.uploadImage(plant.id, f);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plants"] });
      setImgBust((n) => n + 1); // refresh image in place, keep modal open (UX-14)
      // The swapped-in image is the visible confirmation; announce for screen readers.
      announce(t("plant.photoReplaced"));
    },
  });

  if (editing)
    return <EditView plant={plant} onClose={onClose} onCancel={() => setEditing(false)} />;

  const since = daysSince(plant.last_watered_at);
  const lastWatered =
    since == null
      ? plant.last_watered_at
      : since <= 0
        ? t("date.today")
        : since === 1
          ? t("date.yesterday")
          : t("date.daysAgo", { n: since });
  const level = plantStatus(plant);
  const statusText =
    level === "due" || level === "overdue"
      ? t("plant.overdue", { n: plant.days_overdue })
      : t(level === "soon" ? "status.soon" : "status.ok");
  const imgSrc = plant.image_url
    ? `${plant.image_url}${imgBust ? `?v=${imgBust}` : ""}`
    : "/placeholder.png";

  return (
    <Backdrop onClose={onClose} label={plant.name}>
      <div className="flex flex-col items-center gap-3">
        <img
          src={imgSrc}
          alt={plant.name}
          className="pixelated h-36 w-36 rounded-lg border-2 border-pp-border object-cover"
        />
        <button
          type="button"
          className="min-h-[44px] px-3 py-2 text-xs underline disabled:opacity-50"
          disabled={uploadImg.isPending}
          onClick={() => fileRef.current?.click()}
        >
          {uploadImg.isPending ? `${t("plant.replacePhoto")}…` : t("plant.replacePhoto")}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) uploadImg.mutate(f);
          }}
        />
        <h2 className="pp-heading text-sm">{plant.name}</h2>
        <dl className="w-full text-xs leading-relaxed">
          <Row k={t("plant.interval")} v={t("plant.everyDays", { n: plant.interval_days })} />
          {plant.location_room && <Row k={t("plant.room")} v={plant.location_room} />}
          <Row k={t("plant.lastWatered")} v={lastWatered} />
          <Row k={t("plant.status")} v={statusText} />
          {plant.water_amount_ml != null && (
            <Row k={t("plant.amount")} v={`${plant.water_amount_ml} ml`} />
          )}
          {plant.notes && <Row k={t("plant.notes")} v={plant.notes} />}
        </dl>
        <InlineError error={water.error ?? uploadImg.error} className="text-center" />
        <div className="mt-2 flex w-full gap-2">
          <button
            type="button"
            className="pp-btn flex-1"
            onClick={() => water.mutate()}
            disabled={water.isPending}
          >
            <span aria-hidden="true">💧</span> {water.isPending ? "…" : t("plant.water")}
          </button>
          <button type="button" className="pp-btn flex-1" onClick={() => setEditing(true)}>
            <span aria-hidden="true">✏️</span> {t("plant.edit")}
          </button>
        </div>
        {/* Destructive action separated from the primary buttons to prevent mis-taps (UX-08) */}
        <button
          type="button"
          className="mt-1 min-h-[44px] px-3 py-2 text-xs text-pp-danger underline"
          onClick={() => {
            onDelete(plant);
            onClose();
          }}
        >
          <span aria-hidden="true">🗑</span> {t("plant.delete")}
        </button>
      </div>
    </Backdrop>
  );
}

function EditView({
  plant,
  onClose,
  onCancel,
}: {
  plant: Plant;
  onClose: () => void;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [name, setName] = useState(plant.name);
  const [interval, setIntervalDays] = useState(plant.interval_days);
  const [notes, setNotes] = useState(plant.notes ?? "");
  const [room, setRoom] = useState(plant.location_room ?? "");
  const [waterMl, setWaterMl] = useState(
    plant.water_amount_ml != null ? String(plant.water_amount_ml) : "",
  );

  const save = useMutation({
    mutationFn: () =>
      api.updatePlant(plant.id, {
        name,
        interval_days: interval,
        notes: notes || null,
        location_room: room.trim() || null,
        water_amount_ml: waterMl ? Number(waterMl) : null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plants"] });
      // No toast — closing the modal reveals the updated card; announce for screen readers.
      announce(t("plant.saved"));
      onClose();
    },
  });

  return (
    <Backdrop onClose={onClose} label={plant.name}>
      <h2 className="pp-heading mb-4 text-sm">{plant.name}</h2>
      <form
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <Field label={`${t("plant.name")} *`}>
          <input
            className="pp-input"
            value={name}
            required
            onChange={(e) => setName(e.target.value)}
          />
        </Field>
        <Field label={t("plant.interval")}>
          <input
            type="number"
            min={1}
            max={365}
            inputMode="numeric"
            className="pp-input"
            value={interval}
            onChange={(e) => setIntervalDays(Number(e.target.value))}
          />
        </Field>
        <Field label={t("plant.room")}>
          <input
            className="pp-input"
            value={room}
            maxLength={80}
            onChange={(e) => setRoom(e.target.value)}
          />
        </Field>
        <Field label={t("plant.notes")}>
          <textarea className="pp-input" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </Field>
        <Field label={t("plant.amount")}>
          <input
            type="number"
            min={0}
            step={10}
            inputMode="numeric"
            className="pp-input"
            value={waterMl}
            onChange={(e) => setWaterMl(e.target.value)}
          />
        </Field>
        <InlineError error={save.error} />
        <div className="mt-2 flex gap-2">
          <button type="submit" className="pp-btn flex-1" disabled={save.isPending}>
            {save.isPending ? "…" : t("plant.save")}
          </button>
          <button type="button" className="pp-btn flex-1" onClick={onCancel}>
            {t("plant.cancel")}
          </button>
        </div>
      </form>
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
