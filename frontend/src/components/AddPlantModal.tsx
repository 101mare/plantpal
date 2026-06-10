import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useI18n } from "../i18n";
import { InlineError, announce } from "./Feedback";
import { PixelIcon } from "./PixelIcon";

// Accept only what the server accepts (N27): the picker shouldn't offer HEIC/GIF/SVG that the
// backend then rejects with a 415 after a full upload. MAX_IMAGE_MB mirrors IMG_MAX_UPLOAD_MB.
export const IMAGE_ACCEPT = "image/jpeg,image/png,image/webp";
export const MAX_IMAGE_MB = 10;
export const MAX_IMAGE_BYTES = MAX_IMAGE_MB * 1024 * 1024;

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
  const [photoErr, setPhotoErr] = useState<string | null>(null);
  // Progressive disclosure (B2): room/notes/water amount stay folded — the fast path to
  // plant #1 is name + interval (+ optional photo). One-way reveal; a one-shot form
  // doesn't need a re-collapse toggle.
  const [more, setMore] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      const form = new FormData();
      form.set("name", name);
      form.set("interval_days", String(interval));
      if (notes) form.set("notes", notes);
      if (waterMl) form.set("water_amount_ml", waterMl);
      if (room.trim()) form.set("location_room", room.trim());
      if (file) form.set("image", file); // photo is optional (B1) — server renders placeholder
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
    if (f && f.size > MAX_IMAGE_BYTES) {
      // Reject oversized files client-side, before a doomed upload (N27).
      setPhotoErr(t("plant.photoTooLarge", { mb: MAX_IMAGE_MB }));
      e.target.value = "";
      setFile(null);
      setPreview((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return null;
      });
      return;
    }
    setFile(f);
    if (f) setPhotoErr(null);
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
    mutation.mutate(); // photo optional (B1): name is the only required field
  }

  return (
    <Backdrop onClose={onClose} label={t("nav.add")} dismissOnBackdrop={false}>
      <h2 className="pp-heading mb-4 text-sm">{t("nav.add")}</h2>
      <form className="flex flex-col gap-3" onSubmit={submit}>
        {/* Fast path first (B2): the only required field leads, the focus trap lands on it,
            and plant #1 is name + Save. Photo and details are optional extras below. */}
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
        <div className="flex flex-col items-center gap-2 text-xs">
          <span className="pp-heading text-[10px]">
            {t("plant.photo")} <span className="lowercase opacity-60">({t("plant.optional")})</span>
          </span>
          {/* The picker is a hidden <input> triggered by tappable controls (>=44pt). A bare
              <input type="file"> renders a sub-44pt native button on iOS (touch/A11Y). */}
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            aria-label={t("plant.photo")}
            aria-invalid={!!photoErr}
            aria-describedby={photoErr ? "addplant-photo-err" : undefined}
            className="rounded"
          >
            {preview ? (
              <img
                src={preview}
                alt=""
                className="pixelated h-24 w-24 rounded border-2 border-pp-border object-cover"
              />
            ) : (
              <div
                aria-hidden="true"
                className={`flex h-24 w-24 items-center justify-center rounded border-2 border-dashed ${
                  photoErr ? "border-pp-danger" : "border-pp-border"
                }`}
              >
                <PixelIcon name="camera" size={28} className="opacity-60" />
              </div>
            )}
          </button>
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            className="pp-tap text-[11px] underline opacity-80"
          >
            {preview ? t("plant.replacePhoto") : t("plant.photo")}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept={IMAGE_ACCEPT}
            onChange={pick}
            className="hidden"
            tabIndex={-1}
          />
          {photoErr && (
            <span id="addplant-photo-err" role="alert" className="text-[10px] text-pp-danger-ink">
              {photoErr}
            </span>
          )}
        </div>
        {/* Progressive disclosure: room/notes/amount are set-and-forget metadata — folded so
            the first-run form is 2 fields + photo. One-way reveal (no re-collapse). */}
        {!more ? (
          <button
            type="button"
            className="pp-tap self-center text-[11px] underline opacity-80"
            aria-expanded={false}
            onClick={() => setMore(true)}
          >
            {t("plant.moreDetails")}
          </button>
        ) : (
          <>
            <Field label={t("plant.room")}>
              <input
                value={room}
                maxLength={80}
                onChange={(e) => setRoom(e.target.value)}
                className="pp-input"
              />
            </Field>
            <Field label={t("plant.notes")}>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="pp-input"
              />
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
          </>
        )}
        <InlineError error={mutation.error} />
        {/* Sticky action row: with the keyboard open on a small phone the 6-field form scrolls, so the
            primary CTA (Save) stays pinned + reachable instead of below the scroll boundary (UX). */}
        <div className="sticky bottom-0 -mx-6 -mb-6 mt-2 flex flex-wrap gap-2 border-t-2 border-pp-border bg-pp-panel px-6 py-3">
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
    // N30: while the modal is open, lock background scroll (no touch scroll-bleed) and mark the
    // rest of the app inert so the screen-reader cursor and Tab can't wander into the background.
    // The dialog is portaled to <body> (outside #main), so it stays interactive.
    const { body } = document;
    const prevOverflow = body.style.overflow;
    const prevOverscroll = body.style.overscrollBehavior;
    body.style.overflow = "hidden";
    body.style.overscrollBehavior = "contain";
    const main = document.getElementById("main");
    main?.setAttribute("inert", "");
    main?.setAttribute("aria-hidden", "true");

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
      // Order matters: drop inert BEFORE restoring focus, or the trigger (inside #main) can't
      // receive focus (an inert element isn't focusable).
      main?.removeAttribute("inert");
      main?.removeAttribute("aria-hidden");
      body.style.overflow = prevOverflow;
      body.style.overscrollBehavior = prevOverscroll;
      prevActive?.focus?.(); // return focus to the trigger on close (A11Y-03)
    };
  }, [ref]);
}

export function Backdrop({
  children,
  onClose,
  label,
  dismissOnBackdrop = true,
}: {
  children: React.ReactNode;
  onClose: () => void;
  label?: string;
  /** Whether a tap on the dark backdrop closes the sheet. Read-only sheets: yes; input forms: no —
   *  a stray backdrop tap must not silently discard a half-filled form (UX-04). Escape + the explicit
   *  Cancel/Close buttons always close. */
  dismissOnBackdrop?: boolean;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  // onClose is often an inline arrow (new identity each render) — keep it in a ref so the
  // mount-only effect below doesn't re-run and push a second history entry on every render.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCloseRef.current();
    };
    window.addEventListener("keydown", onKey);
    // Push a history entry so the Android / browser Back gesture (and the PWA back-swipe) closes the
    // sheet instead of navigating away from the page — the expected mobile behaviour for an overlay.
    window.history.pushState({ ppSheet: true }, "");
    const onPop = () => onCloseRef.current();
    window.addEventListener("popstate", onPop);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("popstate", onPop);
      // Closed via button/Escape → our entry is still on top, pop it so Back isn't a dead no-op.
      // Closed via Back → the entry is already gone (state no longer ours), so we don't double-pop.
      if ((window.history.state as { ppSheet?: boolean } | null)?.ppSheet) window.history.back();
    };
  }, []);
  useFocusTrap(dialogRef);
  // Portal to <body> so the dialog lives outside #main (which we mark inert above). Anchored to the
  // TOP on phones (items-start) so the focused field + action row stay above the on-screen keyboard;
  // centred on larger screens (sm:items-center).
  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 p-4 sm:items-center"
      // Float below the notch: the dialog is portaled to <body> (bypassing #root's safe-area pad), and
      // the body::before notch scrim (z-60) sits above this z-50 layer, so a flat 16px top would hide
      // the sheet header behind it on notched iPhones.
      style={{ paddingTop: "max(1rem, env(safe-area-inset-top))" }}
      onClick={dismissOnBackdrop ? onClose : undefined}
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
    </div>,
    document.body,
  );
}
