# Backend-Architektur-Referenz

**Quelle:** Codex (OpenAI gpt-5.5, xhigh reasoning), 2026-05-21
**Status:** Implementierungs-Referenz für Backend + Auth. Spec-Wahrheit bleibt das [PRD](../PRD.md) — dieses Dokument ergänzt um Implementierungs-Details und Code-Konventionen.

---

## Hinweis: Abweichungen vom M1-Scope

Codex hat einige Strukturen vorgeschlagen, die **über den M1-Scope hinaus** gehen. Diese werden in M1 NICHT umgesetzt; im Architektur-Text bleiben sie als Referenz für spätere Milestones erhalten:

| Element | Codex schlägt vor | M1-Entscheidung | Begründung |
|---|---|---|---|
| `plant_events` Tabelle | Verlauf aller Plant-Aktionen | **OUT M1** | PRD §4.8: kein History-Log. Tabelle erst in M3. |
| `plants.species`, `plants.location` | Zusätzliche Plant-Felder | **OUT M1** | Latin Name in Grill-Session explizit gestrichen. |
| `users.display_name` | Anzeigename | **OUT M1** | PRD nutzt nur `email`. Kann später nachgezogen werden. |
| `users.reminder_hour_berlin` per-User | Individueller Reminder-Zeitpunkt | **OUT M1** | PRD §11 Out-of-Scope: einheitlich 08:00. |
| `repositories/`-Layer | Ports/Adapter-Trennung | **OUT M1** | PRD Memory-Konvention: flache `src/plantpal/` Struktur. Services nutzen `aiosqlite.Connection` direkt. |
| `api/`-Unterordner-Router-Split | Pro Domain ein Router | **OUT M1** | PRD: Routes direkt in `main.py`. Erst bei >8 Endpoints splitten. |
| `app_kv` Tabelle | Generic KV-Store | **OUT M1** | Keinen klaren Use-Case in M1. |
| Admin `disable_user` Endpoint | Soft-Disable | **OUT M1** | PRD M1 hat nur `revoke-sessions` via CLI. |
| `--reactivate`, `--force` Flags am CLI | Edge-Case-Flags | **Optional in M1** | Bootstrap-CLI minimal halten. |

## Hinweis: Sicherheits-Improvements, die ins M1-PRD übernommen werden

Codex schlägt einige Härtungen vor, die das PRD noch nicht hatte. Diese werden **in M1 mit umgesetzt** (PRD §4.1 / §8 wurde entsprechend aktualisiert):

| Improvement | Codex-Vorschlag | M1-Übernahme |
|---|---|---|
| **Token-Hashing in DB** | `magic_tokens.token_hash`, `sessions.session_hash` statt plaintext | ✓ JA. Wenn DB leakt, sind Tokens nicht direkt nutzbar. |
| **`reminder_send_log` Tabelle** | Sende-Protokoll mit UNIQUE-Constraint | ✓ JA. Stärkere Idempotenz-Garantie als nur `users.reminder_last_sent_date`. |
| **`rate_limits` Tabelle, SQLite-backed** | Custom SQLite-Limiter statt slowapi-in-memory | ✓ JA. Pi-Restart erhält den Counter. Slowapi nur als Fallback. |
| **Signed double-submit CSRF** | HMAC-Token bindet an Session-ID | ✓ JA. Ergänzt Origin/Referer-Check. |
| **`BEGIN IMMEDIATE` + atomic UPDATE** | Token-Consume race-safe | ✓ JA (war bereits im PRD F-AUTH-5). |
| **`Image.verify()` Pre-Pass** | Pre-Check vor eigentlichem Processing | ✓ JA in F-IMG-Pipeline. |
| **Atomic Image-Write** | tmp-File + rename | ✓ JA in F-IMG-6. |

---

## Codex-Output (verbatim, English)

> Below is the original Codex output. M1-Scope-Filter bitte mittels obiger Tabellen anwenden. Code-Patterns, Reihenfolge der SQL-Operationen und Sicherheits-Argumentation sind 1:1 als Implementierungs-Vorlage nutzbar.

---

## 1. Backend Module Tree

Assume package root: `backend/src/plantpal/`.

```text
plantpal/
  __init__.py
  main.py
  config.py
  db.py
  schema.sql
  models.py
  errors.py
  security.py
  rate_limit.py
  spa.py
  cli.py

  api/
    __init__.py
    deps.py
    auth.py
    plants.py
    settings.py
    admin.py

  services/
    __init__.py
    auth_service.py
    plant_service.py
    image_service.py
    email_service.py
    reminder_service.py
    invite_service.py
    user_service.py

  repositories/
    __init__.py
    users_repo.py
    sessions_repo.py
    tokens_repo.py
    invites_repo.py
    plants_repo.py
    images_repo.py
    reminder_repo.py
    rate_limit_repo.py

  jobs/
    __init__.py
    scheduler.py

  utils/
    __init__.py
    time.py
    tokens.py
    paths.py
    logging.py

  tests/
    ...
```

> **M1-Override:** Wir starten flach (`src/plantpal/` mit ~10 Files), KEIN `api/`-Subpackage, KEIN `repositories/`-Layer. Services greifen direkt auf `aiosqlite.Connection` zu. Routes liegen in `main.py`. Erst wenn >8 Endpoints im selben File werden, Domain-Split.

### `config.py`

Centralized runtime configuration via Pydantic Settings.

```python
APP_ENV
APP_BASE_URL
DATABASE_PATH
STORAGE_DIR
SECRET_KEY
TOKEN_PEPPER
CSRF_SECRET

SESSION_DAYS = 90
SESSION_HARD_CAP_DAYS = 180
SESSION_RENEW_IF_OLDER_THAN_HOURS = 24
SESSION_LAST_SEEN_DEBOUNCE_MIN = 10

LOGIN_TOKEN_TTL_MIN = 30
INVITE_TOKEN_TTL_DAYS = 14

REMINDER_HOUR_BERLIN = 8
REMINDER_TIMEZONE = "Europe/Berlin"
RESEND_API_KEY
RESEND_FROM_EMAIL
RESEND_RATE_PER_SEC = 5

IMG_SIZE = 96
MAX_UPLOAD_MB = 10
MAX_IMAGE_PIXELS = 20_000_000
ALLOWED_IMAGE_MIME_TYPES = ["image/jpeg", "image/png", "image/webp"]

AUTH_LOGIN_EMAIL_PER_HOUR = 3
AUTH_LOGIN_IP_PER_HOUR = 10
AUTH_VERIFY_IP_PER_MIN = 10
USER_RATE_PLANTS_PER_MIN = 30
USER_RATE_IMAGE_UPLOAD_PER_MIN = 5

COOKIE_NAME = "plantpal_session"
CSRF_COOKIE_NAME = "plantpal_csrf"
```

### `db.py`

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = NORMAL;
```

Helpers: `connect_db()`, `init_db()`, `get_db()`, `transaction(db, mode="IMMEDIATE")`, `apply_pragmas()`.

### `security.py`

- `new_url_token() -> str` (32-byte url-safe)
- `hash_token(token: str) -> str` (HMAC-SHA256 with `TOKEN_PEPPER`)
- `constant_time_equal(a, b)`
- `create_session_cookie(response, session_token, settings)`
- `clear_session_cookie(response, settings)`
- `create_csrf_token(session_id) -> str`
- `verify_csrf_token(request)`
- `normalize_email(email)` (lowercase + trim)
- `hash_ip(ip)` (für Logging ohne PII)

### `rate_limit.py`

SQLite-backed fixed-window limiter (kein slowapi). Begründung: Pi-Restart erhält Counter, Multi-Worker safe.

```python
check_rate_limit(db, key: str, limit: int, window_seconds: int) -> None
rate_key_ip(request, scope: str) -> str
rate_key_user(user_id, scope: str) -> str
rate_key_email(email, scope: str) -> str
```

### `cli.py`

```bash
docker compose exec plantpal python -m plantpal.cli <command>
```

Commands:
- `bootstrap_admin(email)`
- `issue_login_link(email, send=False, print_link=True)`
- `create_invite(created_by, email)`

---

## 2. DB Schema (Codex Vollvorschlag)

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = NORMAL;

CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  display_name TEXT,                       -- OUT M1: weglassen
  role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
  reminder_enabled INTEGER NOT NULL DEFAULT 1 CHECK (reminder_enabled IN (0, 1)),
  reminder_hour_berlin INTEGER NOT NULL DEFAULT 8 CHECK (reminder_hour_berlin BETWEEN 0 AND 23),  -- OUT M1: hardcoded 8
  reminder_last_sent_date TEXT,
  reminder_channel TEXT NOT NULL DEFAULT 'email' CHECK (reminder_channel IN ('email', 'instagram', 'both')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_login_at TEXT,
  last_seen_at TEXT
);

CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_reminder_due ON users(reminder_enabled, reminder_last_sent_date);

CREATE TABLE invites (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token_hash TEXT NOT NULL UNIQUE,         -- ✓ M1: hashen
  email TEXT COLLATE NOCASE,
  created_by_user_id INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at TEXT NOT NULL,
  used_at TEXT,
  used_by_user_id INTEGER,
  revoked_at TEXT,
  FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (used_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_invites_email ON invites(email);
CREATE INDEX idx_invites_expires ON invites(expires_at);
CREATE INDEX idx_invites_unused ON invites(used_at, revoked_at, expires_at);

CREATE TABLE magic_tokens (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token_hash TEXT NOT NULL UNIQUE,         -- ✓ M1: hashen
  purpose TEXT NOT NULL CHECK (purpose IN ('login', 'register')),
  email TEXT NOT NULL COLLATE NOCASE,
  user_id INTEGER,
  invite_id INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at TEXT NOT NULL,
  used_at TEXT,
  consumed_by_session_id INTEGER,
  request_ip_hash TEXT,
  request_user_agent TEXT,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (invite_id) REFERENCES invites(id) ON DELETE CASCADE,
  FOREIGN KEY (consumed_by_session_id) REFERENCES sessions(id) ON DELETE SET NULL
);

CREATE INDEX idx_magic_tokens_hash ON magic_tokens(token_hash);
CREATE INDEX idx_magic_tokens_email_created ON magic_tokens(email, created_at);
CREATE INDEX idx_magic_tokens_expiry ON magic_tokens(expires_at);
CREATE INDEX idx_magic_tokens_unused ON magic_tokens(used_at, expires_at);

CREATE TABLE sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_hash TEXT NOT NULL UNIQUE,       -- ✓ M1: hashen
  user_id INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at TEXT NOT NULL,
  hard_expires_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  renewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  revoked_at TEXT,
  ip_hash TEXT,
  user_agent TEXT,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_sessions_hash ON sessions(session_hash);
CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_valid ON sessions(session_hash, revoked_at, expires_at, hard_expires_at);

CREATE TABLE plants (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  species TEXT,                            -- OUT M1: weglassen
  location TEXT,                           -- OUT M1: weglassen
  notes TEXT,
  watering_interval_days INTEGER NOT NULL DEFAULT 7 CHECK (watering_interval_days BETWEEN 1 AND 365),
  last_watered_at TEXT,
  next_water_due_at TEXT,                  -- OPTIONAL M1: derived, kann auch serverseitig pro Request berechnet werden
  image_path TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TEXT,                         -- M1: ersetzt is_active=0-Pattern, äquivalent
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_plants_user_active ON plants(user_id, deleted_at);
CREATE INDEX idx_plants_due ON plants(user_id, next_water_due_at, deleted_at);

CREATE TABLE plant_events (                -- OUT M1: ganz weglassen
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plant_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  event_type TEXT NOT NULL CHECK (event_type IN ('watered', 'created', 'updated', 'image_uploaded')),
  event_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  payload_json TEXT,
  FOREIGN KEY (plant_id) REFERENCES plants(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE reminder_send_log (           -- ✓ M1
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  reminder_date TEXT NOT NULL,
  channel TEXT NOT NULL DEFAULT 'email',
  status TEXT NOT NULL CHECK (status IN ('sent', 'failed', 'skipped')),
  error_code TEXT,
  error_message TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  UNIQUE(user_id, reminder_date, channel)
);

CREATE INDEX idx_reminder_log_date ON reminder_send_log(reminder_date, status);

CREATE TABLE rate_limits (                 -- ✓ M1
  key TEXT NOT NULL,
  window_start INTEGER NOT NULL,
  count INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  PRIMARY KEY (key, window_start)
);

CREATE INDEX idx_rate_limits_expires ON rate_limits(expires_at);

CREATE TABLE app_kv (                      -- OUT M1
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

Write transactions that consume tokens or mutate sessions use `BEGIN IMMEDIATE` to avoid token double-use races.

---

## 3. Endpoints

All response errors use:

```json
{
  "error": {
    "code": "string",
    "message": "string"
  }
}
```

### Auth

#### `POST /auth/request-login`

Request:
```json
{ "email": "user@example.com" }
```

Response (always generic, timing-padded):
```json
{ "ok": true, "message": "If this email can sign in, a link has been sent." }
```

- Auth: none.
- Rate-Limit: `3/email/hour` AND `10/IP/hour`.
- Status: `202 Accepted` für normalen Flow (auch unbekannte Email). `429` nur bei IP-Abuse.
- Resend-Down: Token wird trotzdem geschrieben, Mail-Failure geloggt, generische 202 zurück.

#### `GET /auth/verify?token=...`

- Auth: none.
- Rate-Limit: `10/IP/min`.
- Success: `303 See Other` zu `/app` (Browser-Flow) oder JSON 200 bei `Accept: application/json`.
- Errors: `400 invalid_token`, `410 token_expired`, `409 token_already_used`, `404 user_not_found`, `403 user_disabled`, `429 rate_limited`.

#### `POST /auth/register-with-invite`

Request:
```json
{ "invite_token": "...", "email": "user@example.com" }
```

- Rate-Limit: `10/IP/hour`.
- Errors: `400 invalid_invite`, `403 invite_email_mismatch`, `409 invite_already_used` / `user_exists`, `410 invite_expired`.

#### `POST /auth/logout`

- Auth required, CSRF required.
- Errors: `401`, `403 csrf_failed`.

#### `GET /auth/me`

- Auth required.
- Response: `{ id, email, role }`.
- Errors: `401`.

### Plants

All require auth. Mutations require CSRF.

| Endpoint | Method | Rate-Limit | Errors |
|---|---|---|---|
| `/api/plants` | GET | – | – |
| `/api/plants` | POST | 30/user/min | 400, 401, 403, 429 |
| `/api/plants/{id}` | GET | – | 404 |
| `/api/plants/{id}` | PATCH | 30/user/min | 404, 403, 429 |
| `/api/plants/{id}` | DELETE | 30/user/min | 404 |
| `/api/plants/{id}/water` | POST | 30/user/min | 404 |
| `/api/plants/{id}/image` | POST (multipart) | 5/user/min | 400, 413, 415, 422, 404 |
| `/api/plants/{id}/image` | GET | – | 404 |

Cross-User-Access: immer `404 plant_not_found` (never reveal existence).

### Settings

- `GET /api/settings` — Auth.
- `PATCH /api/settings` — Auth + CSRF, Rate `30/user/min`. Body: `{ reminder_enabled }`. `reminder_channel` ist read-only bis M2.

### Admin

Alle Admin-Endpoints: `users.role = 'admin'`.

- `POST /api/admin/invites` — Body: `{ email }`. Response: `{ id, email, invite_url, expires_at }`.
- `GET /api/admin/invites` — Liste.
- `POST /api/admin/invites/{id}/revoke`.
- `GET /api/admin/users`.
- `PATCH /api/admin/users/{id}` (M2): `{ status, role }`. Letzter aktiver Admin kann nicht demoted/disabled werden.

---

## 4. Magic-Link Flow (race-safe)

### Request Login

1. `POST /auth/request-login` mit Email.
2. `security.normalize_email()`.
3. Rate-Limit-Check (`3/email/h`, `10/IP/h`).
4. Response-Timing wird auf konfiguriertes Minimum gepaddet (`AUTH_REQUEST_MIN_MS = 350`).
5. `auth_service.request_login_link()` lookup `users.email`.
6. Wenn User nicht existiert / disabled: KEIN Token, generische 202.
7. Wenn aktiv: `new_url_token()`, `hash_token(token)` in `magic_tokens` mit `purpose='login'`, `expires_at = now + LOGIN_TOKEN_TTL_MIN`.
8. `email_service.send_magic_link()`.
9. 202 Accepted, generic message.

Edge Cases:
- Unbekannte Email → 202 generic.
- Disabled User → 202 generic.
- Email-Limit → 202 generic, kein Token.
- IP-Limit → 429.
- Resend down → 202 generic, Mail-Failure log, CLI-Fallback verfügbar.

### Verify Login

1. `GET /auth/verify?token=...`.
2. Token-Shape-Check.
3. Rate-Limit `10/IP/min`.
4. `hash_token(token)`.
5. `auth_service.verify_magic_link()` startet `BEGIN IMMEDIATE`.
6. `SELECT * FROM magic_tokens WHERE token_hash = ?`.
7. None → 400 invalid_token.
8. `used_at IS NOT NULL` → 409 token_already_used.
9. `expires_at <= now` → 410 token_expired.
10. `purpose != 'login'` → 400 invalid_token.
11. Load `users.id = user_id`.
12. Missing → 404 user_not_found.
13. Disabled → 403 user_disabled.
14. Atomic consume:
```sql
UPDATE magic_tokens
SET used_at = CURRENT_TIMESTAMP
WHERE id = ? AND used_at IS NULL AND expires_at > CURRENT_TIMESTAMP;
```
15. `rowcount != 1` → 409 token_already_used (Race-Sieger ist der andere).
16. Session-Row in derselben Transaktion erstellen.
17. `magic_tokens.consumed_by_session_id` setzen.
18. `users.last_login_at` updaten.
19. Commit.
20. Session-Cookie + CSRF-Cookie setzen.
21. Redirect oder JSON.

### Register With Invite

1. `POST /auth/register-with-invite`.
2. Normalize email, hash invite_token.
3. `BEGIN IMMEDIATE`.
4. Load invite via `token_hash`.
5. Diverse Validierungen (existiert? revoked? used? expired? email match?).
6. Wenn `users.email` schon existiert: `409 user_exists`, „Sign in instead".
7. Insert user.
8. Atomic mark invite used:
```sql
UPDATE invites
SET used_at = CURRENT_TIMESTAMP, used_by_user_id = ?
WHERE id = ? AND used_at IS NULL AND revoked_at IS NULL AND expires_at > CURRENT_TIMESTAMP;
```
9. `rowcount != 1` → 409.
10. Session erstellen.
11. Commit.
12. Cookies setzen.

---

## 5. Session Mechanics

Cookie: `plantpal_session`.

```text
HttpOnly: true
Secure: true (production), false (local HTTP)
SameSite: Lax
Path: /
Domain: unset (host-only)
Max-Age: SESSION_DAYS * 86400
```

Session-Token: 32-byte URL-safe. Nur `hash_token(...)` in `sessions.session_hash`. Cookie hat plaintext.

Validation in Middleware:

```sql
SELECT s.*, u.*
FROM sessions s
JOIN users u ON u.id = s.user_id
WHERE s.session_hash = ?
  AND s.revoked_at IS NULL
  AND s.expires_at > CURRENT_TIMESTAMP
  AND s.hard_expires_at > CURRENT_TIMESTAMP
  AND u.status = 'active';
```

Sliding Renewal:

- Nominal 90 Tage.
- Hard-Cap 180 Tage ab `sessions.created_at`.
- Renew nur wenn `now - renewed_at >= SESSION_RENEW_IF_OLDER_THAN_HOURS (24h)`.
- Neues `expires_at = min(now + 90 days, hard_expires_at)`.
- Cookie-Max-Age neu gesetzt.

`last_seen_at`-Update debounced via konditionalem UPDATE:

```sql
UPDATE sessions
SET last_seen_at = CURRENT_TIMESTAMP
WHERE id = ?
  AND last_seen_at < datetime('now', '-' || ? || ' minutes');
```

Logout setzt `sessions.revoked_at` und clear-Cookies.

---

## 6. CSRF Strategy

**Origin/Referer-Enforcement PLUS signed double-submit cookie.**

Cookies:
- `plantpal_session`: HttpOnly.
- `plantpal_csrf`: NOT HttpOnly (Frontend liest).
- CSRF-Token = `base64(session_id || nonce || hmac(CSRF_SECRET, session_id || nonce))`.

Frontend sendet bei unsafe methods (POST/PUT/PATCH/DELETE):
```text
X-CSRF-Token: <cookie value>
```

Middleware `verify_csrf_token(request)` prüft für unsafe methods:

1. Skippen für unauthenticated cookie-less endpoints (`/auth/request-login`, `/auth/verify`, `/auth/register-with-invite`).
2. `Origin`-Header muss zu `APP_BASE_URL` matchen.
3. Wenn `Origin` fehlt: `Referer` muss matchen.
4. `X-CSRF-Token` muss vorhanden sein.
5. Konstant-Zeit-Vergleich mit `plantpal_csrf`-Cookie.
6. HMAC-Verifikation bindet Token an aktuelle `sessions.id`.

Fehler: `403 csrf_failed`, „Security check failed. Refresh the page and try again.".

---

## 7. Rate-Limiting

Custom SQLite-backed Fixed-Window. Begründung: Pi-Restart erhält Counter, kein in-memory Limiter benötigt.

```sql
INSERT INTO rate_limits (key, window_start, count, expires_at)
VALUES (?, ?, 1, ?)
ON CONFLICT(key, window_start)
DO UPDATE SET count = count + 1;
```

Rules:

| Endpoint | Limit |
|---|---|
| `POST /auth/request-login` | `3/email/hour` + `10/IP/hour` |
| `GET /auth/verify` | `10/IP/min` |
| `POST /auth/register-with-invite` | `10/IP/hour` |
| `POST /api/plants` | `30/user/min` |
| `PATCH /api/plants/{id}` | `30/user/min` |
| `DELETE /api/plants/{id}` | `30/user/min` |
| `POST /api/plants/{id}/water` | `30/user/min` |
| `POST /api/plants/{id}/image` | `5/user/min` |
| `PATCH /api/settings` | `30/user/min` |
| Admin mutations | `30/admin-user/min` |

Timing-konstantes Login: Service paddet Response auf konfiguriertes Minimum.

---

## 8. Bootstrap-Admin CLI

```bash
docker compose exec plantpal python -m plantpal.cli <command>
```

### `bootstrap-admin --email <email>`

- Normalize email.
- Kein Admin? → Create user (oder upgrade existierenden) zu admin.
- User existiert? → promote zu admin.
- Anderer Admin existiert? → Refuse (außer `--force`).

### `issue-login-link --email <email> [--send] [--print-link]`

- Aktiver User notwendig.
- Schreibt `magic_tokens` Row.
- Druckt Login-URL.
- `--send` versucht Resend.
- Bei Resend-Failure: URL trotzdem in stdout.

### `create-invite --created-by <email> [--email <new>] [--send]`

- `created_by` muss Admin sein (außer `--system`).
- Erstellt `invites` Row mit `expires_at = now + INVITE_TOKEN_TTL_DAYS`.
- Druckt Invite-URL.

---

## 9. Image Service

Pipeline in `services/image_service.py:process_upload()`.

```python
Image.MAX_IMAGE_PIXELS = settings.MAX_IMAGE_PIXELS
```

Steps:
1. Rate-Limit `5/user/min`.
2. Plant-Ownership-Check.
3. Read max `MAX_UPLOAD_MB + 1` Bytes.
4. Size > Limit → `413 upload_too_large`.
5. Magic-Bytes-MIME via `python-magic` / `filetype`. Nicht `UploadFile.content_type` vertrauen.
6. Unsupported MIME → `415`.
7. `await asyncio.to_thread(_process_image_sync, raw_bytes)`.
8. Pillow `Image.verify()` Pre-Pass, dann reopen.
9. `ImageOps.exif_transpose(image)`.
10. Strip alle EXIF (neu erstellen ohne Metadata).
11. Center-crop auf Quadrat.
12. `Image.Resampling.LANCZOS` resize auf `IMG_SIZE × IMG_SIZE`.
13. Save als PNG, atomic write (tmp + rename).
14. `plants.image_path` updaten.

Failure-Codes:
- Too large → 413
- MIME mismatch → 415
- Decompression bomb → 400 invalid_image
- Truncated/corrupt → 400 invalid_image
- Pillow unexpected → 422 image_processing_failed
- Disk full → 507 oder 500
- Cross-user plant id → 404 plant_not_found

---

## 10. Reminder Cron

```python
AsyncIOScheduler(timezone=ZoneInfo("Europe/Berlin"))

CronTrigger(
    hour=settings.REMINDER_HOUR_BERLIN,
    minute=0,
    timezone="Europe/Berlin"
)
```

Begründung: System-Cron nicht nutzen (DST + Container-TZ-Drift sind häufige Pi-Failure-Modes).

Idempotency:
- `users.reminder_last_sent_date` = `YYYY-MM-DD` (Berlin local).
- `reminder_send_log UNIQUE(user_id, reminder_date, channel)`.

Catch-up:
- App-Start ruft `catch_up_missed_reminders(now_utc)`.
- Berlin-Lokaldatum + -Stunde berechnen.
- Wenn nach 08:00: target_date = heute.
- Wenn vor 08:00: target_date = gestern.
- Nur senden, wenn nicht schon gesendet.

DST:
- 08:00 existiert auf beiden DST-Wechsel-Tagen.
- Idempotency schützt vor doppeltem Send.

Per-User-Handling:
```python
for user in due_users:
    try:
        await send_user_digest(db, user.id, target_date)
    except Exception as exc:
        await reminder_repo.log_failure(...)
    await asyncio.sleep(1 / settings.RESEND_RATE_PER_SEC)
```

Resend:
- `0.2s` Sleep zwischen Sends.
- Bei `429`: exponentielle Backoff (max 3 Retries).
- Bei Failure: `reminder_send_log.status = 'failed'`, nächster Cron-Run versucht NICHT automatisch erneut (Admin-Retry separat).

Due Plants:
```sql
SELECT *
FROM plants
WHERE user_id = ?
  AND deleted_at IS NULL
  AND next_water_due_at <= ?
ORDER BY next_water_due_at ASC;
```

---

## 11. Config-Validation

- `SESSION_HARD_CAP_DAYS >= SESSION_DAYS`
- `IMG_SIZE > 0`
- `MAX_UPLOAD_MB <= 50`
- `REMINDER_HOUR_BERLIN ∈ [0, 23]`
- Production: Secure-Cookies + non-default secrets.

---

## 12. M2 Forward-Compat

Schema only:
```sql
reminder_channel TEXT NOT NULL DEFAULT 'email'
CHECK (reminder_channel IN ('email', 'instagram', 'both'))
```

M1: ignore `instagram`; senden wenn `reminder_channel IN ('email', 'both')`.

Kein Instagram-Code in M1.

---

## 13. Test-Strategie

Stack: pytest + pytest-asyncio + httpx.AsyncClient/ASGITransport + tmp_path SQLite + freezegun.

Test-Cases (konkret):

- **bootstrap**: Erste Admin-Erstellung, Refuse 2. ohne `--force`.
- **register**: valid invite, mismatch-email, used invite.
- **login happy**: Token erstellen, Verify, Cookies gesetzt.
- **login expired token**: 410 expired.
- **login double-click race**: parallel Verify-Calls, exactly one wins, anderer 409.
- **session renewal**: alt renewed_at bumps expires_at, hard_expires_at nicht überschritten.
- **logout**: revokes session, `/auth/me` → 401.
- **plant CRUD user isolation**: User B → 404 für User A's plant.
- **water action**: updates `last_watered_at` + `next_water_due_at` + event-log.
- **image upload magic-bytes fail**: text mit .jpg → 415/400.
- **image upload success**: EXIF strip + 96×96 PNG.
- **cron idempotency**: doppelter Lauf am gleichen Tag → 1 Mail.
- **cron DST spring-forward**: Test um 26.3.
- **cron Resend failure**: ein User fails, andere erfolgreich.

---

## 14. Failure-Mode Catalog (Top 10)

1. **Resend-Outage = Login-Lockout** → `request-login` schreibt Token vor Send, `cli.issue_login_link` druckt URL.
2. **Magic-Link Double-Click / Browser-Prefetch** → `BEGIN IMMEDIATE` + conditional `UPDATE`.
3. **Expired Magic Link** → 410 token_expired.
4. **Pi-Reboot um 08:00** → APScheduler Catch-up beim Start.
5. **DST-Doppel-/Skip-Send** → Berlin TZ + idempotency.
6. **Pillow blockt Event-Loop** → `asyncio.to_thread()`.
7. **Malicious Upload** → Magic-Bytes + MAX_IMAGE_PIXELS + Verify + EXIF-Strip.
8. **SQLite-Lock unter Concurrency** → WAL + `busy_timeout=5000` + short transactions.
9. **CSRF gegen Cookie-Auth** → SameSite + Origin/Referer + signed double-submit.
10. **Invite-only verhindert Admin-Bootstrap** → `cli.bootstrap_admin`.
