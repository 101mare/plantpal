# 🌱 PlantPal

Ein selbst-gehosteter, Pokédex-artiger Gieß-Erinnerungs-Tracker für deine Zimmerpflanzen.
Multi-User (invite-only), Magic-Link-Login, täglicher Email-Reminder, Pixel-Art-UI.

- **Backend:** Python 3.12 · FastAPI · aiosqlite · APScheduler · Resend
- **Frontend:** Vite · React · TypeScript · Tailwind v4
- **Deployment:** Docker Compose (App + Caddy + optional Litestream) auf Raspberry Pi / NAS / VPS

Spezifikation: [`PRD.md`](PRD.md) · Backend-Architektur: [`docs/BACKEND_ARCHITECTURE.md`](docs/BACKEND_ARCHITECTURE.md)

---

## Schnellstart (lokale Entwicklung)

```bash
# Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # Secrets eintragen (siehe unten)
uvicorn plantpal.main:create_app --factory --reload   # http://localhost:8000

# Frontend (zweites Terminal)
cd frontend && npm install && npm run dev             # http://localhost:5173 (proxyt /api → :8000)
```

Ersten Admin anlegen (siehe [CLI](#cli)):

```bash
python -m plantpal.cli bootstrap-admin --email du@beispiel.de
# druckt einen Login-Link in die Konsole — öffnen → eingeloggt
```

---

## Tests & Qualität

```bash
# Backend
pytest tests/                                  # alle Tests
pytest --cov=plantpal --cov-report=term tests/ # mit Coverage (Ziel ≥ 90 %)
ruff check src/ tests/ && ruff format --check src/ tests/

# Frontend
cd frontend && npm run test && npm run lint && npm run build
```

---

## Konfiguration (ENV)

Alle Werte in `.env` (siehe `.env.example`). Defaults in `src/plantpal/config.py`.

| Variable | Pflicht | Beschreibung |
|---|---|---|
| `BASE_URL` | ✅ | Öffentliche URL, z. B. `https://plantpal.example.com`. In Prod HTTPS-Pflicht. |
| `TOKEN_PEPPER` | ✅ | Zufälliger Key (≥32 Zeichen) zum Hashen von Tokens. `python -c "import secrets;print(secrets.token_urlsafe(48))"` |
| `CSRF_SECRET` | ✅ | Zufälliger Key (≥32 Zeichen) für CSRF-Signaturen. |
| `RESEND_API_KEY` | ✅ (Prod) | API-Key von [resend.com](https://resend.com) für Magic-Link- + Reminder-Mails. |
| `RESEND_FROM_EMAIL` | ✅ | Absender, z. B. `PlantPal <noreply@plantpal.example.com>`. |
| `PLANTPAL_DOMAIN` | Compose | Domain für Caddy/Auto-HTTPS (in `docker-compose.yml`). |
| `DB_PATH` | – | Default `data/plantpal.db` (Container: `/data/plantpal.db`). |
| `IMAGE_DIR` | – | Default `data/images`. |
| `REMINDER_HOUR_BERLIN` | – | Stunde des täglichen Digests (Default 8, Europe/Berlin). |
| `SESSION_SOFT_CAP_DAYS` / `SESSION_HARD_CAP_DAYS` | – | Session-Lebensdauer (Default 90 / 180). |
| `LITESTREAM_REPLICA_URL` | Backup | S3-kompatibles Ziel, z. B. `s3://bucket/plantpal`. |

---

## Deployment (Pi / Mini-PC via Docker + Cloudflare Tunnel)

**Idee (v3):** öffentlich erreichbar **ohne** Port-Forwarding im Heimrouter — Cloudflare Tunnel
terminiert TLS am Edge und reicht den Request intern an die App weiter.

**Voraussetzungen:** Docker + Docker Compose, eine Domain (`getplantpal.com`, idealerweise beim
**Cloudflare-Registrar** registriert) und ein Cloudflare-Account.

1. **Tunnel anlegen:** Cloudflare → Zero Trust → Networks → Tunnels → *Create*. Public Hostname
   `getplantpal.com` → Service `http://plantpal:8000`. Tunnel-Token kopieren.
2. **Mail-Domain verifizieren:** in [Resend](https://resend.com) `getplantpal.com` als
   Absender-Domain hinzufügen und SPF/DKIM/DMARC-Records in Cloudflare setzen (sonst Spam).
3. **Starten:**

```bash
cp .env.example .env   # Secrets + BASE_URL=https://getplantpal.com + CLOUDFLARE_TUNNEL_TOKEN setzen
docker compose up -d --build   # startet plantpal + cloudflared

# ersten Admin anlegen (Login-Link + Code werden in die Konsole gedruckt):
docker compose exec plantpal python -m plantpal.cli bootstrap-admin --email du@beispiel.de
```

Die App läuft mit **einem** Worker (SQLite + Scheduler in einem Prozess; WAL + `busy_timeout`
reicht für 100–1000 Nutzer). Migrationen laufen beim Start automatisch und idempotent.

**Monitoring:** kostenlosen [UptimeRobot](https://uptimerobot.com)-Monitor auf
`https://getplantpal.com/api/health` setzen (alarmiert bei Down / DB-Fehler / totem Scheduler).

> **Alternative ohne Cloudflare:** Auf einem VPS mit offenen Ports 80/443 kann statt `cloudflared`
> der beiliegende `Caddyfile` (Auto-HTTPS via Let's Encrypt) genutzt werden.

---

## CLI

Alle administrativen Schreibzugriffe laufen über die CLI (kein Roh-SQL in der Shell):

```bash
docker compose exec plantpal python -m plantpal.cli <command>
```

| Command | Zweck |
|---|---|
| `bootstrap-admin --email <addr> [--force] [--send]` | Ersten Admin anlegen/befördern. Druckt Login-Link. |
| `issue-login-link --email <addr> [--send]` | **Resend-Ausfall-Fallback:** Login-Link manuell ausstellen. |
| `create-invite --created-by <admin-addr> [--email-hint <addr>] [--send]` | Invite-Token generieren. |
| `revoke-sessions --email <addr>` | Alle Sessions eines Users zwangsweise beenden. |
| `set-invite-quota --email <addr> --quota <n>` | Einlade-Kontingent eines Users setzen (v3). |
| `backup --out <pfad>` | Konsistenten SQLite-Snapshot schreiben (v3, kein sqlite3-CLI nötig). |

`--send` versucht zusätzlich den Versand per Resend; der gedruckte Link funktioniert immer.

---

## Backup & Restore

Die SQLite-DB liegt auf dem Docker-Volume `plantpal-data` (`/data`).

**Variante A — Cron-Snapshot + rsync (v3-Default):** `scripts/backup.sh` macht einen
WAL-konsistenten Snapshot (via `cli backup`, kein sqlite3-CLI im Image nötig) und kopiert DB
**und** Bilder heraus. In die Host-Crontab eintragen:

```bash
30 3 * * *  PLANTPAL_BACKUP_DEST=/backup/plantpal /opt/plantpal/scripts/backup.sh
```

**Variante B — Litestream (kontinuierlich, optional):**

```bash
# .env: LITESTREAM_REPLICA_URL=s3://bucket/plantpal + S3-Credentials
docker compose --profile backup up -d
docker compose run --rm litestream restore -o /data/plantpal.db "$LITESTREAM_REPLICA_URL"
```

> Eine SD-Karte im Pi stirbt irgendwann — richte Litestream (oder einen Cron-`rsync`) ein, bevor du echte Daten hast.

---

## Datenschutz (Privacy)

- **Selbst-gehostet:** Alle Daten (Pflanzen, Bilder, Accounts) liegen auf deinem Server.
- **Externe Dienste:** Nur **Resend** (Email-Versand). Magic-Link-Tokens stehen kurzzeitig in den Resend-Logs (single-use, 30 min). Schließe bei produktivem Einsatz einen AVV mit Resend ab.
- **Account-Löschung:** Über Settings → „Account löschen" werden User, Pflanzen, Sessions, Tokens und Bilder vollständig (hart) entfernt.
- **Optional Cloudflare-Tunnel** statt offener Ports: dann terminiert Cloudflare TLS und sieht den Klartext-Traffic — für Hobby-Nutzung i. d. R. akzeptabel.

---

## Spross-Evolution (v2)

Das Maskottchen **Spross** wächst durch 6 Stufen, abgeleitet aus deiner eigenen Pflege-Historie
(keine neuen Daten — nur `GET /api/stats` + Pflanzen-Alter). **Monoton:** die Stufe ist Identität
und klettert nur; ein Pflege-Lapsus ändert nur die *Stimmung* (durstig/welkend), nie die Stufe.
Server-durabel via High-Water-Mark (`users.vitality_stage_max`, `max()`-only) → kein Downgrade bei
Storage-Verlust / neuem Gerät / Private-Mode.

**Vitalität (0–100):**

```
vitalität   = round(100 × careQuality × tenure)
careQuality = 0.7·(consistency% / 100) + 0.3·min(streak / 30, 1)     # Konsistenz zuverlässig
            = min(streak / 30, 1)                                     # falls alle Intervalle > 30 T (Konsistenz = bogus 100)
tenure      = 0.2 + 0.8·min(ältestes_Pflanzenalter_Tage / 120, 1)     # 0.2 … 1.0
```

`careQuality × tenure` ist **multiplikativ**: Pflege schlägt Sammeln (Horten ohne Konsistenz bleibt
niedrig) und Wachstum ist über Zeit verdient (ein Tag-0-Perfektionist bleibt Stufe 1).

**Schwellen** (`STAGE_THRESHOLDS = [0, 15, 30, 48, 65, 83]`):

| Vitalität | Stufe |
| --------- | ----- |
| 0–14      | 1 · Keimling |
| 15–29     | 2 · Sprossling |
| 30–47     | 3 · Blattgeist |
| 48–64     | 4 · Rankenweiser |
| 65–82     | 5 · Blütenwächter |
| 83–100    | 6 · Urgeist |

**Beispiel-Verlauf** (Konsistenz %, Streak, ältestes Alter → Vitalität → Stufe):

| Situation | Vitalität | Stufe |
| --------- | --------- | ----- |
| neu, 1 Pflanze, Tag 0 (25, 0, 0)            | 4  | 1 · Keimling |
| reine Kakteen-Sammlung, Tag 0 (bogus 100, 0) | 0  | 1 · Keimling *(Bogus-100-Falle entschärft)* |
| ~Tag 10, gute Pflege (70, 10, 10)           | 16 | 2 · Sprossling |
| ~Tag 30 (85, 30, 30)                        | 36 | 3 · Blattgeist |
| ~Tag 90 (90, 30, 90)                        | 74 | 5 · Blütenwächter |
| ~Tag 120, exzellent (95, 30+, 120)          | 96 | 6 · Urgeist |

→ ermutigend früh (Stufe 2 in ~10 Tagen), Prestige (Urgeist) erst nach ~4 Monaten exzellenter Pflege.

**Quelle der Wahrheit** (alle Konstanten tunebar): [`frontend/src/status.ts`](frontend/src/status.ts)
(`vitalityScore`, `stageFromVitality`, `STAGE_THRESHOLDS`); verifiziert in `status.test.ts`.
Die Schwellen/Trajektorie sind kalibrierbar — Werte auf echten Accounts gegenprüfen.

---

## Roadmap

- **M1 (dieses Release):** CRUD, Magic-Link-Auth, Plantdex, Email-Digest, Settings, Stats, Docker-Deploy.
- **M2:** Instagram-Posting als alternativer Reminder-Channel (`users.reminder_channel` ist bereits vorbereitet).
- **M3+:** Watering-History/Streaks, Web-Push/PWA, Account-Email ändern, offene Registrierung.
