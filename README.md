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

## Deployment (Raspberry Pi / VPS via Docker)

**Voraussetzungen:** Docker + Docker Compose, eine öffentliche Domain auf den Host gerichtet (A/AAAA-Record), offene Ports **80** und **443** für Caddys Auto-HTTPS.

```bash
cp .env.example .env          # Secrets + BASE_URL=https://deine-domain setzen
export PLANTPAL_DOMAIN=deine-domain.example.com
docker compose up -d --build

# ersten Admin anlegen (CLI im laufenden Container):
docker compose exec plantpal python -m plantpal.cli bootstrap-admin --email du@beispiel.de
```

Caddy holt automatisch ein Let's-Encrypt-Zertifikat. Die App läuft mit **einem** Worker
(SQLite + Scheduler in einem Prozess). Migrationen laufen beim Start automatisch und idempotent.

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

`--send` versucht zusätzlich den Versand per Resend; der gedruckte Link funktioniert immer.

---

## Backup & Restore

Die SQLite-DB liegt auf dem Docker-Volume `plantpal-data` (`/data`).

**Variante A — Litestream (empfohlen, kontinuierlich):**

```bash
# .env: LITESTREAM_REPLICA_URL=s3://bucket/plantpal + S3-Credentials
docker compose --profile backup up -d         # startet den Litestream-Sidecar
# Restore:
docker compose run --rm litestream restore -o /data/plantpal.db "$LITESTREAM_REPLICA_URL"
```

**Variante B — manueller Snapshot:**

```bash
docker compose exec plantpal sh -c "sqlite3 /data/plantpal.db '.backup /data/backup.db'"
docker compose cp plantpal:/data/backup.db ./plantpal-backup-$(date +%F).db
```

> Eine SD-Karte im Pi stirbt irgendwann — richte Litestream (oder einen Cron-`rsync`) ein, bevor du echte Daten hast.

---

## Datenschutz (Privacy)

- **Selbst-gehostet:** Alle Daten (Pflanzen, Bilder, Accounts) liegen auf deinem Server.
- **Externe Dienste:** Nur **Resend** (Email-Versand). Magic-Link-Tokens stehen kurzzeitig in den Resend-Logs (single-use, 30 min). Schließe bei produktivem Einsatz einen AVV mit Resend ab.
- **Account-Löschung:** Über Settings → „Account löschen" werden User, Pflanzen, Sessions, Tokens und Bilder vollständig (hart) entfernt.
- **Optional Cloudflare-Tunnel** statt offener Ports: dann terminiert Cloudflare TLS und sieht den Klartext-Traffic — für Hobby-Nutzung i. d. R. akzeptabel.

---

## Roadmap

- **M1 (dieses Release):** CRUD, Magic-Link-Auth, Plantdex, Email-Digest, Settings, Stats, Docker-Deploy.
- **M2:** Instagram-Posting als alternativer Reminder-Channel (`users.reminder_channel` ist bereits vorbereitet).
- **M3+:** Watering-History/Streaks, Web-Push/PWA, Account-Email ändern, offene Registrierung.
