import { useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { toast } from "sonner";
import { api, ApiError } from "../api";

export function RegisterPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [email, setEmail] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.register(token, email);
      setDone(true);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Registrierung fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full items-center justify-center p-4">
      <div className="pp-frame w-full max-w-md p-8">
        <h1 className="pp-heading mb-6 text-center text-lg">🌿 Account erstellen</h1>
        {!token ? (
          <p className="text-center text-sm">
            Ungültiger oder fehlender Einladungs-Link. Bitte fordere eine neue Einladung an.
          </p>
        ) : done ? (
          <p className="text-center text-sm leading-relaxed">
            Account erstellt! Wir haben dir einen Login-Link geschickt.{" "}
            <Link to="/login" className="text-pp-gold underline">
              Zum Login
            </Link>
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
              {busy ? "Erstelle…" : "Account erstellen"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
