import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError } from "../api";
import { useMe } from "../App";

export function SettingsPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { data: me } = useMe();
  const { data: settings } = useQuery({ queryKey: ["settings"], queryFn: api.getSettings });
  const [inviteUrl, setInviteUrl] = useState<string | null>(null);

  const toggle = useMutation({
    mutationFn: (enabled: boolean) => api.updateSettings(enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Fehler."),
  });

  const logout = useMutation({
    mutationFn: api.logout,
    onSuccess: () => {
      qc.clear();
      navigate("/login");
    },
  });

  const invite = useMutation({
    mutationFn: () => api.createInvite(),
    onSuccess: (r) => setInviteUrl(r.invite_url),
    onError: (err) => toast.error(err instanceof ApiError ? err.message : "Fehler."),
  });

  const removeAccount = useMutation({
    mutationFn: api.deleteAccount,
    onSuccess: () => {
      qc.clear();
      navigate("/login");
    },
  });

  return (
    <div className="mx-auto max-w-md p-4">
      <header className="mb-6 flex items-center justify-between">
        <h1 className="pp-heading text-lg">Settings</h1>
        <Link to="/" className="pp-btn">
          Zurück
        </Link>
      </header>

      <div className="pp-frame mb-4 p-4 text-xs">
        <p className="mb-3 opacity-80">Angemeldet als {settings?.email}</p>
        <label className="flex items-center justify-between gap-3">
          Email-Reminder
          <input
            type="checkbox"
            checked={settings?.email_reminders_enabled ?? false}
            onChange={(e) => toggle.mutate(e.target.checked)}
            className="h-5 w-5"
          />
        </label>
      </div>

      {me?.is_admin && (
        <div className="pp-frame mb-4 p-4 text-xs">
          <h2 className="pp-heading mb-2 text-xs">Einladungen</h2>
          <button
            className="pp-btn w-full"
            onClick={() => invite.mutate()}
            disabled={invite.isPending}
          >
            Invite-Link generieren
          </button>
          {inviteUrl && (
            <input
              readOnly
              value={inviteUrl}
              onFocus={(e) => e.target.select()}
              className="mt-3 w-full rounded border-2 border-pp-border bg-pp-panel-2 p-2 text-[10px]"
            />
          )}
        </div>
      )}

      <div className="flex flex-col gap-2">
        <button className="pp-btn" onClick={() => logout.mutate()}>
          Logout
        </button>
        <button
          className="pp-btn"
          style={{ background: "#7c3a3a", borderColor: "#5e2a2a" }}
          onClick={() => {
            if (confirm("Account und alle Pflanzen endgültig löschen?")) removeAccount.mutate();
          }}
        >
          Account löschen
        </button>
      </div>
    </div>
  );
}
