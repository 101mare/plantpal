import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useI18n } from "../i18n";
import { InlineError, announce } from "./Feedback";

export function AddPlantModal({ onClose }: { onClose: () => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [interval, setIntervalDays] = useState(7);
  const [notes, setNotes] = useState("");
  const [waterMl, setWaterMl] = useState("");
  const [room, setRoom] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [photoError, setPhotoError] = useState(false);

  const mutation = useMutation({
    mutationFn: async () => {
      const form = new FormData();
      form.set("name", name);
      form.set("interval_days", String(interval));
      if (notes) form.set("notes", notes);
      if (waterMl) form.set("water_amount_ml", waterMl);
      if (room.trim()) form.set("location_room", room.trim());
      form.set("image", file!);
      return api.createPlant(form);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plants"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      // No toast — closing the modal reveals the new card in the list; announce for screen readers.
      announce(t("plant.added"));
      onClose();
    },
  });

  function pick(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    if (f) setPhotoError(false);
    setPreview((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return f ? URL.createObjectURL(f) : null;
    });
  }
  useEffect(
    () => () => {
      if (preview) URL.revokeObjectURL(preview);
    },
    [preview],
  );

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      setPhotoError(true); // inline field error instead of a one-word toast (UX-04)
      return;
    }
    mutation.mutate();
  }

  return (
    <Backdrop onClose={onClose} label={t("nav.add")}>
      <h2 className="pp-heading mb-4 text-sm">{t("nav.add")}</h2>
      <form className="flex flex-col gap-3" onSubmit={submit}>
        <div className="flex flex-col items-center gap-2 text-xs">
          <span className="pp-heading text-[10px]">{t("plant.photo")} *</span>
          <label className="flex flex-col items-center gap-2">
            {preview ? (
              <img
                src={preview}
                alt=""
                className="pixelated h-24 w-24 rounded border-2 border-pp-border object-cover"
              />
            ) : (
              <div
                className={`flex h-24 w-24 items-center justify-center rounded border-2 border-dashed text-2xl ${
                  photoError ? "border-pp-danger" : "border-pp-border"
                }`}
              >
                📷
              </div>
            )}
            <input
              type="file"
              accept="image/*"
              onChange={pick}
              className="text-[10px]"
              aria-label={t("plant.photo")}
              aria-invalid={photoError}
            />
          </label>
          {photoError && (
            <span className="text-[10px] text-pp-danger">{t("plant.photoRequired")}</span>
          )}
        </div>
        <Field label={`${t("plant.name")} *`}>
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="pp-input"
          />
        </Field>
        <Field label={t("plant.interval")}>
          <input
            type="number"
            min={1}
            max={365}
            inputMode="numeric"
            value={interval}
            onChange={(e) => setIntervalDays(Number(e.target.value))}
            className="pp-input"
          />
        </Field>
        <Field label={t("plant.room")}>
          <input
            value={room}
            maxLength={80}
            onChange={(e) => setRoom(e.target.value)}
            className="pp-input"
          />
        </Field>
        <Field label={t("plant.notes")}>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} className="pp-input" />
        </Field>
        <Field label={t("plant.amount")}>
          <input
            type="number"
            min={0}
            step={10}
            inputMode="numeric"
            value={waterMl}
            onChange={(e) => setWaterMl(e.target.value)}
            className="pp-input"
          />
        </Field>
        <InlineError error={mutation.error} />
        <div className="mt-2 flex gap-2">
          <button type="submit" className="pp-btn flex-1" disabled={mutation.isPending}>
            {mutation.isPending ? "…" : t("plant.save")}
          </button>
          <button type="button" className="pp-btn flex-1" onClick={onClose}>
            {t("plant.cancel")}
          </button>
        </div>
      </form>
    </Backdrop>
  );
}

/** Persistent label above its input (placeholders vanish on type — UX-05 / A11Y-04). */
export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span>{label}</span>
      {children}
    </label>
  );
}

function useFocusTrap(ref: React.RefObject<HTMLElement | null>) {
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const prevActive = document.activeElement as HTMLElement | null;
    const sel =
      'a[href],button:not([disabled]),input:not([disabled]),textarea:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])';
    const items = () => Array.from(node.querySelectorAll<HTMLElement>(sel));
    (items()[0] ?? node).focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;
      const list = items();
      if (list.length === 0) return;
      const first = list[0];
      const last = list[list.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    node.addEventListener("keydown", onKey);
    return () => {
      node.removeEventListener("keydown", onKey);
      prevActive?.focus?.(); // return focus to the trigger on close (A11Y-03)
    };
  }, [ref]);
}

export function Backdrop({
  children,
  onClose,
  label,
}: {
  children: React.ReactNode;
  onClose: () => void;
  label?: string;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  useFocusTrap(dialogRef);
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        ref={dialogRef}
        className="pp-frame max-h-[90dvh] w-full max-w-md overflow-y-auto p-6"
        role="dialog"
        aria-modal="true"
        aria-label={label}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
