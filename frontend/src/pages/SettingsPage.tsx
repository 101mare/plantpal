import { useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { useI18n } from "../i18n";
import { useTheme } from "../theme";
import { Backdrop } from "../components/AddPlantModal";
import { ErrorState, InlineError, announce } from "../components/Feedback";
import type { Background, Locale, Theme } from "../types";

export function SettingsPage() {
  const { t, locale, setLocale } = useI18n();
  const { theme, setTheme, background, setBackground } = useTheme();
  const qc = useQueryClient();
  const nav = useNavigate();
  const settingsQuery = useQuery({ queryKey: ["settings"], queryFn: api.getSettings });
  const s = settingsQuery.data;
  const invitesQuery = useQuery({ queryKey: ["invites"], queryFn: api.listInvites });
  const invites = invitesQuery.data;
  const [inviteUrl, setInviteUrl] = useState<string | null>(null);
  const [newEmail, setNewEmail] = useState("");
  const [confirmDel, setConfirmDel] = useState(false);
  const [copied, setCopied] = useState(false);
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
      <header className="mb-6 flex items-center justify-between">
        <h1 className="pp-heading text-lg" tabIndex={-1}>
          {t("settings.title")}
        </h1>
        <Link to="/" className="pp-btn">
          {t("nav.back")}
        </Link>
      </header>

      {settingsQuery.isError ? (
        <ErrorState error={settingsQuery.error} onRetry={() => settingsQuery.refetch()} />
      ) : (
        <>
          <Section title={t("settings.account")}>
            <p className="mb-3 break-all opacity-80">{s?.email}</p>
            <details>
              <summary className="cursor-pointer text-pp-gold">{t("settings.changeEmail")}</summary>
              <div className="mt-2 flex flex-col gap-2">
                <input
                  type="email"
                  className="pp-input"
                  placeholder={t("settings.newEmail")}
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
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
            </details>
          </Section>

          <Section title={t("settings.emailReminders")}>
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
                type="number"
                min={0}
                max={23}
                inputMode="numeric"
                className="pp-input w-20"
                key={s?.reminder_hour ?? 8}
                defaultValue={s?.reminder_hour ?? 8}
                onBlur={(e) => {
                  const h = Number(e.target.value);
                  if (Number.isInteger(h) && h >= 0 && h <= 23) patch.mutate({ reminder_hour: h });
                  else e.target.value = String(s?.reminder_hour ?? 8); // reject NaN/out-of-range
                }}
              />
            </label>
            <InlineError error={patch.error} className="mt-2" />
          </Section>

          <Section title={`${t("settings.language")} / ${t("settings.theme")}`}>
            <div className="flex items-center justify-between gap-3">
              {t("settings.language")}
              <select
                className="pp-input w-auto"
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
                  readOnly
                  value={inviteUrl}
                  onFocus={(e) => e.target.select()}
                  className="pp-input flex-1 text-[10px]"
                />
                <button
                  type="button"
                  className="pp-btn"
                  onClick={() => {
                    navigator.clipboard?.writeText(inviteUrl);
                    // Inline confirmation at the trigger: the label briefly flips to "Copied ✓".
                    setCopied(true);
                    announce(t("settings.copied"));
                    window.setTimeout(() => setCopied(false), 1500);
                  }}
                >
                  {copied ? `✓ ${t("settings.copied")}` : t("settings.copy")}
                </button>
              </div>
            )}
            <ul className="mt-3 flex flex-col gap-2">
              {(invites ?? []).map((inv) => (
                <li key={inv.id} className="flex items-center justify-between gap-2 text-[10px]">
                  <span className="min-w-0 break-words">
                    {inv.used_count}/{inv.max_uses} {t("settings.inviteUses")} · {inv.status}
                  </span>
                  {inv.status === "active" && (
                    <button
                      type="button"
                      className="shrink-0 px-3 py-2 underline"
                      onClick={() => revoke.mutate(inv.id)}
                    >
                      {t("settings.revoke")}
                    </button>
                  )}
                </li>
              ))}
            </ul>
            <InlineError
              error={invitesQuery.error ?? createInvite.error ?? revoke.error}
              className="mt-2"
            />
          </Section>

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
            <button
              type="button"
              className="pp-btn"
              style={{ background: "#7c3a3a", borderColor: "#5e2a2a" }}
              onClick={() => setConfirmDel(true)}
            >
              {t("settings.deleteAccount")}
            </button>
          </div>

          {confirmDel && (
            <Backdrop onClose={() => setConfirmDel(false)}>
              <p className="mb-4 text-center text-sm">{t("settings.deleteConfirm")}</p>
              <div className="flex gap-2">
                <button
                  type="button"
                  className="pp-btn flex-1"
                  style={{ background: "#7c3a3a", borderColor: "#5e2a2a" }}
                  disabled={removeAccount.isPending}
                  onClick={() => removeAccount.mutate()}
                >
                  {t("settings.deleteAccount")}
                </button>
                <button
                  type="button"
                  className="pp-btn flex-1"
                  onClick={() => setConfirmDel(false)}
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

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="pp-frame mb-4 p-4 text-xs">
      <h2 className="pp-heading mb-2 text-xs">{title}</h2>
      {children}
    </div>
  );
}
