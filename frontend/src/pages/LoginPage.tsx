import { useState } from "react";
import { toast } from "sonner";
import { api, ApiError } from "../api";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.requestLogin(email);
      setSent(true);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Fehler beim Senden.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full items-center justify-center p-4">
      <div className="pp-frame w-full max-w-md p-8">
        <h1 className="pp-heading mb-6 text-center text-lg">🌱 PlantPal</h1>
        {sent ? (
          <p className="text-center text-sm leading-relaxed">
            Wenn diese Email einen Account hat, ist ein Login-Link unterwegs. Schau in dein
            Postfach.
          </p>
        ) : (
          <form onSubmit={submit} className="flex flex-col gap-4">
            <label className="text-xs">
              Email
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-2 w-full rounded-lg border-2 border-pp-border bg-pp-panel-2 p-3 text-sm"
                placeholder="du@beispiel.de"
              />
            </label>
            <button type="submit" className="pp-btn" disabled={busy}>
              {busy ? "Sende…" : "Login-Link senden"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
