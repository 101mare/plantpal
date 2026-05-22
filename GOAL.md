# GOAL — PlantPal M1 Vollständige Implementation

**Status:** Active
**Erstellt:** 2026-05-21
**Ausführender Agent:** Codex (OpenAI gpt-5.5)
**Spec-Wahrheit:** [`PRD.md`](PRD.md) + [`docs/BACKEND_ARCHITECTURE.md`](docs/BACKEND_ARCHITECTURE.md)

---

## Outcome

PlantPal M1 vollständig implementiert, getestet, lint-clean. Deploybar via `docker compose up` auf Raspberry Pi.

---

## Completion-Conditions (ALLE müssen TRUE sein)

Diese Conditions sind **mechanisch verifizierbar**. Solange auch nur eine FALSE ist, gilt das Goal als nicht erreicht und es wird iteriert.

### Backend

- [ ] **C1** — Alle 22 Akzeptanzkriterien aus PRD §11 (AK-1 … AK-22) sind als pytest-Tests implementiert.
- [ ] **C2** — `pytest tests/` → exit code 0, alle Tests grün.
- [ ] **C3** — `pytest --cov=plantpal --cov-report=term tests/` → Coverage ≥ 90 % auf `src/plantpal/`.
- [ ] **C4** — `ruff check src/ tests/` → 0 Errors.
- [ ] **C5** — `ruff format --check src/ tests/` → 0 Formatting-Issues.
- [ ] **C6** — Alle SQL-Migrationen aus `migrations/` laufen idempotent (`init_db()` zweimal aufrufen → kein Fehler).
- [ ] **C7** — CLI-Commands funktional: `python -m plantpal.cli bootstrap-admin --email …`, `… issue-login-link --email …`, `… create-invite --created-by … --email …`.

### Frontend

- [ ] **C8** — `npm run build` im `frontend/` → exit 0.
- [ ] **C9** — `npm run lint` im `frontend/` → exit 0 (eslint + prettier).
- [ ] **C10** — `npm run test` (Vitest) → exit 0.
- [ ] **C11** — Plantdex-Page, Add-Plant-Modal, Plant-Detail-Modal, Login, Register, Settings, Stats existieren als Komponenten und sind in Routing eingebunden.

### Deployment

- [ ] **C12** — `docker compose build` → exit 0.
- [ ] **C13** — `docker compose up -d` startet ohne Crash; `curl localhost:8000/api/health` → JSON `{"status":"ok","db_ok":true,"scheduler_running":true}`.
- [ ] **C14** — Caddy-Config + Litestream-Sidecar in `docker-compose.yml` vorhanden, Konfiguration via ENV-Vars.

### Dokumentation

- [ ] **C15** — `README.md` mit: Setup-Schritte, ENV-Variablen-Tabelle, Deploy-Anleitung Pi, CLI-Befehle, Backup/Restore-Drill, Privacy-Notice.

---

## Scope

- **In M1:** Alles aus PRD §4 (Functional Requirements) und §5 (Non-Functional).
- **Out of M1:** Items aus PRD §12 sind verboten zu implementieren. Wenn Codex unklar ist: PRD §12 als Negativ-Liste konsultieren.
- **Implementierungs-Details:** `docs/BACKEND_ARCHITECTURE.md` — Codex' eigener Vorschlag. Bei Konflikt mit M1-Scope-Tabellen dort: M1-Scope gewinnt.

---

## Architektur-Anker (binding)

- **Backend:** flache `src/plantpal/`-Struktur (~10–12 Files). KEINE `repositories/`-Schicht. KEIN `api/`-Subpackage. Routes direkt in `main.py` (split nur wenn >150 Zeilen).
- **DB:** SQLite via aiosqlite, raw parametrisierte SQL. WAL + `busy_timeout=5000`, `foreign_keys=ON`. Migrations `migrations/001_*.sql`, tracked in `_migrations`.
- **Datetimes:** naive Berlin (`Europe/Berlin`), Helper `now_berlin()`.
- **Soft-Delete:** `is_active=0` Pattern (PRD §8). Wenn Codex `deleted_at TEXT` bevorzugt: ok, aber konsistent in allen Tables.
- **Frontend:** Vite + React + TS + Tailwind v4 + Pixel-CSS. State via Tanstack Query. Forms via React-Hook-Form. Toasts via sonner.
- **Tests:** pytest + pytest-asyncio + httpx (ASGI). conftest mit `db` (tmp_path) + `client` Fixture. `pytest-asyncio mode=auto`.

---

## Iterations-Regel

Codex arbeitet in folgenden Phasen, jede Phase muss grün sein, bevor die nächste startet:

1. **Phase 1 — Foundation:** `pyproject.toml`, `package.json`, `.gitignore`, `config.py`, `db.py`, `models.py`, `security.py`, Migrations. → `pytest tests/test_config.py tests/test_db.py` grün, `ruff` grün.
2. **Phase 2 — Auth Core:** `auth_service.py`, magic-link request/verify, sessions, CSRF, rate-limit, CLI bootstrap. → AK-1 bis AK-4, AK-14, AK-16, AK-17, AK-18, AK-20, AK-21 grün.
3. **Phase 3 — Plants + Images:** `plant_service.py`, `image_service.py`, async-pipeline, magic-bytes, EXIF. → AK-5, AK-6, AK-7, AK-15 grün.
4. **Phase 4 — Email + Reminder-Cron:** `email_service.py`, `reminder_service.py`, APScheduler, idempotency, catch-up. → AK-8 bis AK-13 grün.
5. **Phase 5 — Routes + main.py:** alle Endpoints, FastAPI app, Middleware. → AK-19, AK-22 grün, restliche Integration-Tests grün.
6. **Phase 6 — Frontend:** Vite + Tailwind + Pages + Routing. → `npm run build`, `npm test` grün.
7. **Phase 7 — Deployment:** Dockerfile, docker-compose, Caddyfile, Litestream-Config, README. → C12–C15 grün.
8. **Phase 8 — Coverage & Polish:** Test-Coverage auf 90% bringen, alle Lint-Issues fixen.

Nach jeder Phase: vollständiger Test+Lint-Run. Wenn rot → fixen, nicht weitermachen.

---

## Acceptance Test (Self-Verification)

Codex muss am Ende jedes Iterations-Runs folgende Befehle ausführen und Output kapieren:

```bash
ruff check src/ tests/
ruff format --check src/ tests/
pytest tests/ -v
pytest --cov=plantpal --cov-report=term tests/
cd frontend && npm run lint && npm run test && npm run build
docker compose build
```

Solange einer fehlschlägt: weiter iterieren.

---

## Stop-Condition

Goal erfüllt, sobald **ALLE** Conditions C1–C15 TRUE sind, verifiziert via expliziter Befehlsausführung im aktuellen Run.

Bei Blockern (z.B. fehlende OS-Pakete, externe API down): Codex schreibt blockierende Issue in `BLOCKERS.md` und beendet mit klarem Status.
