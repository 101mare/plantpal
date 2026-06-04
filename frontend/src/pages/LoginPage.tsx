import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../api";
import { useI18n, errorText } from "../i18n";
import { LangThemeBar } from "../components/LangThemeBar";

export function LoginPage() {
  const { t } = useI18n();
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
      toast.error(errorText(err, t));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full items-center justify-center p-4">
      <div className="w-full max-w-md">
        <h1 className="pp-heading mb-6 text-center text-lg">🌱 PlantPal</h1>
        {sent ? (
          <div className="pp-frame p-8 text-center text-sm leading-relaxed">
            <p className="mb-4">{t("login.checkInbox")}</p>
            <Link
              to={`/login/code?email=${encodeURIComponent(email)}`}
              className="pp-btn inline-block"
            >
              {t("login.haveCode")}
            </Link>
            <button
              type="button"
              className="mt-3 block w-full py-2 text-xs underline"
              onClick={() => setSent(false)}
            >
              {t("login.wrongEmail")}
            </button>
          </div>
        ) : (
          <form onSubmit={submit} className="pp-frame flex flex-col gap-4 p-8">
            <h2 className="pp-heading text-sm">{t("login.title")}</h2>
            <label className="text-xs">
              {t("login.email")}
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="pp-input mt-2"
                placeholder="du@beispiel.de"
              />
            </label>
            <button type="submit" className="pp-btn" disabled={busy}>
              {busy ? "…" : t("login.sendLink")}
            </button>
          </form>
        )}
        <LangThemeBar />
      </div>
    </div>
  );
}
