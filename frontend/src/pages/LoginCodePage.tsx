import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useI18n } from "../i18n";
import { InlineError, announce } from "../components/Feedback";

export function LoginCodePage() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState(params.get("email") ?? "");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);

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

  // The page tells locked-out/expired users to "request a new code" — give them the button (N28).
  async function resend() {
    if (!email) return;
    setResending(true);
    setErr(null);
    setResent(false);
    try {
      await api.requestLogin(email);
      setResent(true);
      announce(t("login.resendDone"));
    } catch (ex) {
      setErr(ex);
    } finally {
      setResending(false);
    }
  }

  return (
    <div className="flex h-full items-center justify-center p-4">
      <div className="w-full max-w-md">
        <h1 className="mb-6 text-center" tabIndex={-1}>
          <img
            src="/wordmark.png"
            alt="PlantPal"
            width={735}
            height={160}
            className="mx-auto h-14 w-auto"
          />
        </h1>
        <form onSubmit={submit} className="pp-frame flex flex-col gap-4 p-8">
          <h2 className="pp-heading text-sm">{t("login.codeTitle")}</h2>
          <input
            type="email"
            required
            autoComplete="email"
            autoCapitalize="none"
            spellCheck={false}
            aria-label={t("login.email")}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="pp-input"
            placeholder={t("login.email")}
          />
          <input
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="\d{6}"
            maxLength={6}
            required
            autoFocus
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
          <button
            type="button"
            onClick={resend}
            disabled={!email || resending}
            className="flex min-h-[44px] items-center justify-center text-[11px] underline opacity-80 disabled:opacity-40"
          >
            {resending ? "…" : t("login.resend")}
          </button>
          {resent && (
            <p role="status" className="text-center text-[11px] text-pp-gold">
              ✓ {t("login.resendDone")}
            </p>
          )}
          <Link
            to="/login"
            className="flex min-h-[44px] items-center justify-center text-[10px] underline opacity-70"
          >
            {t("nav.back")}
          </Link>
        </form>
      </div>
    </div>
  );
}
