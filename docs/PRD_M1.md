# PlantPal — Product Requirements Document

**Status:** Draft v2 — nach Plan-Review (Claude × 4 + Codex gpt-5.5)
**Stand:** 2026-05-21
**Autor:** Marius Schwarzin (mariusschwarzin@gmail.com)
**Basis:** Grill-Session 2026-05-21 + Plan-Review 2026-05-21

Änderungen v1 → v2: Widersprüche aufgelöst (Latin Name, Avg Watering Interval, Soft-Delete-Bild, Bootstrap-Admin), CRITICAL-Risiken adressiert (Pillow-async, Resend-Lockout-Fallback, DST/Cron-Idempotenz), GAPs geschlossen (Test-Strategie, Indexe, Config-Zentralisierung, Upload-Härtung, CSRF, Forward-Compat M2).

---

## 1. Overview

### Problem
Zimmerpflanzen brauchen regelmäßiges Gießen — aber ohne ein zuverlässiges Erinnerungssystem werden Gießintervalle leicht vergessen, was zu vertrockneten oder überwässerten Pflanzen führt.

### Solution
**PlantPal** ist eine selbst-gehostete Web-App, die das eigene Pflanzen-Inventar als „Plantdex" (Pokédex-Analogie) verwaltet. Jede Pflanze hat ein Foto, einen Namen und ein Gieß-Intervall. Die App erkennt automatisch, welche Pflanzen Durst haben, hebt sie hervor und schickt einen täglichen Email-Digest. Multi-User, Invite-only.

---

## 2. Goals & Non-Goals

### Goals (MVP / M1)
1. Schnelles Anlegen einer Pflanze mit Foto + Gießintervall.
2. Visuelle Erkennung der durstigen Pflanzen (Plantdex + Thirsty-Section).
3. Ein-Klick-„Gegossen"-Aktion.
4. Täglicher Email-Reminder pro User, in Settings abschaltbar.
5. Mehrere User auf derselben Instanz, Invite-only.
6. Selbst-gehostet, datensouverän (Pi/NAS/VPS via Docker).
7. Robust gegen Pi-Reboot, DST-Wechsel, Resend-Ausfall.

### Non-Goals (MVP)
- Öffentliche Registrierung.
- Pflanzen-Wiki / Species-Datenbank.
- Wassersensoren / Hardware-Integration.
- Mehrere Bilder pro Pflanze.
- Gemeinschafts-Features (geteilte Pflanzen, Likes, Kommentare).
- Native Mobile-App.
- Web-Push-Notifications.
- Konfigurierbare Reminder-Uhrzeit per User.

### Explicit Future Scope
**M2 — Instagram-Posting:** PlantPal-Account postet täglich Foto der thirsty plants und taggt User. Forward-Compat-Hook in M1: `users.reminder_channel` Spalte mit Default `'email'`, Werte `email|instagram|both`. Kein anderer Code-Pfad in M1.

---

## 3. User Personas & Stories

### Persona
**Pflanzen-Marius**, 30, hat 14+ Zimmerpflanzen, hostet selbst auf einem Raspberry Pi, mag Retro-Pixel-Ästhetik, lädt evtl. Familie/Freunde ein.

### User Stories

| ID | Story |
|---|---|
| US-1 | Als neuer User möchte ich mich mit einem Invite-Token registrieren. |
| US-2 | Als User möchte ich mich per Magic Link einloggen, ohne Passwort. |
| US-3 | Als User möchte ich eine Pflanze mit Foto, Name, Gieß-Intervall (Tage) anlegen. |
| US-4 | Als User möchte ich beim Öffnen sofort alle Pflanzen sehen, mit Hervorhebung der durstigen. |
| US-5 | Als User möchte ich mit einem Klick markieren, dass eine Pflanze gegossen wurde. |
| US-6 | Als User möchte ich morgens eine Email mit den durstigen Pflanzen erhalten. |
| US-7 | Als User möchte ich in Settings den Email-Digest abschalten können. |
| US-8 | Als User möchte ich Bild, Name, Intervall, Notizen einer Pflanze ändern oder die Pflanze löschen können. |
| US-9 | Als User möchte ich Detailinfos einer Pflanze sehen (Foto, Notizen, Wassermenge, Last watered). |
| US-10 | Als User möchte ich eine simple Stats-Übersicht sehen (Anzahl Pflanzen, aktuell durstige). |
| US-11 | Als User möchte ich meinen Account vollständig löschen können (DSGVO). |
| US-12 | Als Admin möchte ich Invite-Tokens für andere generieren. |

---

## 4. Functional Requirements

### 4.1 Auth & Onboarding

| Req | Beschreibung |
|---|---|
| F-AUTH-1 | **Bootstrap-Admin:** Erster Admin wird via CLI angelegt: `docker compose exec plantpal python -m plantpal.cli bootstrap-admin --email <addr>`. Erzeugt User-Row mit `is_admin=1`, sendet sofort Magic-Link-Mail. Wenn CLI ausfällt: fallback `--print-token` druckt Token in stdout. |
| F-AUTH-2 | **Invite-Token-Generation:** Admin erstellt Token via Settings-Page ODER CLI (`create-invite --email-hint <addr>`). Token: 32-byte url-safe random, gespeichert in `invite_tokens`, default 14 Tage gültig (konfigurierbar). |
| F-AUTH-3 | **Registrierung:** `GET /register?token=<X>` → Form mit Email-Feld → `POST /auth/register` validiert Token (existiert? nicht used? nicht expired?) + erstellt User mit `is_admin=0` + markiert Invite-Token als used + triggert Magic-Link-Mail. Bei ungültigem Token: 410 Gone + generische Fehlermeldung. |
| F-AUTH-4 | **Magic-Link-Request:** `POST /auth/request-login { email }` generiert Token (`secrets.token_urlsafe(32)`), speichert in `login_tokens` mit 30 min Gültigkeit, schickt Mail. **Timing-konstante Antwort:** identische 200-Response unabhängig davon, ob die Email existiert, mit fester Mindest-Latenz, um Enumeration zu blockieren. |
| F-AUTH-5 | **Magic-Link-Verify:** `GET /auth/verify?token=<X>`. Atomic single-use via SQL: `UPDATE login_tokens SET used_at=? WHERE token=? AND used_at IS NULL AND expires_at > ?` und nur bei `cursor.rowcount==1` weiter (verhindert Double-Click-Race). Bei Erfolg: Session-Cookie + Redirect zu `/`. Bei Misserfolg: 410 Gone + Link zu Re-Login. |
| F-AUTH-6 | **Session-Cookie:** Name `plantpal_session`, httpOnly + Secure + SameSite=Lax + Path=/. **Soft-Cap:** 90 Tage Max-Age, Sliding-Renewal (jeder Request setzt Max-Age neu). **Hard-Cap:** 180 Tage absolute Lifetime ab `sessions.created_at`. Nach Hard-Cap: Session wird invalidiert, User muss neu Magic-Link anfordern. |
| F-AUTH-7 | **`last_seen_at`-Update debounced:** UPDATE nur, wenn mehr als 5 min seit letztem Update vergangen — verhindert UPDATE-pro-Request-Storm. |
| F-AUTH-8 | **Logout:** `POST /auth/logout` löscht Session-Row und entfernt Cookie (Set-Cookie mit Max-Age=0). |
| F-AUTH-9 | **User-Scope-Enforcement:** Alle Plant-Queries filtern auf `user_id = current_user.id`. Cross-User-IDs liefern 404 (nicht 403, um Existenz-Leak zu vermeiden). |
| F-AUTH-10 | **Multi-Device:** Jedes Device hat eigene Session-Row. Logout invalidiert nur die aktuelle Session. CLI-Befehl `revoke-sessions --user-email <addr>` ermöglicht Admin-Zwangs-Logout. |
| F-AUTH-11 | **Resend-Fallback CLI:** `python -m plantpal.cli issue-login-link --email <addr>` schreibt Token in DB + druckt fertige Login-URL in stdout. Damit kann sich der Admin notfalls auch ohne Resend einloggen. Im README dokumentiert. |
| F-AUTH-12 | **CSRF:** Cookie ist SameSite=Lax (deckt klassische CSRF-Angriffe ab). Zusätzlich: Origin/Referer-Header-Check bei allen mutating Requests (POST/PATCH/DELETE). Bei Fehlen oder Mismatch: 403. |

### 4.2 Plant CRUD

| Req | Beschreibung |
|---|---|
| F-PLANT-1 | **Felder:** `id INTEGER PK, user_id INTEGER FK, name TEXT (≤100 chars, req), interval_days INTEGER (1–365, req), image_path TEXT (req), last_watered_at TEXT, created_at TEXT, is_active INTEGER, notes TEXT (≤500 chars, opt), water_amount_ml INTEGER (1–5000, opt)`. **Kein** `latin_name` (Striche aus UI-Spec). |
| F-PLANT-2 | **Anlegen:** `POST /api/plants` (multipart): name, interval_days, image (file), notes?, water_amount_ml?. Setzt `last_watered_at = now_berlin()` (Annahme: User legt direkt nach Gießen an), `is_active = 1`. |
| F-PLANT-3 | **Edit:** `PATCH /api/plants/{id}`: name, interval_days, notes, water_amount_ml. Image-Edit über separaten Endpoint `POST /api/plants/{id}/image` (multipart). `last_watered_at` nicht über PATCH; nur via Watering-Action. |
| F-PLANT-4 | **Soft-Delete:** `DELETE /api/plants/{id}` setzt `is_active = 0`. Pflanze verschwindet aus UI, bleibt in DB + Bild bleibt auf Filesystem (für späteren Undo). Bei Account-Löschung (F-SET-5): Hard-Delete inkl. Bilder. |
| F-PLANT-5 | **Liste GET:** `GET /api/plants` liefert nur `is_active = 1`, sortiert: thirsty zuerst (`days_overdue DESC`), dann alphabetisch. Response enthält pro Plant: alle Felder + derived `is_thirsty` (bool) + `days_overdue` (int, ≥0). |
| F-PLANT-6 | **Validation:** Server-side via Pydantic. Bei Verletzung: 422 mit klarer Field-Error. |

### 4.3 Image Upload & Storage

| Req | Beschreibung |
|---|---|
| F-IMG-1 | **Upload:** multipart/form-data, akzeptierte Content-Types: `image/jpeg`, `image/png`, `image/webp`. Max 10 MB Upload-Größe (FastAPI-`UploadFile` mit `max_size`). |
| F-IMG-2 | **Magic-Bytes-Check:** Nach Empfang prüft `python-magic` (oder `filetype`-Lib) die ersten Bytes. Wenn Header nicht zu Content-Type passt → 415 + Reject. Schützt vor MIME-Spoofing/Polyglot. |
| F-IMG-3 | **Decompression-Bomb-Guard:** `Image.MAX_IMAGE_PIXELS = 25_000_000` (≈ 25 MP). Beim `Image.open()` werden Bilder darüber refused via `DecompressionBombError`. |
| F-IMG-4 | **Pipeline (async):** Resize läuft via `await asyncio.to_thread(_resize_sync, ...)` — blockiert nicht den Event-Loop. Steps: open → respect EXIF orientation (Pillow `ImageOps.exif_transpose`) → strip alle anderen EXIF-Daten → center-crop auf Quadrat → resize via `Image.LANCZOS` auf 96×96 → save als PNG. |
| F-IMG-5 | **Storage-Pfad:** `data/images/{user_id}/{plant_id}.png`. User-Verzeichnis wird bei Bedarf angelegt. Path-Traversal-Schutz: nur Integer-IDs werden in Pfad eingesetzt. |
| F-IMG-6 | **Edit / Re-Upload:** überschreibt gleiche Datei (atomic via tmp-file + rename). |
| F-IMG-7 | **Soft-Delete:** Bild bleibt erhalten (für Undo-Option). Erst bei Account-Löschung (F-SET-5) wird das gesamte `data/images/{user_id}/` rekursiv gelöscht. |
| F-IMG-8 | **Frontend-Display:** `<img>` mit `image-rendering: pixelated; image-rendering: crisp-edges;`. Serving via App-Route `GET /api/plants/{id}/image` mit Content-Type-Header `image/png` (nicht direkt aus statischem Verzeichnis, damit User-Scope erzwungen wird). |
| F-IMG-9 | **Failure-Modes:** Korruptes Bild → 422 + Cleanup tmp-Datei. Disk-Full → 507 + Logging. EXIF-Bug → fall through, kein Crash. |

### 4.4 Watering Action

| Req | Beschreibung |
|---|---|
| F-WATER-1 | `POST /api/plants/{id}/water` setzt `last_watered_at = now_berlin()`. Liefert 200 mit aktualisierter Plant. |
| F-WATER-2 | Kein Confirm-Dialog. Direkter Klick. |
| F-WATER-3 | Frontend: Optimistic Update + Rollback bei Fehler (Toast: „Konnte nicht speichern, erneut versuchen?"). |
| F-WATER-4 | Mehrfach-Gießen erlaubt, kein Lock. |

### 4.5 Thirsty Detection

| Req | Beschreibung |
|---|---|
| F-THIRST-1 | Server-side derived per GET-Request: `thirsty = (date(today_berlin) >= date(last_watered_at) + interval_days)`, Tages-Granularität. |
| F-THIRST-2 | `days_overdue = max(0, (today_berlin - (last_watered_at + interval_days)).days)`. |
| F-THIRST-3 | Kein gespeichertes `is_thirsty`-Feld. Immer derived. |
| F-THIRST-4 | UI: Wassertropfen-Icon rechts unten an Plant-Card UND Hervorhebung in „THIRSTY PLANTS!"-Section oben. |

### 4.6 Email Reminder

| Req | Beschreibung |
|---|---|
| F-MAIL-1 | Versand via Resend HTTP-API (`https://api.resend.com/emails`). ENV: `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, `RESEND_BASE_URL` (default offizielle). |
| F-MAIL-2 | **Daily Cron:** APScheduler mit `CronTrigger(hour=8, minute=0, timezone='Europe/Berlin')`. DST-safe per Lib. |
| F-MAIL-3 | **Idempotenz:** `users.reminder_last_sent_date` (DATE). Cron verschickt nur, wenn dieser Wert ≠ heute. Schützt vor doppeltem Versand bei DST und Container-Restart. |
| F-MAIL-4 | **Catch-up:** Beim App-Start prüft Cron, ob `reminder_last_sent_date < today_berlin AND now_berlin().hour >= 8` für irgendeinen User; wenn ja, einmal nachholen. Schützt vor Pi-Reboot-Lücke. |
| F-MAIL-5 | **Voraussetzungen pro User:** `email_reminders_enabled = 1` UND mind. 1 thirsty plant UND `reminder_last_sent_date < today`. Wenn alle drei wahr: Mail senden, dann `reminder_last_sent_date = today`. |
| F-MAIL-6 | **Rate-Limit gegen Resend:** sequentielle Sends mit `asyncio.sleep(0.2)` (5/sec); bei 100 Usern dauert ein Cron-Run ~20s. Bei `429` von Resend: exponentielle Backoff (max 3 Retries). |
| F-MAIL-7 | **Failure-Logging:** Jeder fehlgeschlagene Send wird mit `user_id`, error, retry_count geloggt. `reminder_last_sent_date` wird NICHT gesetzt → nächster Cron-Run versucht erneut. |
| F-MAIL-8 | **Mail-Inhalt:** Subject `🌱 [Anzahl] Pflanzen haben Durst`. Plaintext + HTML-Multipart. Pro Plant: Name, days_overdue, Link zur App. Inline-Bilder als CID-Attachments (Resend supports). |
| F-MAIL-9 | **Magic-Link-Mails:** Über denselben Resend-Account. Template: Pixel-Art-Header + Button mit Login-URL, Hinweis „Link gültig 30 min, single-use". |

### 4.7 Settings

| Req | Beschreibung |
|---|---|
| F-SET-1 | **Email-Toggle:** Checkbox „Email-Reminder erhalten". Persistiert `users.email_reminders_enabled`. |
| F-SET-2 | **Email anzeigen** (read-only im MVP). |
| F-SET-3 | **Logout-Button.** |
| F-SET-4 | **Admin-only — Invite-Generierung:** Form: Email-Hint (optional, nur Hilfsfeld). Button „Invite generieren" → Token-String + fertige Registrierungs-URL werden angezeigt + Copy-Button. |
| F-SET-5 | **Account löschen (DSGVO):** Button „Account vollständig löschen" mit Confirm-Modal. Bei Bestätigung: Hard-Delete aller User-Daten (plants, sessions, login/invite-tokens, images, user-row). Sofortiger Logout. |

### 4.8 Stats

| Req | Beschreibung |
|---|---|
| F-STAT-1 | Total Plants (active). |
| F-STAT-2 | Currently Thirsty Count. |
| F-STAT-3 | *(gestrichen v2)* |
| F-STAT-4 | Streaks, Verlauf etc. sind out-of-scope (kein History-Log). |

---

## 5. Non-Functional Requirements

| Req | Beschreibung |
|---|---|
| NFR-1 | **Performance:** Plantdex-Page lädt in <500ms bei 50 Plants. DB: WAL-Mode, `busy_timeout=5000`, Indexe (s. §8). |
| NFR-2 | **Datensouveränität:** Selbst-gehostet, externe Abhängigkeiten nur Resend (Mail) + optional Cloudflare-Tunnel (HTTPS). Privacy-Notice im README. |
| NFR-3 | **Backup:** Litestream-Sidecar in docker-compose als **Default** repliziert SQLite-DB nach S3-kompatiblem Storage (z.B. Cloudflare R2 — separate Credentials). Optional abschaltbar via env-Flag. README dokumentiert Restore-Drill. |
| NFR-4 | **HTTPS:** Pflicht für Production. Caddy als Reverse-Proxy mit Auto-HTTPS (Let's Encrypt). Vorbedingung im README: Public-DNS-Name, offene Ports 80 + 443. |
| NFR-5 | **Browser-Support:** Aktuelle Chrome, Firefox, Safari (≥17 für `image-rendering: pixelated`-Konsistenz). Mobile (Chrome Android, Safari iOS) muss funktionieren. |
| NFR-6 | **Sicherheit:** Cookies httpOnly + Secure + SameSite=Lax. CSRF: SameSite + Origin/Referer-Check + signed double-submit-Cookie (HMAC bindet an Session-ID). Login-Tokens single-use + 30 min, **DB-seitig als `token_hash`** gespeichert (HMAC-SHA256 mit `TOKEN_PEPPER`); Cookies enthalten den plaintext-Random-Token. Session-Tokens analog gehasht. Session Soft-Cap 90 d / Hard-Cap 180 d. Keine Passwörter in DB. Parametrisierte SQL only (CI-grep gegen f-strings in SQL). |
| NFR-7 | **Rate-Limiting (via `slowapi`):** `POST /auth/request-login`: 3 / Email-Adresse / Stunde + 10 / IP / Stunde. Login-Verify: 10 / IP / min. Plant-Mutations: 30 / User / min. Image-Upload: 5 / User / min. Bei Limit-Hit: 429 + `Retry-After`-Header. |
| NFR-8 | **Logging:** Strukturierte Logs via `structlog`. Keine Secrets/PII (Email-Adressen → hash für Logs). Log-Level via ENV. |
| NFR-9 | **Healthcheck:** `GET /api/health` liefert 200 + JSON `{status, db_ok, scheduler_running}`. Wird von Docker-`HEALTHCHECK` und externem Monitoring genutzt. |
| NFR-10 | **DSGVO:** Privacy-Notice + Resend-AVV im README. Account-Hard-Delete (F-SET-5). Magic-Link-Tokens sind in Resend-Logs sichtbar; das ist akzeptabel weil single-use + 30 min. |

---

## 6. UI / UX

### Design-Reference
Pixel-Art-Pokédex-Stil mit dunklen Grüntönen und Goldakzenten. Referenzbild: `images/design-reference.jpeg`.

### Wichtige UI-Elemente
- **Top-Frame „THIRSTY PLANTS!"** mit Karten-Liste durstiger Pflanzen + „WATER"-Button pro Karte.
- **„MY PLANTDEX (N)"** Grid (3 Spalten Desktop, 2 Tablet, 1 Mobile).
- **Plant-Card:** Foto links, Name + „WATER: N DAYS" rechts. Wassertropfen-Icon rechts unten wenn thirsty.
- **Header rechts:** STATS, SETTINGS, ADD PLANT.
- **Pixel-Font** „Press Start 2P" (Google Fonts; offline-fallback `VT323`).
- **Farbpalette:** Dunkel-Grün (#1a3d2e bis #2d5f4a), Goldgelb (#d4af37), Beige.

### Add-Plant-Modal
Felder: Foto-Upload (Pflicht, Preview, 96×96-Preview client-side), Name, Intervall (default 7), Notizen (opt), Wassermenge (opt). Submit + Cancel.

### Plant-Detail-Modal
Großes Foto, Name, Intervall, Last watered, Notizen, Wassermenge. Edit + Delete-Buttons.
*(„Latin Name" — gestrichen v2.)*

### UI-States explizit definiert
- **Loading:** Skeleton-Cards für Plantdex.
- **Empty Plantdex:** Illustration + Hint „Klicke ADD PLANT, um deine erste Pflanze einzutragen".
- **Empty Thirsty:** „🌿 Alles gewässert!".
- **Error (API-Fail):** Toast + Retry-Button.
- **Offline:** Banner „Verbindung verloren, Aktionen lokal gespeichert" *(MVP: nur Banner, kein echtes Offline-Queueing)*.

---

## 7. Tech Stack

> **Implementierungs-Referenz:** [`docs/BACKEND_ARCHITECTURE.md`](docs/BACKEND_ARCHITECTURE.md) enthält die ausgearbeitete Architektur (Codex gpt-5.5) — exakte Modul-Tree, Endpoint-Specs, Magic-Link-Sequenz, Session-Mechanik, CSRF-Implementation, Rate-Limit-Algorithmus, Image-Pipeline und Cron-Logik. Spec-Wahrheit bleibt das PRD; das Dokument liefert das WIE.

### Backend (`pyproject.toml`)
- Python 3.12
- FastAPI
- aiosqlite — raw parametrisierte SQL
- Pydantic v2 (Models + Settings)
- Pillow + `filetype` (oder `python-magic`) — Bild-Pipeline mit Magic-Bytes-Check
- `resend` Python SDK — Email-Versand
- APScheduler (AsyncIOScheduler) mit Timezone `Europe/Berlin` — Cron-Job
- **SQLite-backed Rate-Limit** (`rate_limits` Tabelle) statt `slowapi`-in-memory (Pi-Restart-safe)
- `structlog` — Logging
- uv — Dependency-Management

### Frontend (`frontend/package.json`)
- Vite + React 18 + TypeScript 5
- Tailwind CSS v4 + Custom Pixel-CSS-Layer
- React Router
- Tanstack Query (API-Client)
- React-Hook-Form (Add-Plant-Form)
- sonner (Toasts)

### Infra
- Docker (multi-stage)
- docker-compose: `plantpal` + `caddy` + `litestream` (sidecar)
- Caddy — Reverse-Proxy + Auto-HTTPS
- SQLite-DB + Bilder auf persistentem Volume `/data`

### Tests
- **Backend:** pytest + pytest-asyncio + httpx (ASGI Transport). `pytest-asyncio mode=auto`. `conftest.py`: `db` (tmp_path), `client`.
- **Frontend:** Vitest (Unit) + Playwright (E2E gegen Backend mit tmp-DB).

---

## 8. Datenmodell (SQLite)

```sql
-- PRAGMAs beim DB-Connect:
-- PRAGMA journal_mode = WAL;
-- PRAGMA foreign_keys = ON;
-- PRAGMA busy_timeout = 5000;

CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  is_admin INTEGER NOT NULL DEFAULT 0,
  email_reminders_enabled INTEGER NOT NULL DEFAULT 1,
  reminder_channel TEXT NOT NULL DEFAULT 'email',  -- M2-forward-compat
  reminder_last_sent_date TEXT,                     -- ISO DATE, idempotency
  created_at TEXT NOT NULL
);

CREATE TABLE invite_tokens (
  token TEXT PRIMARY KEY,
  created_by_user_id INTEGER NOT NULL,
  email_hint TEXT,
  used_at TEXT,
  expires_at TEXT NOT NULL,
  FOREIGN KEY(created_by_user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX idx_invite_expires ON invite_tokens(expires_at) WHERE used_at IS NULL;

CREATE TABLE login_tokens (
  token TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  used_at TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_login_email_expires ON login_tokens(email, expires_at) WHERE used_at IS NULL;

CREATE TABLE sessions (
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,        -- sliding (Soft-Cap 90d)
  hard_expires_at TEXT NOT NULL,   -- absolute (Hard-Cap 180d)
  last_seen_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);

CREATE TABLE plants (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  interval_days INTEGER NOT NULL CHECK (interval_days BETWEEN 1 AND 365),
  image_path TEXT NOT NULL,
  last_watered_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 1,
  notes TEXT,
  water_amount_ml INTEGER CHECK (water_amount_ml BETWEEN 1 AND 5000),
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX idx_plants_user_active ON plants(user_id) WHERE is_active = 1;

CREATE TABLE _migrations (
  filename TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL
);
```

**Konventionen:**
- Alle Datetimes: naive Berlin (`Europe/Berlin`), ISO-8601 ohne TZ-Suffix.
- Soft-Delete: `is_active=0` (außer User-Hard-Delete via F-SET-5).
- Numbered Migrations: `migrations/001_users.sql`, ..., tracked in `_migrations`.
- WAL-Mode bei jedem Connect gesetzt.

---

## 9. Konfiguration (Pydantic Settings → `config.yaml` + ENV)

Alle „magic numbers" zentral in `src/plantpal/config.py`:

```python
class Settings(BaseSettings):
    # Auth
    SESSION_SOFT_CAP_DAYS: int = 90
    SESSION_HARD_CAP_DAYS: int = 180
    SESSION_LAST_SEEN_DEBOUNCE_MIN: int = 5
    LOGIN_TOKEN_TTL_MIN: int = 30
    INVITE_TOKEN_TTL_DAYS: int = 14

    # Images
    IMG_SIZE_PX: int = 96
    IMG_MAX_UPLOAD_MB: int = 10
    IMG_MAX_PIXELS: int = 25_000_000

    # Reminders
    REMINDER_HOUR_BERLIN: int = 8
    RESEND_RATE_PER_SEC: int = 5
    RESEND_MAX_RETRIES: int = 3

    # Rate-Limits (slowapi-Strings)
    RL_LOGIN_REQUEST: str = "3/hour"        # pro Email
    RL_LOGIN_VERIFY: str = "10/minute"      # pro IP
    RL_PLANT_MUTATION: str = "30/minute"    # pro User
    RL_IMAGE_UPLOAD: str = "5/minute"       # pro User

    # External
    RESEND_API_KEY: str
    RESEND_FROM_EMAIL: str
    BASE_URL: str   # z.B. https://plantpal.example.com
    DB_PATH: str = "data/plantpal.db"
    IMAGE_DIR: str = "data/images"

    # Litestream
    LITESTREAM_ENABLED: bool = True
    LITESTREAM_REPLICA_URL: str | None = None  # z.B. s3://bucket/plantpal

    class Config:
        env_file = ".env"
```

---

## 10. Milestones

### M1 — MVP (dieses Dokument)
- Auth (Magic Link, Invite-Token, Sessions, CLI-Bootstrap + Fallback).
- Plant CRUD + Image Upload mit Härtung.
- Plantdex + Thirsty Section UI.
- Daily Email Digest (Resend, DST-safe, idempotent, catch-up).
- Settings (Email-Toggle, Logout, Admin-Invite, Account-Löschen).
- Stats (Total + Thirsty).
- Docker-Compose Deployment auf Pi (+ Caddy + Litestream).
- Test-Suite (Backend Unit + Integration, Frontend Vitest + Playwright).

**Akzeptanz M1:** Akzeptanzkriterien §11 alle grün.

### M2 — Instagram-Integration
- PlantPal IG-Business-Account + FB-Page-Verknüpfung.
- Daily Job nutzt `users.reminder_channel` für Routing (`email | instagram | both`).
- Methode (Graph API empfohlen) zur M2-Zeit final entscheiden.
- Settings-Erweiterung: User wählt Channel.

### M3+ Backlog (nicht commited)
- Watering-History-Tabelle (Streaks, Avg Interval).
- Web-Push / PWA.
- Mobile-Layout-Politur.
- Account-Email ändern.
- Open Registration mit Email-Verification.
- Multilingual.

---

## 11. Akzeptanzkriterien (M1)

Jede Akzeptanz hat eine Test-ID, die im Backend- oder E2E-Test verifiziert wird.

| ID | Szenario | Test-Datei |
|---|---|---|
| AK-1 | **Bootstrap-Admin via CLI:** CLI erstellt Admin-User, Magic-Link kommt an, Klick → eingeloggt. | `tests/test_cli_bootstrap.py` |
| AK-2 | **Invite-Registrierung:** Admin generiert Invite → User öffnet `/register?token=X` → gibt Email ein → Magic-Link → eingeloggt → leerer Plantdex. | `tests/e2e/test_registration.spec.ts` |
| AK-3 | **Magic-Link abgelaufen:** Token 31 min alt → Klick → 410 Gone + Link zu Re-Login. | `tests/test_auth_service.py::test_verify_expired` |
| AK-4 | **Magic-Link double-click race:** Zwei parallele Verify-Requests mit demselben Token → exakt einer wird Session, der andere bekommt 410. | `tests/test_auth_service.py::test_verify_race` |
| AK-5 | **Plant anlegen mit Foto:** Foto-Upload (gültiges JPG, EXIF-rotated) → resized auf 96×96 PNG → sichtbar. | `tests/test_image_service.py::test_upload_pipeline` |
| AK-6 | **Upload-Härtung:** Polyglot-Datei (HTML mit JPG-Endung) → 415. Decompression-Bomb → 415. 11 MB JPG → 413. | `tests/test_image_service.py::test_hardening` |
| AK-7 | **Plant wässern:** Plant in Thirsty-Frame → Klick „WATER" → verschwindet aus Thirsty + bleibt im Plantdex ohne Wassertropfen. | `tests/e2e/test_water.spec.ts` |
| AK-8 | **Email-Reminder:** Plant interval=1, angelegt Tag X, am Tag X+1 um 08:00 → Mail kommt mit dieser Plant. | `tests/test_reminder_cron.py::test_daily_send` |
| AK-9 | **Idempotenz / DST Spring-Forward:** Cron-Lauf am 29.3. springt von 02:00 auf 03:00 (DST) → keine doppelte Mail. | `tests/test_reminder_cron.py::test_dst_spring` |
| AK-10 | **Idempotenz / DST Fall-Back:** Cron-Lauf am 26.10. 03:00 wiederholt 02:00 → keine doppelte Mail. | `tests/test_reminder_cron.py::test_dst_fall` |
| AK-11 | **Catch-up nach Reboot:** Container down von 07:30 bis 09:00 → beim Start prüft Scheduler, sendet ausstehende Reminders. | `tests/test_reminder_cron.py::test_catchup` |
| AK-12 | **Resend-Failure-Retry:** Mock 429 → exponential Backoff → spätestens 3. Versuch erfolgreich → `reminder_last_sent_date` gesetzt. | `tests/test_reminder_cron.py::test_resend_retry` |
| AK-13 | **Email-Toggle off:** Settings → off → kein Mail-Versand am nächsten Tag. | `tests/test_reminder_cron.py::test_toggle_off` |
| AK-14 | **Logout:** Klick → Cookie weg + Session-Row weg → erneuter Aufruf von `/api/me` → 401. | `tests/test_auth_service.py::test_logout` |
| AK-15 | **Multi-User-Isolation:** User A's Plant-ID → User B's GET → 404 (nicht 403). | `tests/test_plant_service.py::test_user_scope` |
| AK-16 | **Session-Sliding-Renewal:** Login Tag X → Request Tag X+60 → Cookie-Max-Age + DB-expires_at frisch verlängert. | `tests/test_auth_service.py::test_sliding` |
| AK-17 | **Session-Hard-Cap:** Login Tag X → Request Tag X+181 → 401, Session invalidiert. | `tests/test_auth_service.py::test_hard_cap` |
| AK-18 | **Rate-Limit-Login:** 4. Magic-Link-Request für gleiche Email in 1h → 429 + Retry-After. | `tests/test_auth_service.py::test_rate_limit` |
| AK-19 | **Account-Hard-Delete:** Settings → Confirm → User-Row + alle Plants + alle Sessions + alle Bilder weg, sofortiger Logout. | `tests/test_account_delete.py` |
| AK-20 | **Resend-Fallback CLI:** Mit deaktivierter Resend-Anbindung → CLI `issue-login-link` druckt URL, manueller Aufruf loggt User ein. | `tests/test_cli_fallback.py` |
| AK-21 | **CSRF:** POST /api/plants mit anderem Origin → 403. | `tests/test_csrf.py` |
| AK-22 | **Healthcheck:** GET /api/health → 200 + db_ok=true + scheduler_running=true. | `tests/test_health.py` |

---

## 12. Out-of-Scope (M1)

- Watering-History-Tabelle.
- Avg Watering Interval / komplexere Stats.
- Latin Name / Species-Feld.
- Web-Push / PWA.
- Instagram-Posting (→ M2).
- Geteilte Pflanzen.
- Native Mobile-App.
- Public Registration.
- Multiple Bilder pro Pflanze.
- Konfigurierbare Reminder-Uhrzeit per User.
- Password-Login, Google OAuth.
- Multilingual.

---

## 13. Failure-Mode-Catalog (Top 10)

| # | Failure | Mitigation in M1 |
|---|---|---|
| 1 | **Resend-Outage / API-Key revoked** | CLI-Fallback `issue-login-link`, Magic-Link manuell aushändigen. Cron failed gracefully, retried am nächsten Tag. |
| 2 | **Pi-Reboot zwischen 07:30–08:30** | Catch-up-Logik (F-MAIL-4): nach Start prüft Scheduler `reminder_last_sent_date` und sendet nachträglich. |
| 3 | **DST-Wechsel** | APScheduler mit `timezone='Europe/Berlin'` (DST-aware) + Idempotenz-Spalte. |
| 4 | **Disk voll** | Image-Upload liefert 507; Healthcheck flaggt; Litestream-Backup ggf. ebenfalls 507 → externes Monitoring sieht es. |
| 5 | **Malicious Upload (Polyglot/Decompression-Bomb)** | Magic-Bytes + `MAX_IMAGE_PIXELS` (F-IMG-2/3). |
| 6 | **SQLite-Lock unter Last** | WAL + busy_timeout=5000 + Connection-Pool. Cron läuft asynchron, blockiert nicht. |
| 7 | **Magic-Link-Token-Race (Double-Click)** | Atomic UPDATE mit rowcount-Check (F-AUTH-5). |
| 8 | **Cookie-Diebstahl** | Hard-Cap 180d limitiert maximalen Schaden; Admin kann `revoke-sessions` via CLI. |
| 9 | **DB-Korruption** | Litestream-Sidecar (NFR-3); README dokumentiert Restore. |
| 10 | **Email-Enumeration durch Latenz-Side-Channel** | Timing-konstante Response in `/auth/request-login` (F-AUTH-4). |

---

## 14. Offene Punkte (zur Klärung WÄHREND Implementation)

| Punkt | Default | Korrigierbar bis |
|---|---|---|
| Pixel-Font: Press Start 2P vs. VT323 | Press Start 2P (mehr pixelig), VT323 als Fallback | Vor Frontend-Build |
| Litestream-Replica-Ziel: R2 vs. lokales 2. Volume | R2 (cloud-side robust) | Vor Production-Deploy |
| Caddy vs. Cloudflare-Tunnel | Caddy lokal mit Let's Encrypt | Vor Production-Deploy |
| `python-magic` vs. `filetype` für Magic-Bytes | `filetype` (pure-python, kein libmagic-Sysdep) | Während Backend-Build |
| Frontend Routing-Lib | React Router v6 | Während Frontend-Build |

---

## Sign-off

Dokument bereit zur User-Freigabe (v2). Nach Freigabe startet Implementation gemäß Task-Liste 4–12. Codex-Backend-Detail-Output wird zusätzlich beim Backend-Build als Architektur-Referenz herangezogen.
