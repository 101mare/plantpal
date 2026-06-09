import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { codeMessage, useI18n } from "../i18n";
import { LangThemeBar } from "../components/LangThemeBar";
import { InlineError } from "../components/Feedback";

export function LoginPage() {
  const { t } = useI18n();
  const [params, setParams] = useSearchParams();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  // Surface a backend redirect like /login?error=token_expired (e.g. from a dead magic link),
  // then strip the param so a refresh doesn't keep re-showing it (N21).
  const [linkErrorCode, setLinkErrorCode] = useState<string | null>(null);
  useEffect(() => {
    const code = params.get("error");
    if (!code) return;
    setLinkErrorCode(code);
    const next = new URLSearchParams(params);
    next.delete("error");
    setParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    setLinkErrorCode(null);
    try {
      await api.requestLogin(email);
      setSent(true);
    } catch (ex) {
      setErr(ex);
    } finally {
      setBusy(false);
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
        {linkErrorCode && (
          <div role="alert" className="pp-frame mb-4 p-3 text-center text-sm text-pp-danger">
            {codeMessage(linkErrorCode, t)}
          </div>
        )}
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
              className="mt-3 block min-h-[44px] w-full py-2 text-xs underline"
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
                autoComplete="email"
                autoCapitalize="none"
                spellCheck={false}
                enterKeyHint="send"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="pp-input mt-2"
                placeholder={t("login.emailPlaceholder")}
              />
            </label>
            <button type="submit" className="pp-btn" disabled={busy}>
              {busy ? "…" : t("login.sendLink")}
            </button>
            <InlineError error={err} />
          </form>
        )}
        <LangThemeBar />
      </div>
    </div>
  );
}
