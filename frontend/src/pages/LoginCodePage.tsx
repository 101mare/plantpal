import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useI18n } from "../i18n";
import { InlineError } from "../components/Feedback";

export function LoginCodePage() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState(params.get("email") ?? "");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await api.verifyCode(email, code);
      await qc.invalidateQueries({ queryKey: ["me"] });
      nav("/");
    } catch (ex) {
      setErr(ex);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full items-center justify-center p-4">
      <div className="w-full max-w-md">
        <h1 className="pp-heading mb-6 text-center text-lg">🌱 PlantPal</h1>
        <form onSubmit={submit} className="pp-frame flex flex-col gap-4 p-8">
          <h2 className="pp-heading text-sm">{t("login.codeTitle")}</h2>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="pp-input"
            placeholder={t("login.email")}
          />
          <input
            inputMode="numeric"
            pattern="\d{6}"
            maxLength={6}
            required
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            className="pp-input text-center text-lg tracking-[0.4em]"
            placeholder="••••••"
            aria-label={t("login.code")}
          />
          <button type="submit" className="pp-btn" disabled={busy || code.length !== 6}>
            {busy ? "…" : t("login.verify")}
          </button>
          <InlineError error={err} className="text-center" />
          <Link to="/login" className="text-center text-[10px] underline opacity-70">
            {t("nav.back")}
          </Link>
        </form>
      </div>
    </div>
  );
}
