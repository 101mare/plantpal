# PlantPal auf dem Raspberry Pi — Runbook

> Für den Pi, der **schon andere Dienste hostet**: PlantPal kommt als eigenes
> Compose-Projekt (`name: plantpal`), öffnet **keine Host-Ports** (Ingress läuft
> ausschließlich über den Cloudflare Tunnel) und ist auf 512 MB RAM / 2 CPUs gedeckelt.
> ARM64-Build wurde cross-verifiziert (Image baut & importiert unter linux/arm64 ✓).

---

## 0. Voraussetzungen (einmalig prüfen)

- [ ] Raspberry Pi mit **64-bit-OS** (`uname -m` → `aarch64`). 2 GB RAM reichen, 4 GB komfortabel.
- [ ] **Docker + Compose-Plugin**: `docker --version && docker compose version`.
      Falls fehlt: `curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker $USER` (neu einloggen).
- [ ] **Domain aktiv:** `getplantpal.com` im Cloudflare-Dashboard auf Status **„Active"**
      (→ Nameserver-Umstellung, siehe `GOAL_PRODUCTION_READY.md` §7.1). Ohne „Active" kein Tunnel-Routing.
- [ ] **Resend-Account** mit verifizierter Absender-Domain (für Magic-Link-Mails):
      [resend.com](https://resend.com) → Domain `getplantpal.com` verifizieren (DNS-Records setzt
      Cloudflare) → API-Key erzeugen. *(Bis dahin funktioniert Login trotzdem — per CLI-Fallback, s. §7.)*

## 1. Erstinstallation

```bash
# 1) Code holen
cd /opt && sudo mkdir -p plantpal && sudo chown $USER plantpal
git clone https://github.com/101mare/plantpal.git plantpal && cd plantpal
git checkout production-ready   # bzw. main nach dem Merge

# 2) Konfiguration
cp .env.example .env
python3 -c "import secrets; print('TOKEN_PEPPER=' + secrets.token_urlsafe(48)); print('CSRF_SECRET=' + secrets.token_urlsafe(48))"
nano .env
```

In der `.env` setzen:

| Variable | Wert |
|---|---|
| `BASE_URL` | `https://getplantpal.com` |
| `TOKEN_PEPPER` / `CSRF_SECRET` | die zwei frisch generierten Zufallswerte (NIE wieder ändern — Pepper-Wechsel invalidiert alle Sessions/Tokens) |
| `RESEND_API_KEY` / `RESEND_FROM_EMAIL` | aus Resend, z. B. `PlantPal <gruss@getplantpal.com>` |
| `CLOUDFLARE_TUNNEL_TOKEN` | kommt in Schritt 2 |

## 2. Cloudflare Tunnel anlegen (einmalig, ~5 Min)

1. [Cloudflare Dashboard](https://one.dash.cloudflare.com) → **Zero Trust → Networks → Tunnels → Create a tunnel** (Typ „Cloudflared").
2. Name z. B. `plantpal-pi`. Den angezeigten **Token** (langer String nach `--token`) in die `.env` als `CLOUDFLARE_TUNNEL_TOKEN` eintragen. *(Die angebotenen Install-Kommandos ignorieren — cloudflared läuft bei uns als Compose-Service.)*
3. Tab **Public Hostname → Add**: Subdomain leer, Domain `getplantpal.com`, Service **HTTP** → `plantpal:8000`. Speichern.

## 3. Starten

```bash
docker compose up -d --build        # erster Build auf dem Pi: 5–15 Min
docker compose ps                   # beide Services "Up", plantpal "healthy"
curl -s https://getplantpal.com/api/health   # {"status":"ok"} von unterwegs
```

**Ersten Admin anlegen + einloggen:**

```bash
docker compose exec plantpal python -m plantpal.cli bootstrap-admin --email deine@mail.de
# druckt einen Login-Link → auf dem Handy öffnen → drin.
```

Danach: PWA installieren (Safari → Teilen → „Zum Home-Bildschirm"), in den Settings
Einladungen für Familie/Freunde erzeugen.

## 4. Updates einspielen

```bash
cd /opt/plantpal
./scripts/backup.sh                       # Sicherheits-Snapshot (s. §5)
git pull
docker compose up -d --build              # baut neu + startet um (~1 Min Downtime)
docker compose ps && curl -fsS https://getplantpal.com/api/health
```

Rollback bei Problemen: `git checkout <letzter-guter-commit> && docker compose up -d --build`.
**Deploy-Freeze:** Während ein App-Store-Review läuft, NICHT deployen/rebooten (Apple testet live).

## 5. Backups

**Standardweg (Cron auf dem Pi-Host):**

```bash
sudo mkdir -p /backup/plantpal && sudo chown $USER /backup/plantpal
crontab -e   # ergänzen:
# 30 3 * * *  cd /opt/plantpal && PLANTPAL_BACKUP_DEST=/backup/plantpal ./scripts/backup.sh >> /var/log/plantpal-backup.log 2>&1
```

Das Skript zieht einen **WAL-konsistenten** SQLite-Snapshot (sqlite-Backup-API, kein Lock-Risiko)
plus die Bilder. Optional `PLANTPAL_BACKUP_RSYNC=user@nas:/backups/plantpal` für off-site.

**Restore (geprobt am 2026-06-10: 63-MB-DB, integrity ok, alle Zeilen identisch):**

```bash
docker compose down
docker run --rm -v plantpal_plantpal-data:/data -v /backup/plantpal:/b alpine \
  sh -c "cp /b/plantpal-JJJJ-MM-TT.db /data/plantpal.db && rm -f /data/plantpal.db-wal /data/plantpal.db-shm && cp -r /b/images-JJJJ-MM-TT/. /data/images/"
docker compose up -d
```

**Off-site-Alternative Litestream** (kontinuierliche Replikation nach S3/B2):
`litestream.yml` + `.env` (`LITESTREAM_REPLICA_URL`) konfigurieren, dann
`docker compose --profile backup up -d`.

## 6. Monitoring & Pflege

- **Health:** `https://getplantpal.com/api/health` (Liveness; Details intern:
  `docker compose exec plantpal python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8000/api/health/detail').read().decode())"`).
- **Logs:** `docker compose logs -f plantpal` (strukturiert; keine sensiblen Daten).
- **Ressourcen:** `docker stats --no-stream` — plantpal ist auf 512 m/2 CPU gedeckelt,
  erwarteter Normalbetrieb < 200 MB. Die anderen Pi-Dienste bleiben unberührt.
- **Platz:** DB wächst langsam (Lasttest: 50 User × 2 Jahre ≈ 63 MB). `df -h` gelegentlich.
- Empfohlen: externer Uptime-Ping (z. B. UptimeRobot, kostenlos) auf `/api/health` —
  wichtig im App-Review-Fenster.

## 7. Troubleshooting

| Symptom | Diagnose / Fix |
|---|---|
| Seite nicht erreichbar | `docker compose ps` → cloudflared up? Tunnel-Status im Zero-Trust-Dashboard „Healthy"? Token in `.env` korrekt? |
| Health rot / Container restartet | `docker compose logs --tail 100 plantpal`; häufigste Ursache nach Update: Migration — Logs zeigen die fehlgeschlagene Datei. Rollback per §4. |
| Mails kommen nicht an | Resend-Dashboard → Logs. Übergangslösung: `docker compose exec plantpal python -m plantpal.cli issue-login-link --email user@mail.de` druckt Link + 6-stelligen Code (Code in der App unter „Code eingeben"). |
| „rate_limited" beim Testen | Gewollt (Brute-Force-Schutz). 1 h warten oder gezielt: `docker compose exec plantpal python -c "import sqlite3;c=sqlite3.connect('/data/plantpal.db');c.execute('DELETE FROM rate_limits');c.commit()"` |
| DB „locked" (extrem selten, WAL) | Kein zweiter Prozess auf der DB? Snapshots immer via `cli backup`, nie `cp` auf die laufende DB. |
| Speicher knapp | `docker system prune -f` (alte Build-Layer); Backups rotieren. |

## 8. Sicherheits-Notizen (Stand der Härtung)

- Kein Host-Port offen; TLS endet bei Cloudflare; Origin nur via Tunnel erreichbar.
- `TRUST_CF_CONNECTING_IP=true` ist im Tunnel-Setup korrekt (echte Client-IPs für
  Rate-Limits). Bei jedem anderen Setup auf `false`.
- Container läuft non-root (uid 10001), `/data` ist das einzige beschreibbare Volume.
- Session-Cookies HttpOnly+Secure+Lax; Tokens HMAC-gepeppert; Rate-Limits aktiv
  (Login 3/h pro Mail, Mutationen 30/m, Uploads 5/m).
