import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { codeMessage, useI18n } from "../i18n";
import { useTheme } from "../theme";
import { Backdrop } from "../components/AddPlantModal";
import { ErrorState, InlineError, announce } from "../components/Feedback";
import type { Background, Locale, Theme } from "../types";

export function SettingsPage() {
  const { t, locale, setLocale } = useI18n();
  const { theme, setTheme, background, setBackground } = useTheme();
  const qc = useQueryClient();
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const settingsQuery = useQuery({ queryKey: ["settings"], queryFn: api.getSettings });
  const s = settingsQuery.data;
  const invitesQuery = useQuery({ queryKey: ["invites"], queryFn: api.listInvites });
  const invites = invitesQuery.data;
  const [inviteUrl, setInviteUrl] = useState<string | null>(null);
  const inviteRef = useRef<HTMLInputElement>(null);
  const [newEmail, setNewEmail] = useState("");
  const [confirmDel, setConfirmDel] = useState(false);
  const [delText, setDelText] = useState("");
  const [copied, setCopied] = useState(false);
  const [emailOpen, setEmailOpen] = useState(false);
  const [emailBanner, setEmailBanner] = useState<{ tone: "danger" | "ok"; text: string } | null>(
    null,
  );

  // N21: surface the email-change link result the backend redirects to
  // (/settings?email_changed=1 or ?email_error=<code>), then strip it from the URL.
  useEffect(() => {
    const changed = params.get("email_changed");
    const errCode = params.get("email_error");
    if (!changed && !errCode) return;
    if (changed) setEmailBanner({ tone: "ok", text: t("settings.emailChanged") });
    else if (errCode) setEmailBanner({ tone: "danger", text: codeMessage(errCode, t) });
    const next = new URLSearchParams(params);
    next.delete("email_changed");
    next.delete("email_error");
    setParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // N23: the server is the source of truth for locale/theme (it also drives the reminder mails).
  // Adopt it once settings load so a device that drifted (or another device's change) reconciles,
  // instead of the dropdowns showing a stale localStorage value.
  useEffect(() => {
    if (!s) return;
    if (s.locale && s.locale !== locale) setLocale(s.locale);
    if (s.theme && s.theme !== theme) setTheme(s.theme);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s?.locale, s?.theme]);
  const patch = useMutation({
    mutationFn: api.updateSettings,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      // No toast — the toggle/select already shows its new value; announce for screen readers.
      announce(t("settings.saved"));
    },
  });
  const logout = useMutation({
    mutationFn: api.logout,
    onSuccess: () => {
      qc.clear();
      nav("/login");
    },
  });
  const removeAccount = useMutation({
    mutationFn: api.deleteAccount,
    onSuccess: () => {
      qc.clear();
      nav("/login");
    },
  });
  const createInvite = useMutation({
    mutationFn: () => api.createUserInvite(1),
    onSuccess: (r) => {
      setInviteUrl(r.invite_url);
      qc.invalidateQueries({ queryKey: ["invites"] });
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
  });
  const revoke = useMutation({
    mutationFn: (id: number) => api.revokeInvite(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["invites"] });
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
  });
  const changeEmail = useMutation({
    mutationFn: () => api.requestEmailChange(newEmail),
    onSuccess: () => {
      // Nothing visible changes here (a mail goes out elsewhere), so we keep a persistent inline
      // confirmation below the button — see changeEmail.isSuccess in the JSX. Announce for SR too.
      announce(t("settings.emailChangeSent"));
      setNewEmail("");
    },
  });

  function pickLocale(l: Locale) {
    const prev = locale;
    setLocale(l);
    patch.mutate({ locale: l }, { onError: () => setLocale(prev) });
  }
  function pickTheme(th: Theme) {
    const prev = theme;
    setTheme(th);
    patch.mutate({ theme: th }, { onError: () => setTheme(prev) });
  }

  return (
    <div className="mx-auto max-w-md p-4">
      {/* No back button — the persistent TabBar is the sole primary navigation (Instagram-style). */}
      <header className="mb-6">
        <h1 className="pp-heading text-lg" tabIndex={-1}>
          {t("settings.title")}
        </h1>
      </header>

      {emailBanner && (
        <div
          role={emailBanner.tone === "danger" ? "alert" : "status"}
          className={`pp-frame mb-4 p-3 text-center text-[11px] ${
            emailBanner.tone === "danger" ? "text-pp-danger-ink" : "text-pp-gold"
          }`}
        >
          {emailBanner.text}
        </div>
      )}

      {settingsQuery.isError ? (
        <ErrorState error={settingsQuery.error} onRetry={() => settingsQuery.refetch()} />
      ) : (
        <>
          <Section title={t("settings.account")}>
            <p className="mb-3 break-all opacity-80">{s?.email}</p>
            <button
              type="button"
              className="pp-tap flex min-h-[44px] w-full items-center justify-between"
              aria-expanded={emailOpen}
              aria-controls="email-change-panel"
              onClick={() => setEmailOpen((o) => !o)}
            >
              <span>{t("settings.changeEmail")}</span>
              <span aria-hidden="true">{emailOpen ? "▾" : "›"}</span>
            </button>
            {emailOpen && (
              <div id="email-change-panel" className="mt-2 flex flex-col gap-2">
                <input
                  type="email"
                  className="pp-input"
                  aria-label={t("settings.newEmail")}
                  placeholder={t("settings.newEmail")}
                  value={newEmail}
                  onChange={(e) => {
                    setNewEmail(e.target.value);
                    // N36: drop the sticky "sent ✓" so it doesn't linger / re-show on re-open.
                    if (changeEmail.isSuccess || changeEmail.isError) changeEmail.reset();
                  }}
                />
                <button
                  type="button"
                  className="pp-btn"
                  disabled={!newEmail || changeEmail.isPending}
                  onClick={() => changeEmail.mutate()}
                >
                  {t("settings.sendVerify")}
                </button>
                <InlineError error={changeEmail.error} />
                {changeEmail.isSuccess && (
                  <p role="status" className="text-[11px] leading-snug text-pp-gold">
                    ✓ {t("settings.emailChangeSent")}
                  </p>
                )}
              </div>
            )}
          </Section>

          <Section title={t("settings.notificationsSection")}>
            <label className="flex min-h-[44px] items-center justify-between gap-3">
              {t("settings.emailReminders")}
              <input
                type="checkbox"
                className="h-7 w-7"
                checked={s?.email_reminders_enabled ?? false}
                onChange={(e) => patch.mutate({ email_reminders_enabled: e.target.checked })}
              />
            </label>
            <label className="mt-3 flex items-center justify-between gap-3">
              {t("settings.reminderHour")}
              <input
                type="text"
                inputMode="numeric"
                className="pp-input w-20"
                key={s?.reminder_hour ?? 8}
                defaultValue={s?.reminder_hour ?? 8}
                placeholder="8"
                onBlur={(e) => {
                  const raw = e.target.value.trim();
                  if (raw === "") {
                    // N33: empty field = no change, NOT midnight (Number("") === 0 slips the guard).
                    e.target.value = String(s?.reminder_hour ?? 8);
                    return;
                  }
                  const h = Number(raw);
                  if (Number.isInteger(h) && h >= 0 && h <= 23) patch.mutate({ reminder_hour: h });
                  else e.target.value = String(s?.reminder_hour ?? 8); // reject NaN/out-of-range
                }}
              />
            </label>
            {/* The valid range was only enforced (invisibly) in onBlur — make it legible. */}
            <p className="mt-1 text-[11px] opacity-60">0 – 23 {t("settings.reminderHourUnit")}</p>
            <InlineError error={patch.error} className="mt-2" />
          </Section>

          <Section title={t("settings.display")}>
            <div className="flex items-center justify-between gap-3">
              {t("settings.language")}
              <select
                className="pp-input w-auto"
                aria-label={t("settings.language")}
                value={locale}
                onChange={(e) => pickLocale(e.target.value as Locale)}
              >
                <option value="de">Deutsch</option>
                <option value="en">English</option>
              </select>
            </div>
            <div className="mt-3 flex items-center justify-between gap-3">
              {t("settings.theme")}
              <select
                className="pp-input w-auto"
                aria-label={t("settings.theme")}
                value={theme}
                onChange={(e) => pickTheme(e.target.value as Theme)}
              >
                <option value="dark">{t("settings.theme.dark")}</option>
                <option value="light">{t("settings.theme.light")}</option>
              </select>
            </div>
            <div className="mt-3 flex items-center justify-between gap-3">
              {t("settings.background")}
              <select
                className="pp-input w-auto"
                aria-label={t("settings.background")}
                value={background}
                onChange={(e) => setBackground(e.target.value as Background)}
              >
                <option value="vines">{t("settings.bg.vines")}</option>
                <option value="vines-tiefsee">{t("settings.bg.tiefsee")}</option>
                <option value="vines-tanne">{t("settings.bg.tanne")}</option>
                <option value="vines-moos">{t("settings.bg.moos")}</option>
                <option value="vines-smaragd">{t("settings.bg.smaragd")}</option>
                <option value="vines-espresso">{t("settings.bg.espresso")}</option>
                <option value="vines-burgund">{t("settings.bg.burgund")}</option>
                <option value="none">{t("settings.bg.none")}</option>
              </select>
            </div>
          </Section>

          <Section title={t("settings.invites")}>
            {(s?.invite_quota ?? 0) === 0 && (invites ?? []).length === 0 ? (
              // First-run users (no quota, no history): a quiet line instead of a dead Create button
              // that could only return invite_quota_exceeded. Full UI returns once quota>0 or any
              // invite exists — so nothing (incl. revoke history) is lost.
              <p className="text-[11px] opacity-60">{t("settings.inviteNone")}</p>
            ) : (
              <>
                <p className="mb-2 opacity-70">
                  {t("settings.inviteQuota", { n: s?.invite_quota ?? 0 })}
                </p>
                <button
                  type="button"
                  className="pp-btn w-full"
                  disabled={createInvite.isPending}
                  onClick={() => createInvite.mutate()}
                >
                  {t("settings.createInvite")}
                </button>
                {inviteUrl && (
                  <div className="mt-2 flex gap-2">
                    <input
                      ref={inviteRef}
                      readOnly
                      value={inviteUrl}
                      onFocus={(e) => e.target.select()}
                      className="pp-input min-w-0 flex-1 text-[10px]"
                    />
                    <button
                      type="button"
                      className="pp-btn"
                      onClick={() => {
                        // Only claim "Copied ✓" if the write actually resolved. On a self-hosted Pi over
                        // http://<LAN-IP> there is no secure context, so navigator.clipboard is undefined
                        // (or rejects) — then select the field so the user can copy manually instead of
                        // getting a false success (UX/correctness).
                        const p = navigator.clipboard?.writeText(inviteUrl);
                        if (p) {
                          p.then(() => {
                            setCopied(true);
                            announce(t("settings.copied"));
                            // Collapse the ~60-char read-only field once the copy is confirmed; the
                            // insecure-context path below keeps it for manual selection.
                            window.setTimeout(() => {
                              setCopied(false);
                              setInviteUrl(null);
                            }, 1500);
                          }).catch(() => inviteRef.current?.select());
                        } else {
                          inviteRef.current?.select();
                        }
                      }}
                    >
                      {copied ? `✓ ${t("settings.copied")}` : t("settings.copy")}
                    </button>
                  </div>
                )}
                <ul className="mt-3 flex flex-col gap-2">
                  {(invites ?? []).map((inv) => (
                    <li
                      key={inv.id}
                      className="flex items-center justify-between gap-2 text-[10px]"
                    >
                      <span className="min-w-0 break-words">
                        {inv.used_count}/{inv.max_uses} {t("settings.inviteUses")} · {inv.status}
                      </span>
                      {inv.status === "active" && (
                        <button
                          type="button"
                          className="pp-tap shrink-0 px-3 underline disabled:opacity-40"
                          disabled={revoke.isPending}
                          onClick={() => revoke.mutate(inv.id)}
                        >
                          {revoke.isPending ? "…" : t("settings.revoke")}
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
                <InlineError
                  error={invitesQuery.error ?? createInvite.error ?? revoke.error}
                  className="mt-2"
                />
              </>
            )}
          </Section>

          <Section title={t("settings.dataSection")}>
            <div className="flex flex-col gap-2">
              <a href={api.exportUrl()} className="pp-btn text-center" download>
                {t("settings.export")}
              </a>
              <button
                type="button"
                className="pp-btn"
                disabled={logout.isPending}
                onClick={() => logout.mutate()}
              >
                {logout.isPending ? "…" : t("settings.logout")}
              </button>
              <InlineError error={logout.error} />
            </div>
          </Section>

          {/* The one irreversible action — spatially (mt-8) and chromatically (danger frame) isolated.
              Logout stays NEUTRAL above: it's reversible and doesn't belong in a danger zone. */}
          <div className="mt-8">
            <Section title={t("settings.danger")} tone="danger">
              <p className="mb-2 text-[11px] opacity-70">{t("settings.deleteHint")}</p>
              <button
                type="button"
                className="pp-btn w-full"
                style={{ background: "#7c3a3a", borderColor: "#5e2a2a" }}
                onClick={() => {
                  setDelText("");
                  setConfirmDel(true);
                }}
              >
                {t("settings.deleteAccount")}
              </button>
            </Section>
          </div>

          {/* Legal footer — signed-in users previously had NO path to Impressum/Datenschutz
              (only the logged-out LangThemeBar linked them): Apple 5.1.1(i) requires the privacy
              policy "easily accessible in-app", §5 DDG wants the Impressum ≤2 taps away. */}
          <nav
            aria-label={t("legal.navLabel")}
            className="mt-6 flex items-center justify-center gap-1 text-[11px] opacity-80"
          >
            <Link to="/impressum" className="pp-tap px-2 underline">
              {t("legal.imprint")}
            </Link>
            <span aria-hidden="true">·</span>
            <Link to="/datenschutz" className="pp-tap px-2 underline">
              {t("legal.privacy")}
            </Link>
          </nav>

          {confirmDel && (
            <Backdrop
              onClose={() => {
                setConfirmDel(false);
                setDelText("");
              }}
            >
              <p className="mb-3 text-center text-sm">{t("settings.deleteConfirm")}</p>
              {/* N29: require typing LÖSCHEN/DELETE so one mis-tap can't wipe the account. */}
              <label className="mb-1 block text-center text-[11px] opacity-80">
                {t("settings.deleteConfirmPrompt", { word: t("settings.deleteConfirmWord") })}
              </label>
              <input
                className="pp-input mb-4 text-center"
                value={delText}
                onChange={(e) => setDelText(e.target.value)}
                aria-label={t("settings.deleteConfirmWord")}
                autoComplete="off"
                autoCapitalize="characters"
                spellCheck={false}
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  className="pp-btn flex-1 disabled:opacity-40"
                  style={{ background: "#7c3a3a", borderColor: "#5e2a2a" }}
                  disabled={
                    removeAccount.isPending ||
                    delText.trim().toUpperCase() !== t("settings.deleteConfirmWord")
                  }
                  onClick={() => removeAccount.mutate()}
                >
                  {t("settings.deleteAccount")}
                </button>
                <button
                  type="button"
                  className="pp-btn flex-1"
                  onClick={() => {
                    setConfirmDel(false);
                    setDelText("");
                  }}
                >
                  {t("plant.cancel")}
                </button>
              </div>
              <InlineError error={removeAccount.error} className="mt-3 text-center" />
            </Backdrop>
          )}
        </>
      )}
    </div>
  );
}

function Section({
  title,
  children,
  tone = "default",
}: {
  title: string;
  children: ReactNode;
  tone?: "default" | "danger";
}) {
  const danger = tone === "danger";
  // Inline colors: .pp-frame's `border` shorthand and .pp-heading's `color` are unlayered, so they
  // win the cascade over Tailwind utilities — an inline style is the reliable danger override.
  return (
    <div
      className="pp-frame mb-4 p-4 text-xs"
      style={danger ? { borderColor: "var(--color-pp-danger)" } : undefined}
    >
      <h2
        className="pp-heading mb-2 text-xs"
        style={danger ? { color: "var(--color-pp-danger-ink)" } : undefined}
      >
        {title}
      </h2>
      {children}
    </div>
  );
}
