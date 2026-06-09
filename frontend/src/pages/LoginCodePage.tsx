import { useEffect, useRef, useState } from "react";
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
  const initial = params.get("email") ?? "";
  const [email, setEmail] = useState(initial);
  // On the happy path (arrived from LoginPage with ?email=) the email is a static line; only the
  // "wrong email" escape opens it for editing — so the code box stays the single primary field.
  const [editEmail, setEditEmail] = useState(!initial);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);
  // iOS one-time-code autofill drops all 6 digits at once → auto-submit. The ref guards StrictMode
  // double-invoke and re-submitting the same (wrong) code until it's edited.
  const autoSent = useRef("");

  async function submitCode() {
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

  function submit(e: React.FormEvent) {
    e.preventDefault();
    void submitCode();
  }

  // Auto-submit once a full 6-digit code is present (autofill or manual). On error busy→false but
  // code stays 6 and autoSent===code, so it won't loop until the user edits the code.
  useEffect(() => {
    if (code.length === 6 && !busy && autoSent.current !== code) {
      autoSent.current = code;
      void submitCode();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code, busy]);

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
          {editEmail ? (
            <input
              type="email"
              required
              autoComplete="email"
              autoCapitalize="none"
              spellCheck={false}
              enterKeyHint="next"
              aria-label={t("login.email")}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="pp-input"
              placeholder={t("login.emailPlaceholder")}
            />
          ) : (
            <div className="flex flex-col items-center gap-1">
              <p className="break-all text-center text-xs opacity-70">{email}</p>
              <button
                type="button"
                className="pp-tap mx-auto block text-xs underline opacity-70"
                onClick={() => setEditEmail(true)}
              >
                {t("login.wrongEmail")}
              </button>
            </div>
          )}
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
            className="flex min-h-[44px] items-center justify-center text-xs underline opacity-80 disabled:opacity-40"
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
            className="flex min-h-[44px] items-center justify-center text-xs underline opacity-70"
          >
            {t("nav.back")}
          </Link>
        </form>
      </div>
    </div>
  );
}
