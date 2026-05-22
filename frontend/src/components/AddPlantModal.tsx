import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError } from "../api";

export function AddPlantModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [interval, setInterval] = useState(7);
  const [notes, setNotes] = useState("");
  const [waterMl, setWaterMl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      if (!file) throw new ApiError(400, "no_image", "Bitte ein Foto auswählen.");
      const form = new FormData();
      form.set("name", name);
      form.set("interval_days", String(interval));
      if (notes) form.set("notes", notes);
      if (waterMl) form.set("water_amount_ml", waterMl);
      form.set("image", file);
      return api.createPlant(form);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plants"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      toast.success("Pflanze hinzugefügt 🌱");
      onClose();
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Fehler."),
  });

  function pick(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    setPreview((prev) => {
      if (prev) URL.revokeObjectURL(prev); // free the previous preview
      return f ? URL.createObjectURL(f) : null;
    });
  }

  // Revoke the last object URL when the modal unmounts.
  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  return (
    <Backdrop onClose={onClose}>
      <h2 className="pp-heading mb-4 text-sm">Add Plant</h2>
      <form
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate();
        }}
      >
        <label className="flex flex-col items-center gap-2 text-xs">
          {preview ? (
            <img
              src={preview}
              alt=""
              className="pixelated h-24 w-24 rounded border-2 border-pp-border object-cover"
            />
          ) : (
            <div className="flex h-24 w-24 items-center justify-center rounded border-2 border-dashed border-pp-border text-2xl">
              📷
            </div>
          )}
          <input type="file" accept="image/*" required onChange={pick} className="text-[10px]" />
        </label>
        <input
          required
          placeholder="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="rounded-lg border-2 border-pp-border bg-pp-panel-2 p-2 text-sm"
        />
        <label className="text-xs">
          Gieß-Intervall (Tage)
          <input
            type="number"
            min={1}
            max={365}
            value={interval}
            onChange={(e) => setInterval(Number(e.target.value))}
            className="mt-1 w-full rounded-lg border-2 border-pp-border bg-pp-panel-2 p-2 text-sm"
          />
        </label>
        <textarea
          placeholder="Notizen (optional)"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          className="rounded-lg border-2 border-pp-border bg-pp-panel-2 p-2 text-sm"
        />
        <input
          type="number"
          placeholder="Wassermenge ml (optional)"
          value={waterMl}
          onChange={(e) => setWaterMl(e.target.value)}
          className="rounded-lg border-2 border-pp-border bg-pp-panel-2 p-2 text-sm"
        />
        <div className="mt-2 flex gap-2">
          <button type="submit" className="pp-btn flex-1" disabled={mutation.isPending}>
            {mutation.isPending ? "Speichere…" : "Speichern"}
          </button>
          <button type="button" className="pp-btn flex-1" onClick={onClose}>
            Abbrechen
          </button>
        </div>
      </form>
    </Backdrop>
  );
}

export function Backdrop({
  children,
  onClose,
}: {
  children: React.ReactNode;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div className="pp-frame w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        {children}
      </div>
    </div>
  );
}
