import { useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { api } from "../api";
import { useI18n } from "../i18n";
import { LangThemeBar } from "../components/LangThemeBar";
import { InlineError } from "../components/Feedback";

export function RegisterPage() {
  const { t } = useI18n();
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [email, setEmail] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await api.register(token, email);
      setDone(true);
    } catch (ex) {
      setErr(ex);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="pp-frame p-8">
          <h1 className="mb-4 text-center" tabIndex={-1}>
            <img
              src="/wordmark.png"
              alt="PlantPal"
              width={735}
              height={160}
              className="mx-auto h-12 w-auto"
            />
          </h1>
          <h2 className="pp-heading mb-6 text-center text-sm">{t("register.title")}</h2>
          {!token ? (
            <p className="text-center text-sm">{t("register.noToken")}</p>
          ) : done ? (
            <p className="text-center text-sm leading-relaxed">
              {t("register.done")}{" "}
              <Link to="/login" className="text-pp-gold underline">
                {t("register.toLogin")}
              </Link>
            </p>
          ) : (
            <form onSubmit={submit} className="flex flex-col gap-4">
              <label className="text-xs">
                {t("register.email")}
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
                {busy ? t("register.submitting") : t("register.submit")}
              </button>
              <InlineError error={err} />
            </form>
          )}
        </div>
        <LangThemeBar />
      </div>
    </div>
  );
}
