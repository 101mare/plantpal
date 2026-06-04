# PlantPal — Product Requirements Document v3

**Status:** v3 — Grill-Session 2026-06-03 (autonomer Build-Auftrag)
**Basis:** M1 ist vollständig implementiert (siehe `docs/PRD_M1.md`). Dieses Dokument spezifiziert die v3-Erweiterung.
**Autor:** Marius Schwarzin (mariusschwarzin@gmail.com)
**Erstellt mit:** Ultracode — 7 parallele Spezialisten-Bausteine, im Leader (Claude) synthetisiert.

> **PlantPal v3** erweitert das implementierte M1 (Pokédex-Gieß-Tracker: Magic-Link-Auth, Email-Digest, gehärtete Bild-Pipeline, Docker).
> **Neu in v3:** öffentliche Community (100–1000 User), Invite-Ketten + Mehrfach-Link + 6-stelliger Login-Code, Email-ändern,
> Gieß-Historie + reichhaltige Stats, Standort/Raum-Gruppierung, echte i18n (DE/EN), Light-Mode-Toggle, PWA,
> voll editierbare Pflanzen inkl. Bild-Tausch, Tropfen-Status-Anzeige, Suche/Sortierung/Filter,
> DSGVO (Daten-Export, Impressum, Datenschutzerklärung), Cloudflare-Tunnel-Deployment, Housekeeping-Cron + Monitoring.

## Inhaltsverzeichnis
1. **Overview, Goals, Personas, Tech-Stack, Milestones, Test-Strategie, Out-of-Scope**
2. **Auth & Onboarding** — Invite-Ketten (Quota 3), Mehrfach-Link, 6-stelliger Code, Email-ändern
3. **Backend-Erweiterungen** — Gieß-Historie, reichhaltige Stats, Standort, Cleanup-Cron, WAL/Concurrency, DSGVO-Export
4. **Frontend** — i18n, Editieren+Bild-Tausch, Suche/Filter, Lösch-UX, Light-Mode, Onboarding, PWA, Tropfen-Status
5. **Datenmodell & Migration 002** — vollständiges SQL + Pydantic-Deltas
6. **Deployment & Betrieb** — Cloudflare Tunnel, Backup-Cron, Monitoring
7. **Recht & DSGVO** — Impressum, Datenschutzerklärung

---



# Teil 1 — Overview, Goals, Personas, Tech-Stack, Milestones

# PlantPal — Product Requirements Document v3

**Status:** Draft v3 — Gesamt-PRD über das ganze Projekt (M1 als implementierte Baseline + v3-Erweiterung)
**Stand:** 2026-06-03
**Autor:** Marius Schwarzin (mariusschwarzin@gmail.com)
**Basis:** PRD M1 (v2, 2026-05-21, implementiert) + Decision-Log Grill-Session 2026-06-03

> **Was ist neu gegenüber M1?** M1 ist vollständig gebaut, getestet (121 Tests, 93 % Coverage) und dockerisiert — es bildet die **Baseline**. v3 **erweitert** M1, ersetzt es nicht: neue öffentliche Community-Zielgruppe (100–1000 User), Gieß-Historie + reichhaltige Stats, echte i18n (DE/EN), Tropfen-Wasserstands-Anzeige, Invite-Ketten für alle User, 6-stelliger Login-Code, Email-Änderung, PWA, Light-Mode, DSGVO-Self-Service-Export, Impressum/Datenschutz, sowie ein Betriebs-Re-Setup (Cloudflare Tunnel statt Caddy, Cron-Backup statt Litestream-Default). Geliefert wird in vier Phasen (A–D) in **einem Durchlauf** mit **finalem Codex-Gesamt-Review**.

---

## 1. Overview

### Problem
Zimmerpflanzen brauchen regelmäßiges Gießen — aber ohne zuverlässiges Erinnerungssystem werden Gießintervalle vergessen, was zu vertrockneten oder überwässerten Pflanzen führt. Wer mehrere Pflanzen pflegt, verliert zudem den Überblick: *Welche* ist wie überfällig, *wie konsequent* gieße ich überhaupt, und *wo* (welcher Raum) steht was. M1 löst die Kern-Erinnerung für einen kleinen, privaten Invite-Kreis — aber es war nie deployed, hat keine Gieß-Historie (also keine echten Stats), nur Deutsch, eine rein binäre Durst-Anzeige und ein Onboarding, das einen leeren Plantdex ohne Führung zeigt.

### Solution (v3)
**PlantPal** ist eine selbst-gehostete, Pokédex-artige Web-App, die das eigene Pflanzen-Inventar als „Plantdex" verwaltet: jede Pflanze hat ein 96×96-Pixel-Foto, einen Namen, ein Gieß-Intervall und einen Standort/Raum. Die App erkennt automatisch, welche Pflanzen Durst haben, visualisiert den Wasserstand pro Pflanze als Tropfen-Reihe (Füllgrad = verstrichene Zeit seit Gießung / Intervall, welke Blüte ab Überfälligkeit) und schickt einen täglichen, pro User zeitlich wählbaren Email-Digest. Jede Gieß-Aktion wird in einer **Historie** protokolliert, woraus reichhaltige Statistiken entstehen (Gieß-Streak, Konsistenz-%, am längsten überfällige Pflanze, Durchschnitts-Intervall). v3 öffnet PlantPal für eine kleine **öffentliche Community (100–1000 User)** über **selbst-tragende Invite-Ketten** (jeder lädt ein, Default-Kontingent 3), bietet **echte Zweisprachigkeit (DE/EN)**, einen **Light-/Dark-Mode**, ist als **PWA installierbar** und erfüllt deutsche/EU-**Rechtspflichten** (Impressum, Datenschutzerklärung, DSGVO-Self-Service-Export & -Löschung). Betrieben wird sie weiterhin selbst-gehostet auf einem Pi/Mini-PC, jetzt öffentlich erreichbar via **Cloudflare Tunnel** unter **getplantpal.com**.

### Designprinzip v3 (durchgängig)
**Backend voll, sauber, getestet — Frontend zeigt zunächst eine kuratierte Teilmenge.** Schema und Service-Layer implementieren die *vollständige* Funktionalität (gesamte Gieß-Historie, alle Stat-Kennzahlen, vollständige Tropfen-Wasserstands-Daten). Das Frontend rendert in dieser Iteration bewusst nur das, was sofort Nutzwert stiftet (Kernzahlen + Streak + überfälligste Pflanze; Tropfen-Anzeige als spezifizierter, später aktivierter Baustein). So bleibt das Backend zukunftsfest, ohne das UI zu überladen.

---

## 2. Goals & Non-Goals (v3)

### Goals (v3)
1. **Gieß-Historie als Fundament:** Jede `/water`-Aktion wird in einer `waterings`-Tabelle protokolliert UND aktualisiert `plants.last_watered_at` — Grundlage für echte Stats und Konsistenz-Messung.
2. **Reichhaltige Stats (Backend voll):** Streak, Gieß-Konsistenz %, am längsten überfällige Pflanze, Durchschnitts-Intervall pro Pflanze und global — vollständig berechnet und getestet.
3. **Pflanze voll editierbar inkl. Bild-Tausch:** Die in M1 bereits vorhandenen Endpoints (`PATCH`, `POST …/image`) bekommen vollständiges UI; neues Feld **Standort/Raum** mit Gruppierung in Liste/Stats.
4. **Echte i18n (DE + EN):** Browser-Locale-Default mit Fallback Deutsch, Umschalter in Settings, lokalisierte Mail-Templates (`users.locale`).
5. **Selbst-tragende Invite-Ketten:** Jeder User darf einladen (Default-Quota 3, Admin kann erhöhen); Mehrfach-Invite-Links mit Kontingent + Ablauf, Redemptions getrackt.
6. **Login-Komfort & -Robustheit:** Zusätzlich zum Magic-Link ein 6-stelliger numerischer Code (gleiche Mail enthält Link UND Code), an Token/Email gebunden, kurze TTL, strenge Rate-Limits + Lockout.
7. **Self-Service-Accountpflege:** Email-Adresse ändern (Verify an neue Adresse), DSGVO-Daten-Export (JSON + Bilder als ZIP), Account-Löschung (existiert bereits).
8. **UX-Politur & Onboarding:** Tropfen-Wasserstands-Anzeige (Spec), Suche/Sortierung/Thirsty-Filter, Lösch-UX mit Undo-Toast, freundlicher Empty-State mit Erste-Pflanze-CTA, Light-/Dark-Mode-Toggle, Mobile-Safe-Areas & Touch-Targets.
9. **PWA:** Installierbar (Manifest + Service-Worker), store-ready, Offline-fähige Shell.
10. **Pro User wählbare Reminder-Uhrzeit:** Default 8 Uhr, Zeitzone bleibt fix `Europe/Berlin`; stündlicher Cron filtert fällige User.
11. **Öffentlicher Betrieb:** Deploy via Cloudflare Tunnel auf getplantpal.com, tägliches Backup (DB + Bilder), Housekeeping-Cron, externes Uptime-Monitoring.
12. **Rechtskonformität:** Impressum (DDG) + Datenschutzerklärung (DSGVO Art. 13) als statische Seiten mit Footer-Links; kein Cookie-Banner (Begründung in §RECHT).

### Non-Goals (v3)
- **Web-Push-Notifications.** Reminder bleibt ausschließlich Email; `reminder_channel` bleibt reiner Forward-Compat-Hook.
- **Instagram-Posting / Social-Posting.** (Aus dem M1-„M2"-Plan herausgenommen; nicht Bestandteil von v3.)
- **Wassersensoren / Hardware-Integration.**
- **Mehrere Bilder pro Pflanze / Galerie.** Genau ein 96×96-Pixel-Icon pro Pflanze.
- **Postgres / DB-Migration weg von SQLite.** SQLite (WAL) bleibt; **keine Pagination**.
- **Öffentliche Self-Service-Registrierung ohne Invite.** Zugang bleibt invite-only (jetzt über Invite-Ketten breit verteilbar).
- **Passwort-Login, Google/OAuth-Login.**
- **Geteilte Pflanzen, Likes, Kommentare, Community-Feed.** Trotz öffentlicher Community bleiben Pflanzen strikt user-scoped & privat.
- **Native Mobile-App.** PWA statt nativer App.
- **Konfigurierbare Reminder-*Zeitzone*.** Uhrzeit ist wählbar, TZ ist fix Berlin.
- **Eigenes finales Logo in dieser Iteration.** PWA-Icons sind temporäre Platzhalter (echtes Logo später via Higgsfield MCP in eigener Iteration).

### Übernommene M1-Non-Goals (weiterhin gültig)
Pflanzen-Wiki / Species-DB; Latin-Name-Feld; Offline-Queueing von Mutationen (PWA cached nur die Shell, keine schreibende Offline-Queue).

---

## 3. User Personas & Stories (v3)

### Persona-Update
M1 zielte auf **„Pflanzen-Marius"** (1 Self-Hoster + Familie). v3 erweitert auf eine **kleine öffentliche Community von 100–1000 Usern**, die über Invite-Ketten organisch wächst:

- **Host-Marius** (unverändert Kern): 30, 14+ Pflanzen, betreibt die Instanz auf Pi/Mini-PC, mag Retro-Pixel-Ästhetik, ist Bootstrap-Admin, vergibt Invite-Kontingente.
- **Community-Mitglied „Lena"**, 26, kam über einen geteilten Invite-Link einer Freundin, nutzt PlantPal primär am **Handy** (PWA installiert, Home-Screen-Icon), spricht im Zweifel lieber **Englisch**, will morgens *zu ihrer* Uhrzeit erinnert werden und ihre **Gieß-Streak** sehen.
- **Einladende „Tom"**, beliebiger Bestands-User ohne Admin-Rechte, möchte seine WG einladen — erzeugt im normalen Settings-UI einen Invite-Link mit Kontingent 3 und teilt ihn.

Implikationen: Mobile-First-Politur (Safe-Areas, Touch-Targets ≥ 44 px), Mehrsprachigkeit, Selbstbedienungs-Onboarding ohne Admin-Eingriff pro User, und sichtbare, motivierende Stats (Streak/Konsistenz) für Engagement.

### User Stories (M1 — bereits implementiert, Baseline)
US-1 … US-12 aus PRD M1 (Invite-Registrierung, Magic-Link-Login, Pflanze anlegen mit Foto, Plantdex mit Durst-Hervorhebung, Ein-Klick-Gießen, Email-Digest, Email-Toggle, Pflanze editieren/löschen, Detailansicht, Basis-Stats, Account-Löschung, Admin-Invite) gelten unverändert als erfüllt.

### User Stories (v3 — neu/erweitert)

| ID | Story |
|---|---|
| US-13 | Als User möchte ich beim Login **alternativ einen 6-stelligen Code** aus der Mail eingeben, falls der Magic-Link (z. B. auf anderem Gerät) unbequem ist. |
| US-14 | Als **beliebiger** User möchte ich im Settings-UI einen **Invite-Link mit Kontingent + Ablauf** erzeugen und teilen, ohne Admin zu sein. |
| US-15 | Als User möchte ich meine **Email-Adresse ändern** und das per Bestätigungsmail an die neue Adresse verifizieren. |
| US-16 | Als User möchte ich die **Sprache (DE/EN) umschalten**; die App startet automatisch in meiner Browser-Sprache (Fallback Deutsch) und meine Reminder-Mails kommen in meiner Sprache. |
| US-17 | Als User möchte ich pro Pflanze einen **Standort/Raum** angeben und meine Pflanzen danach **gruppiert** sehen. |
| US-18 | Als User möchte ich auf einer Pflanze **„Gegossen"** klicken und sicher sein, dass dies in meiner **Gieß-Historie** landet — für Streak & Statistiken. |
| US-19 | Als User möchte ich **reichhaltige Stats** sehen: aktuell mind. Kernzahlen (Total, durstig), **Gieß-Streak** und die **am längsten überfällige** Pflanze. |
| US-20 | Als User möchte ich pro Pflanze auf einen Blick den **Wasserstand** erkennen (Tropfen-Reihe, Füllgrad nach verstrichener Zeit; welke Blüte + Tage-überfällig bei Überfälligkeit). |
| US-21 | Als User möchte ich meine Pflanzen **durchsuchen**, nach **Durst/Name/zuletzt gegossen sortieren** und einen **Thirsty-Filter** setzen. |
| US-22 | Als User möchte ich eine Pflanze **löschen** und sie über einen **Rückgängig-Toast** sofort wiederherstellen können. |
| US-23 | Als User möchte ich **die Uhrzeit** meines täglichen Reminders selbst wählen (Zeitzone fix Berlin). |
| US-24 | Als neuer User mit leerem Plantdex möchte ich einen **freundlichen Empty-State** mit klarer **„Erste Pflanze anlegen"-CTA** und 2–3 Tipps sehen. |
| US-25 | Als User möchte ich PlantPal **als App installieren** (PWA, Home-Screen-Icon, App-Splash). |
| US-26 | Als User möchte ich **zwischen Light- und Dark-Mode** umschalten; meine Wahl bleibt erhalten. |
| US-27 | Als User möchte ich meine **Daten exportieren** (JSON + meine Bilder als ZIP), gemäß DSGVO Art. 15/20. |
| US-28 | Als Besucher/User möchte ich **Impressum** und **Datenschutzerklärung** über Footer-Links erreichen. |
| US-29 | Als Admin möchte ich das **Invite-Kontingent** einzelner User erhöhen können. |

---

## 4. Tech-Stack (Deltas gegenüber M1)

> M1-Stack bleibt vollständig in Kraft (FastAPI · aiosqlite · raw parametrisierte SQL · Pydantic v2 · Pillow+filetype · APScheduler · SQLite-backed Rate-Limit · structlog; Frontend Vite · React 18 · TS 5 · Tailwind v4 + Pixel-CSS-Layer · React Router v6 · Tanstack Query · react-hook-form · sonner). Nur die **Deltas**:

### Backend — neu
- **Keine** neuen schweren Dependencies für den Kern. i18n-Mail-Templates werden in Python gehalten (Dict/Template-Lookup per `users.locale`), kein zusätzliches Template-Framework.
- **Daten-Export:** `zipfile` (stdlib) für den ZIP-Bundle aus JSON + Bildern — keine neue Lib.
- **Bewusst NICHT eingeführt:**
  - **`slowapi` — NICHT.** Das bestehende SQLite-backed Fixed-Window-Rate-Limit (`rate_limits`-Tabelle, `rate_limit.py`) bleibt der einzige Limiter (Pi-Restart-safe, Single-Writer-kompatibel). Neue Endpoints (Login-Code-Verify, Email-Change, Export, Invite-Create) hängen sich an denselben Mechanismus.
  - **`web-push` / `pywebpush` — NICHT.** Web-Push ist explizit Non-Goal; kein Push-Stack, keine VAPID-Keys.

### Frontend — neu
- **i18next + react-i18next** für echte Laufzeit-i18n (DE/EN), Browser-Locale-Detection (`i18next-browser-languagedetector`) mit Fallback `de`. Übersetzungs-Ressourcen als statische JSON-Bundles (`locales/de.json`, `locales/en.json`).
- **vite-plugin-pwa** (mit Workbox unter der Haube) für Manifest-Generierung + Service-Worker (Precache der App-Shell, Network-First für `/api`). Liefert installierbare, store-ready PWA.
- **Leichtgewichtige Charts via reinem CSS/SVG** — **keine** Charting-Library (kein Recharts/Chart.js). Streak-Heatmap, Konsistenz-Balken und Tropfen-Wasserstand werden als handgebaute SVG-/CSS-Komponenten gerendert (passt zur Pixel-Ästhetik, hält das Bundle klein, keine Lizenz-/Größen-Last).
- **Theme via CSS-Variablen** unter `[data-theme="light|dark"]` am `<html>`-Element; Persistenz in `localStorage` (+ optional `users.theme`). Kein UI-Framework-Wechsel.

### Infra — Deltas (Detail im Deploy-Baustein)
- **Cloudflare Tunnel** (`cloudflared`-Container) statt Caddy/Let's-Encrypt; App nur auf Loopback, TLS terminiert Cloudflare. Ports 80/443 entfallen.
- **Tägliches Cron-Backup** (`sqlite3 .backup` + `rsync` von DB **und** `data/images`) statt Litestream-Default; Litestream deaktiviert/optional.
- **Domain:** getplantpal.com (Cloudflare Registrar; DNS + Tunnel aus einer Hand).
- **Mail:** Resend bleibt, **provider-agnostisch** gekapselt (`email_service.py`); Start auf Free-Tier, Upgrade-Schwelle siehe Offene Punkte.

---

## 5. Milestones

### M1 — MVP ✅ **DONE (implementierte Baseline)**
Vollständig gebaut, getestet (121 Tests, ~93 % Coverage) und dockerisiert. Umfang: Magic-Link-Auth + Invite-Token + Sessions (Hash in DB, Soft-/Hard-Cap, Sliding-Renewal) + CSRF (Origin/Referer + signed double-submit) + SQLite-Rate-Limit; Plant-CRUD; gehärtete Bild-Pipeline (Magic-Bytes, Decompression-Guard, EXIF-Strip, 96×96-PNG, atomic write); Plantdex + Thirsty-Section; täglicher Email-Digest (DST-safe, idempotent via `reminder_send_log`, Reboot-Catch-up); Settings (Email-Toggle, Logout, Admin-Invite, Account-Löschung); Basis-Stats (Total + Thirsty); Healthcheck; Docker-Compose. **18 Endpoints.** *Hinweis: M1 war nie deployed — der öffentliche Betrieb beginnt mit v3.*

### v3 — Public Community Release (dieses PRD), in vier Phasen, ein Durchlauf

- **Phase A — Schema + Backend:** Migration `002` (waterings, location_room, user-Settings-Spalten, Invite-Multi-Use + Redemptions, Login-Code, Email-Change). Service-Layer voll: Historie schreiben/lesen, alle Stats berechnen, Standort, Invite-Ketten, Export. Neue/erweiterte Endpoints. Tests + Lint grün.
- **Phase B — Auth-Erweiterungen:** 6-stelliger Login-Code (Erzeugung in Mail, Verify-Seite, Bindung an Token/Email, TTL, Rate-Limit + Lockout); User-Invite-Erzeugung (nicht-Admin); Email-Änderung mit Verify-Mail; Admin-Quota-Erhöhung. Tests + Lint grün.
- **Phase C — Frontend v3:** i18n (DE/EN, Browser-Default, Umschalter), Pflanzen-Voll-Editor inkl. Bild-Tausch, Standort + Gruppierung, Suche/Sortierung/Filter, Lösch-Undo-Toast, Onboarding-Empty-State, Light-/Dark-Toggle, Stats-UI (Kernzahlen + Streak + überfälligste), Tropfen-Wasserstands-Spec umgesetzt soweit aktiviert, Theme-Politur. Tests + Lint + Build grün.
- **Phase D — Deploy / PWA / Legal:** Cloudflare-Tunnel-Compose, Backup-Cron, Housekeeping-Cron, Uptime-Monitor-Hook auf `/api/health`; PWA (Manifest + SW, Temp-Icons); Impressum + Datenschutz + Footer; DSGVO-Export-UI. Tests + Lint + Docker-Build grün.

### Phasen-Build-Plan (Delivery-Modell)
- **Ein Durchlauf, sequentiell A → B → C → D.** Jede Phase schließt mit **Tests grün + Lint clean** (Backend pytest/ruff, Frontend vitest/eslint/prettier/build, Docker-Build) ab, bevor die nächste startet.
- **Kein Review pro Phase.** Stattdessen **ein finaler Codex-Gesamt-Review** über das fertige v3 (Backend + Frontend + Infra + Migration). Findings werden danach gebündelt gefixt, dann `session-verify`.
- Migration `002` ist **idempotent** und in `_migrations` getrackt (der bestehende Runner in `db.py` splittet auf `;`, strippt `--`-Kommentare und committet DDL + Marker atomar; `002` wird so geschrieben, dass jedes Statement genau einmal sauber anwendbar ist).

### Zukunft / nicht in v3 (Backlog)
Eigenes Logo via Higgsfield (eigene Iteration); Resend-Pro-Upgrade bei Wachstum; vollständige Stats-UI (Konsistenz-%, Durchschnitts-Intervall, Charts, Heatmap); vollständige Aktivierung der Tropfen-Wasserstands-Anzeige, falls in Phase C zurückgestellt.

---

## 6. Test-Strategie (Übersicht v3)

> Detaillierte Akzeptanzkriterien (AK-…) liegen in den fachlichen Bausteinen (Auth, Plants/Historie/Stats, Frontend/PWA/i18n, Reminder, Deploy/Legal). Diese Übersicht definiert Stack, Konventionen und Coverage-Erwartung.

### Stack & Konventionen (unverändert aus M1, fortgeführt)
- **Backend:** pytest + pytest-asyncio (`mode=auto`) + httpx `AsyncClient`/`ASGITransport`; `conftest.py` mit `db`-Fixture (tmp_path-SQLite, Migrationen angewandt) und `client`-Fixture; `freezegun` für Zeit-/DST-/Streak-Tests. Raw parametrisierte SQL; CI-Grep gegen f-strings in SQL bleibt.
- **Frontend:** Vitest (Unit/Component, Testing-Library) + Playwright (E2E gegen Backend mit tmp-DB).
- **Coverage-Ziel:** ≥ 90 % Backend (mind. das M1-Niveau halten); jede Akzeptanz hat eine zugeordnete Test-ID/Datei.

### Neue Test-Schwerpunkte v3 (pro Phase)
- **Migration 002:** Idempotenz (zweifaches `init_db` → keine doppelte Spalte/Fehler), Spalten-/Tabellen-Existenz, Defaults korrekt gesetzt (`invite_quota=3`, `locale='de'`, `reminder_hour=8`, `theme='dark'`), Backfill bestehender Rows.
- **Gieß-Historie:** `/water` schreibt **eine** `waterings`-Row **und** aktualisiert `plants.last_watered_at` (Transaktions-Konsistenz); Mehrfach-Gießen erzeugt mehrere Rows; User-Scope (fremde `plant_id` → 404, kein Historie-Schreiben).
- **Stats:** deterministische Berechnung von Streak / Konsistenz-% / längster Überfälligkeit / Durchschnitts-Intervall bei fixierter Zeit; Edge-Cases (keine Pflanzen, keine Historie, alle überfällig).
- **Login-Code:** korrekter Code loggt ein; falscher Code zählt `attempt_count` hoch; Lockout nach konfiguriertem Schwellwert; abgelaufener Code → Fehler; Code an Email/Token gebunden (Code für falsche Email ungültig); Rate-Limit greift.
- **Email-Change:** Request schreibt `email_change_requests`, Verify-Mail an **neue** Adresse, Bestätigung ändert `users.email`; abgelaufener/benutzter Request → Fehler; Kollision mit existierender Email → Fehler.
- **Invite-Ketten:** Nicht-Admin erzeugt Link; `max_uses`/`used_count`-Enforcement (über Kontingent → Ablehnung); Redemption-Row pro Registrierung; Ablauf greift; Quota-Erschöpfung des Erzeugers wird durchgesetzt.
- **i18n:** Mail-Template wird gemäß `users.locale` gewählt (DE vs. EN); Frontend-Default folgt Browser-Locale mit Fallback `de`.
- **Reminder-Uhrzeit:** stündlicher Cron sendet nur an User, deren `reminder_hour` der aktuellen Berlin-Stunde entspricht und die durstige Pflanzen haben; Idempotenz (`reminder_send_log`) bleibt DST-safe.
- **Export:** ZIP enthält gültiges JSON (alle User-Daten) + alle Bilder des Users; nur eigene Daten (kein Cross-User-Leak).
- **PWA:** Build erzeugt valides Manifest + Service-Worker; App-Shell wird precached; `/api`-Requests sind nicht aggressiv gecacht.
- **Legal/Theme/UX (E2E):** Footer-Links erreichen Impressum/Datenschutz; Lösch-Undo-Toast stellt Pflanze wieder her; Theme-Toggle persistiert über Reload; Suche/Sort/Filter wirken.

---

## 7. Out-of-Scope (v3) — explizit

- Web-Push / Push-Benachrichtigungen jeder Art (kein `pywebpush`, kein VAPID).
- Instagram- / Social-Media-Posting.
- `slowapi` oder ein zweiter Rate-Limiter neben der `rate_limits`-Tabelle.
- Postgres / DB-Engine-Wechsel; Pagination/Infinite-Scroll.
- Charting-Bibliotheken (Charts ausschließlich CSS/SVG).
- Öffentliche Registrierung ohne Invite; Passwort-/OAuth-Login.
- Geteilte Pflanzen, Likes, Kommentare, öffentlicher Community-Feed.
- Mehrere Bilder pro Pflanze / Galerie.
- Native Mobile-App.
- Konfigurierbare Reminder-Zeitzone (nur Uhrzeit wählbar; TZ fix `Europe/Berlin`).
- Cookie-Consent-Banner (nur technisch notwendige Session-/CSRF-Cookies — Begründung im RECHT-Baustein).
- Finales Logo / Custom-Icon-Design (Temp-Platzhalter; Higgsfield-Iteration später).
- Vollständige Stats-UI (über Kernzahlen + Streak + überfälligste hinaus) und vollständige Tropfen-Aktivierung, falls in Phase C zurückgestellt.

---

## 8. Offene Punkte (zur Klärung während/nach v3-Implementation)

| Punkt | Default / Richtung | Korrigierbar bis |
|---|---|---|
| **Echtes Logo / PWA-Icon-Set** | Temporäre Pixel-Platzhalter-Icons (maskable 192/512 px) ausliefern; finales Logo später via **Higgsfield MCP** in **eigener Iteration** generieren und Icons austauschen. | Nach v3 (Icon-Swap erfordert keinen Code-Change außer Asset-Ersatz) |
| **Reminder-Zeitzone** | **Fix `Europe/Berlin`** für alle User (nur Uhrzeit pro User wählbar). Per-User-TZ ist bewusst Non-Goal. | Designentscheidung — fix für v3 |
| **Resend-Tier (Free → Pro)** | **Free starten.** Upgrade auf **Pro**, sobald das Free-Limit (100 Mails/**Tag**) zum Engpass wird — Schwelle: wenn (tägliche Digest-Empfänger + Login-/Code-/Invite-/Email-Change-Mails) sich **100/Tag** nähert (Richtwert: ab ~70 aktiven täglichen Digest-Usern Upgrade einplanen). `email_service.py` bleibt provider-agnostisch, falls späterer Wechsel nötig. | Laufend, betrieblich |
| **Eigene Domain für Resend (SPF/DKIM)** | `getplantpal.com` bei Resend verifizieren (SPF + DKIM via Cloudflare-DNS), `RESEND_FROM_EMAIL` auf `…@getplantpal.com`. | Vor Production-Versand |
| **Stats-UI-Ausbaustufe** | Jetzt: Kernzahlen + Gieß-Streak + am-längsten-überfällige Pflanze. Konsistenz-%, Durchschnitts-Intervall, Heatmap/Charts: Backend liefert sie bereits, UI zieht später nach. | Iterativ nach v3 |
| **Tropfen-Wasserstands-Aktivierung** | Vollständig spezifiziert (Füllgrad = verstrichene Zeit / `interval_days`; welke Blüte + Tage-überfällig ab Überfälligkeit). Rendering-Tiefe in Phase C nach Zeitbudget; Spec ist verbindlich für die spätere Aktivierung. | Phase C / Folge-Iteration |
| **`reminder_channel`** | Bleibt Spalte mit Default `'email'` (Forward-Compat). In v3 kein zweiter Kanal aktiv; keine UI dafür. | Bei späterem Bedarf |
| **Litestream** | Deaktiviert/optional; primäres Backup ist der tägliche Cron (`.backup` + `rsync` von DB **und** `data/images`). Litestream kann bei Bedarf als Zusatz reaktiviert werden. | Betrieblich |

---

## Anhang A — Schema-Delta-Überblick (Migration 002, normativ für diesen Baustein)

> Vollständige DDL + Indexe + Service-/Endpoint-Verträge liegen in den fachlichen Bausteinen (Plants/Historie/Stats, Auth). Hier nur der konsolidierte Überblick zur Orientierung. Migration ist **idempotent** und in `_migrations` getrackt; Datetimes naiv `Europe/Berlin` via `now_berlin()`/`to_iso()`; DB-Defaults werden von Python gesetzt, **nie** SQLite `datetime('now')` (UTC).

- **`waterings`** (neu): `id PK, plant_id FK→plants(id) ON DELETE CASCADE, user_id FK→users(id) ON DELETE CASCADE, watered_at TEXT, created_at TEXT`; Indexe `(plant_id, watered_at)`, `(user_id, watered_at)`. `/water` schreibt **eine Row** UND updated `plants.last_watered_at`.
- **`plants`**: `+ location_room TEXT` (nullable).
- **`users`**: `+ invite_quota INTEGER NOT NULL DEFAULT 3`, `+ locale TEXT NOT NULL DEFAULT 'de'`, `+ reminder_hour INTEGER NOT NULL DEFAULT 8`, `+ theme TEXT NOT NULL DEFAULT 'dark'`.
- **`invite_tokens`**: `+ max_uses INTEGER NOT NULL DEFAULT 1`, `+ used_count INTEGER NOT NULL DEFAULT 0`. **`invite_redemptions`** (neu): `id, invite_id FK, user_id FK, redeemed_at`.
- **`login_tokens`**: `+ code TEXT`, `+ attempt_count INTEGER NOT NULL DEFAULT 0`.
- **`email_change_requests`** (neu): `id, user_id FK, new_email, token_hash, code, expires_at, used_at, created_at`.

## Anhang B — Config-Delta-Überblick (`config.py`, normativ-orientierend)

> Neue zentrale Settings (Defaults), die v3 einführt; Feinheiten (Wertebereiche, exakte Limits) in den fachlichen Bausteinen.

- **Login-Code:** `LOGIN_CODE_LENGTH: int = 6`, `LOGIN_CODE_TTL_MIN: int = 30` (an Magic-Link-TTL gekoppelt), `LOGIN_CODE_MAX_ATTEMPTS: int = 5` (Lockout danach), `RL_LOGIN_CODE_VERIFY_IP: str = "10/m"`.
- **Invite-Ketten:** `INVITE_DEFAULT_QUOTA: int = 3`, `INVITE_DEFAULT_MAX_USES: int = 3`.
- **Email-Change:** `EMAIL_CHANGE_TTL_MIN: int = 30`, `RL_EMAIL_CHANGE: str = "3/h"` (pro User).
- **Reminder:** `REMINDER_HOUR_BERLIN` bleibt als **Default** für neue User (`reminder_hour`); Cron läuft jetzt **stündlich** und filtert auf `reminder_hour == aktuelle Berlin-Stunde`.
- **i18n:** `DEFAULT_LOCALE: str = "de"`, `SUPPORTED_LOCALES: list[str] = ["de", "en"]`.
- **Bewusst NICHT vorhanden:** keine `web-push`/VAPID-Settings, keine `slowapi`-Settings. Litestream-Settings bleiben (`LITESTREAM_ENABLED: bool = False`).

---

*(Ende des Bausteins „Overview, Goals, Milestones, Tech-Stack, Test-Strategie". Fachliche Bausteine — Auth, Plants/Historie/Stats, Frontend/PWA/i18n, Reminder, Recht/DSGVO, Deploy — liefern die ausführlichen F-… Requirements, AK-… Akzeptanzkriterien und vollständigen Schema-/Endpoint-/Config-Deltas.)*



# Teil 2 — Auth & Onboarding v3

## 2.A — Auth & Onboarding v3

**Status:** v3-Erweiterung (ERWEITERT M1 §4.1). Baseline: M1 ist implementiert (Magic-Link + Invite-Token (Einmal) + Sessions sliding/hard-cap + signed double-submit CSRF + SQLite-Rate-Limit + Token-Hashing via `hash_token(raw, settings)`).
**Quellen:** `docs/PRD_M1.md` §4.1/§8/§9, `migrations/001_initial.sql`, `src/plantpal/auth_service.py`, `src/plantpal/security.py`, `src/plantpal/rate_limit.py`, `src/plantpal/errors.py`, `src/plantpal/config.py`, Decision-Log v3 §2/§8.

### Überblick & Delta gegen M1

| Thema | M1 (Baseline) | v3 (neu) |
|---|---|---|
| Wer lädt ein | Nur Admin, `POST /api/admin/invites` | **Jeder User**, `POST /api/invites` im normalen Settings-UI; Admin-Endpoint bleibt für Bonus-Quota |
| Invite-Form | Einmal-Token (`used_at`), 14 Tage | **Mehrfach-Link** mit `max_uses` + `used_count` + Ablauf; jede Einlösung als Row in `invite_redemptions` |
| Quota | — (Admin unbegrenzt) | **`users.invite_quota` Default 3**; verbrauchte Plätze = Summe ausgegebener `max_uses` offener/genutzter Invites; Enforcement bei Erzeugung |
| Login | Nur Magic-Link | **Zusätzlich 6-stelliger numerischer Code**; dieselbe Mail enthält Link UND Code; Eingabeseite `/login/code`; Flow request → verify |
| Login-Härtung | Rate-Limit pro Email/IP | Code zusätzlich: **an `login_token` + Email gebunden, kurze TTL (10 min), Lockout nach N Fehlversuchen pro Token, globaler Brute-Force-Schutz pro Email/IP** |
| Email ändern | Out-of-Scope (M1 §12) | **Request → Verify-Mail an NEUE Adresse → Confirm**; alte Adresse erhält Security-Notice; Sessions optional bleiben gültig |

Konventionsbindung (gilt für alle FRs hier): Tokens/Codes werden NIE im Klartext gespeichert — nur `hash_token(raw, settings)` (HMAC-SHA256 mit `TOKEN_PEPPER`) landet in der DB; der numerische Code wird ebenfalls gehasht gespeichert (`hash_token(str(code), settings)`). Alle Zeiten naiv Berlin via `now_berlin()`/`to_iso()`/`from_iso()`. Single-use/Atomic-Consume race-safe via konditionalem `UPDATE … WHERE used_at IS NULL …` + `rowcount`-Check (wie M1 F-AUTH-5). Email normalisiert via `normalize_email()`. Cross-User/Existenz-Leaks vermieden (generische Antworten). Alle mutierenden Endpoints unter Auth zusätzlich CSRF-pflichtig (`require_csrf`); die unauthenticated Auth-Endpoints (`/auth/*`) sind cookie-los und damit CSRF-frei, aber rate-limit-pflichtig.

---

### 2.A.1 Invite-Ketten & Mehrfach-Invite-Links

| Req | Beschreibung |
|---|---|
| **F-AUTH-13** | **Invite-Erzeugung durch jeden User:** `POST /api/invites` (Auth + CSRF). Body `{ max_uses?, expires_in_days? }`. `max_uses` Default 1, Range 1–20; `expires_in_days` Default = `INVITE_TOKEN_TTL_DAYS` (14), Range 1–90. Erzeugt `invite_tokens`-Row mit `created_by_user_id = current_user.id`, `token_hash = hash_token(raw)`, `max_uses`, `used_count=0`, `expires_at = now_berlin() + expires_in_days`. Response `{ invite_url, max_uses, used_count: 0, expires_at }` (Klartext-Token NUR hier in der URL, danach nie wieder abrufbar). |
| **F-AUTH-14** | **Quota-Enforcement:** Vor dem Insert wird der „belegte" Kontingent-Verbrauch des Users berechnet: `consumed = SUM(max_uses)` über alle `invite_tokens` des Users, die NICHT `revoked_at IS NOT NULL` UND NICHT (`expires_at <= now`)) sind — d.h. offene, noch (teilweise) gültige Invites zählen mit ihrer vollen `max_uses`. Wenn `consumed + new.max_uses > users.invite_quota`: `403 invite_quota_exceeded` mit `message` „Du hast dein Einladungs-Kontingent erreicht." Die Prüfung läuft unter `BEGIN IMMEDIATE` zusammen mit dem Insert (kein TOCTOU-Race über zwei parallele Requests). Admins (`is_admin=1`) sind von der Quota ausgenommen (unbegrenzt). |
| **F-AUTH-15** | **Quota-Recovery:** Revoke (F-AUTH-18) und Ablauf geben Kontingent frei (sie fallen aus der `consumed`-Summe). `invite_quota` ist pro User in der DB hinterlegt (`users.invite_quota`, Default 3) und kann von einem Admin via CLI erhöht werden (`set-invite-quota --email <addr> --quota <n>`). Es gibt keinen API-Endpoint zum Selbst-Erhöhen. |
| **F-AUTH-16** | **Mehrfach-Einlösung & Redemption-Tracking:** `POST /auth/register` (erweitert M1 F-AUTH-3) validiert das Invite über `token_hash`: existiert? nicht `revoked_at`? `expires_at > now`? `used_count < max_uses`? Bei Erfolg in EINER `BEGIN IMMEDIATE`-Transaktion: (1) User-Insert (`is_admin=0`, `invite_quota = DEFAULT 3`), (2) atomarer Verbrauch `UPDATE invite_tokens SET used_count = used_count + 1 WHERE id = ? AND revoked_at IS NULL AND expires_at > ? AND used_count < max_uses` mit `rowcount==1`-Check, (3) Insert `invite_redemptions (invite_id, user_id, redeemed_at)`, (4) `used_at` wird gesetzt, sobald `used_count == max_uses` erreicht ist (Backward-Compat zur M1-Spalte; ein voll ausgeschöpfter Link ist „used"). Danach Login-Token + Magic-Link/Code-Mail (siehe 2.A.3) für den frisch angelegten User. |
| **F-AUTH-17** | **Fehlerfälle Register/Invite:** ungültig/unbekannt → `400 invalid_invite`; widerrufen → `409 invite_revoked`; abgelaufen → `410 invite_expired`; Kontingent erschöpft (`used_count >= max_uses`) → `409 invite_exhausted`; Email existiert bereits → `409 user_exists` („Sign in instead."). Bei `rowcount != 1` im Consume (Race zweier Einlösungen um den letzten Platz): Rollback + `409 invite_exhausted`. Antworten sind generisch genug, dass kein Klartext-Token oder Ersteller geleakt wird. |
| **F-AUTH-18** | **Invite-Verwaltung im User-UI:** `GET /api/invites` listet die eigenen Invites: `{ id, max_uses, used_count, expires_at, revoked_at, created_at, status }` mit `status ∈ {active, exhausted, expired, revoked}` (derived). `POST /api/invites/{id}/revoke` (Auth + CSRF) setzt `revoked_at = now_berlin()` NUR wenn `created_by_user_id == current_user.id`; fremde/unbekannte ID → `404` (kein Existenz-Leak). Klartext-Token wird in `GET` NIE zurückgegeben. Eine Redemption-Zahl (`used_count`) genügt fürs UI; die einzelnen `invite_redemptions` sind nicht user-exponiert (Privacy: Eingeladene bleiben anonym). |

**Schema-Delta (Migration 002) — Invites & Quota:**
```sql
-- users: per-user Einladungs-Kontingent
ALTER TABLE users ADD COLUMN invite_quota INTEGER NOT NULL DEFAULT 3;

-- invite_tokens: von Einmal-Token zu Mehrfach-Link
ALTER TABLE invite_tokens ADD COLUMN max_uses   INTEGER NOT NULL DEFAULT 1;
ALTER TABLE invite_tokens ADD COLUMN used_count INTEGER NOT NULL DEFAULT 0;

-- Bestehende Indizes/Constraints von 001 bleiben. used_at behält
-- Backward-Compat-Bedeutung: gesetzt, sobald used_count == max_uses.

CREATE TABLE invite_redemptions (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  invite_id    INTEGER NOT NULL,
  user_id      INTEGER NOT NULL,
  redeemed_at  TEXT NOT NULL,
  FOREIGN KEY (invite_id) REFERENCES invite_tokens(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id)   REFERENCES users(id)          ON DELETE CASCADE,
  UNIQUE (invite_id, user_id)   -- ein User kann denselben Link nur einmal einlösen
);
CREATE INDEX idx_invite_redemptions_invite ON invite_redemptions(invite_id);

-- Quota-Berechnung profitiert von einem Index über die offenen Invites des Erstellers:
CREATE INDEX idx_invites_by_creator ON invite_tokens(created_by_user_id)
  WHERE revoked_at IS NULL;
```
Die Migration ist idempotent (Existenzprüfung via `PRAGMA table_info` / `sqlite_master` vor `ALTER`/`CREATE`) und wird in `_migrations` getrackt (Konvention M1 §8). `ALTER TABLE … ADD COLUMN` mit `NOT NULL DEFAULT` füllt Bestandszeilen automatisch.

**Akzeptanzkriterien:**

| ID | Szenario | Test-Datei |
|---|---|---|
| AK-V3-AUTH-1 | **User erzeugt Invite:** Nicht-Admin User → `POST /api/invites {max_uses:3}` → 201 + `invite_url` + `used_count:0`. Token-Klartext erscheint NUR in dieser Response, nicht in DB (`SELECT token_hash`). | `tests/test_invites_v3.py::test_user_create_invite` |
| AK-V3-AUTH-2 | **Quota-Enforcement:** Default-Quota 3. User erzeugt Invite `max_uses=3` → ok. Zweiter `POST /api/invites {max_uses:1}` → `403 invite_quota_exceeded`. | `tests/test_invites_v3.py::test_quota_blocks_overcommit` |
| AK-V3-AUTH-3 | **Quota-Recovery durch Revoke:** Nach Revoke des ersten Invites ist erneutes Erzeugen (`max_uses<=3`) wieder erlaubt. | `tests/test_invites_v3.py::test_revoke_frees_quota` |
| AK-V3-AUTH-4 | **Mehrfach-Einlösung:** Invite `max_uses=2` → zwei verschiedene Emails registrieren erfolgreich; `used_count` geht 0→1→2; nach der zweiten Einlösung ist `used_at` gesetzt; eine dritte Registrierung → `409 invite_exhausted`. | `tests/test_invites_v3.py::test_multi_use_redemption` |
| AK-V3-AUTH-5 | **Redemption-Tracking:** Nach zwei Einlösungen existieren genau zwei `invite_redemptions`-Rows mit den korrekten `user_id`s und `invite_id`. | `tests/test_invites_v3.py::test_redemptions_recorded` |
| AK-V3-AUTH-6 | **Letzter-Platz-Race:** Zwei parallele `POST /auth/register` auf einem `max_uses=1`-Invite (verschiedene Emails) → genau einer 200, der andere `409 invite_exhausted`; `used_count` endet bei 1. | `tests/test_invites_v3.py::test_last_seat_race` |
| AK-V3-AUTH-7 | **Abgelaufenes Invite:** `expires_at` in Vergangenheit → Register → `410 invite_expired`; zählt nicht mehr zur Quota (neues Erzeugen wieder möglich). | `tests/test_invites_v3.py::test_expired_invite` |
| AK-V3-AUTH-8 | **Revoke nur eigene:** User A revokes Invite von User B → `404` (kein Existenz-Leak); Invite bleibt aktiv. | `tests/test_invites_v3.py::test_revoke_foreign_404` |
| AK-V3-AUTH-9 | **Admin ohne Quota-Cap:** Admin erzeugt Invite mit `max_uses=20` trotz vorhandener offener Invites → 201 (keine Quota-Prüfung). | `tests/test_invites_v3.py::test_admin_unlimited` |

---

### 2.A.2 6-stelliger Login-Code (Request / Verify, gehärtet)

Der Code ist eine **Alternative zum Magic-Link** für dasselbe Login-Event: `request_login_link` erzeugt EINEN `login_tokens`-Row, der BEIDE Wege bedient — der url-safe Klartext-Token landet im Link, ein zusätzlich erzeugter 6-stelliger numerischer Code (`100000`–`999999`, via `secrets.randbelow`) wird gehasht in derselben Row gespeichert (`login_tokens.code_hash`). Die Mail (siehe 2.A.3) enthält Link UND Code. Eingabeseite ist die SPA-Route `/login/code`.

| Req | Beschreibung |
|---|---|
| **F-AUTH-19** | **Code-Erzeugung an Magic-Link gekoppelt:** `request_login_link()` (M1) wird erweitert: zusätzlich zum url-safe Token wird ein 6-stelliger Code erzeugt und als `code_hash = hash_token(code, settings)` in derselben `login_tokens`-Row gespeichert. **TTL für Code = `LOGIN_CODE_TTL_MIN` (Default 10 min)**, separat und kürzer als die Link-TTL (30 min); umgesetzt über die ohnehin vorhandene `expires_at`-Spalte — der Code-Verify prüft zusätzlich `created_at + LOGIN_CODE_TTL_MIN > now`. Pro Email existiert sinnvollerweise immer der jüngste Token; ältere Tokens derselben Email werden beim Request optional invalidiert (`UPDATE login_tokens SET used_at = now WHERE email = ? AND used_at IS NULL`), damit der Nutzer nur den jüngsten Code eingeben muss. |
| **F-AUTH-20** | **Code-Request-Endpoint:** Es gibt KEINEN zweiten Request-Endpoint — `POST /auth/request-login { email }` (M1 F-AUTH-4) bedient beides. Antwort bleibt timing-konstant + generisch (Anti-Enumeration, M1). Frontend bietet nach dem Request den Link „Ich habe einen Code erhalten" → `/login/code?email=<prefill>`. |
| **F-AUTH-21** | **Code-Verify-Endpoint:** `POST /auth/verify-code { email, code }` (cookie-los, kein CSRF nötig). Ablauf in EINER `BEGIN IMMEDIATE`-Transaktion: (1) jüngsten offenen `login_tokens`-Row der Email laden (`WHERE email = ? AND used_at IS NULL ORDER BY created_at DESC LIMIT 1`); (2) wenn keiner → generischer Fail `400 invalid_code` (kein Enumeration-Signal); (3) Lockout-Check (F-AUTH-23); (4) `code_hash`-Vergleich konstant-zeitlich gegen `hash_token(code)`; (5) bei Mismatch: `attempt_count += 1`, commit, `400 invalid_code` (bzw. `429`/`423` bei Lockout); (6) bei Match + `created_at + LOGIN_CODE_TTL_MIN > now` + `used_at IS NULL`: atomarer Consume `UPDATE login_tokens SET used_at = ? WHERE id = ? AND used_at IS NULL` mit `rowcount==1`, Session anlegen (`_insert_session`), `users.last_login_at` updaten, commit; (7) Erfolg setzt Session-Cookie + CSRF-Cookie (wie M1 `_set_auth_cookies`) und liefert `200 { ok: true }` (SPA navigiert zu `/`). Abgelaufener Code (Row vorhanden, aber `created_at + LOGIN_CODE_TTL_MIN <= now`) → `410 code_expired`. |
| **F-AUTH-22** | **Brute-Force-Rate-Limits (global):** Zusätzlich zu M1 `RL_LOGIN_REQUEST_*`: `POST /auth/verify-code` ist rate-limit-pflichtig über `RL_LOGIN_CODE_VERIFY_IP` (Default `10/m`) UND `RL_LOGIN_CODE_VERIFY_EMAIL` (Default `5/m`). Limit-Hit → `429` + `Retry-After`. Das schützt vor verteiltem Raten unabhängig vom Per-Token-Lockout. |
| **F-AUTH-23** | **Per-Token-Lockout:** `login_tokens.attempt_count` zählt Fehlversuche gegen genau diesen Code. Bei `attempt_count >= LOGIN_CODE_MAX_ATTEMPTS` (Default 5) wird der Token gesperrt: weitere `verify-code`-Versuche für diese Email liefern `423 code_locked` („Zu viele Fehlversuche. Fordere einen neuen Code an."), bis der User via `request-login` einen neuen Token erzeugt. Der Lockout invalidiert NICHT automatisch den Magic-Link-Pfad desselben Tokens nicht — Sicherheits-konservativ wird beim Erreichen des Lockouts der gesamte Token verbrannt (`used_at = now`), sodass auch der Link tot ist. So kostet Raten am Code maximal `LOGIN_CODE_MAX_ATTEMPTS` Versuche pro ausgestelltem Token. |
| **F-AUTH-24** | **Kein Enumeration-/Timing-Leak:** `verify-code` antwortet bei „kein Token für Email" und bei „falscher Code" mit identischem `400 invalid_code` und Body. Der Code-Vergleich nutzt `constant_time_equal`. Es wird nicht verraten, ob die Email existiert, ob ein Token offen ist, oder wie viele Versuche verbleiben (numerischer Verbleib NICHT im Body). |
| **F-AUTH-25** | **Entropie/Format:** Code ist exakt 6 Dezimalstellen, führende Nullen erlaubt (Range `000000`–`999999`, gleichverteilt via `secrets.randbelow(1_000_000)`, zero-padded). Mit Lockout=5 und TTL=10 min ist die Online-Rate-Erfolgswahrscheinlichkeit ≤ 5·10⁻⁶ pro Token — akzeptabel. Eingabe serverseitig validiert (`^\d{6}$`), sonst `400 invalid_code` ohne `attempt_count`-Inkrement (Format-Fehler zählt nicht als Versuch). |

**Endpoint-Spec — `POST /auth/verify-code`:**
```
Request:  { "email": "user@example.com", "code": "042913" }
Auth:     none (cookie-los).  CSRF: none.
Rate:     RL_LOGIN_CODE_VERIFY_IP (10/m) + RL_LOGIN_CODE_VERIFY_EMAIL (5/m)
Success:  200 { "ok": true }  + Set-Cookie: plantpal_session, plantpal_csrf
Errors:   400 invalid_code      (kein Token / falscher Code / Format)
          410 code_expired      (Token vorhanden, Code-TTL überschritten)
          423 code_locked       (attempt_count >= LOGIN_CODE_MAX_ATTEMPTS)
          403 user_disabled     (User status != 'active')
          429 rate_limited      (+ Retry-After)
```

**Schema-Delta (Migration 002) — Login-Code:**
```sql
ALTER TABLE login_tokens ADD COLUMN code_hash     TEXT;                    -- HMAC des 6-stelligen Codes; NULL = kein Code (Altzeilen)
ALTER TABLE login_tokens ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0;
-- expires_at (Link-TTL 30m) existiert; Code-TTL 10m wird relativ zu created_at geprüft.
-- idx_login_tokens_email (email, created_at) aus 001 deckt das "jüngster offener Token"-Lookup ab.
```

**Config-Delta (`config.py`):**
```python
# Login-Code (6-stellig, Alternative zum Magic-Link)
LOGIN_CODE_TTL_MIN: int = 10          # kürzer als LOGIN_TOKEN_TTL_MIN (30)
LOGIN_CODE_MAX_ATTEMPTS: int = 5      # Per-Token-Lockout-Schwelle
RL_LOGIN_CODE_VERIFY_IP: str = "10/m"
RL_LOGIN_CODE_VERIFY_EMAIL: str = "5/m"
```
`validate_runtime()` ergänzen: `LOGIN_CODE_TTL_MIN >= 1`, `LOGIN_CODE_TTL_MIN <= LOGIN_TOKEN_TTL_MIN`, `LOGIN_CODE_MAX_ATTEMPTS >= 1`.

**Akzeptanzkriterien:**

| ID | Szenario | Test-Datei |
|---|---|---|
| AK-V3-AUTH-10 | **Code-Happy-Path:** `request-login` → DB-Row hat `code_hash != NULL`; bekannter Code → `POST /auth/verify-code` → 200 + Session-Cookie + CSRF-Cookie gesetzt; `/api/me` mit dem Cookie → 200. | `tests/test_login_code.py::test_code_happy` |
| AK-V3-AUTH-11 | **Falscher Code inkrementiert:** Falscher Code → `400 invalid_code`; `login_tokens.attempt_count` ist 1. Body verrät keine Verbleib-Zahl. | `tests/test_login_code.py::test_wrong_code_increments` |
| AK-V3-AUTH-12 | **Lockout nach N:** 5 falsche Versuche → 5. Antwort `400`, der 6. Versuch (auch mit RICHTIGEM Code) → `423 code_locked`; Token ist verbrannt (`used_at` gesetzt), der zugehörige Magic-Link `GET /auth/verify` → `410/409`. | `tests/test_login_code.py::test_lockout_burns_token` |
| AK-V3-AUTH-13 | **Code-TTL:** Token 11 min alt (Code-TTL 10) → richtiger Code → `410 code_expired`; Magic-Link desselben Tokens (Link-TTL 30) bei 11 min noch gültig → `303`/Login ok. | `tests/test_login_code.py::test_code_ttl_independent_of_link` |
| AK-V3-AUTH-14 | **Single-use:** Erfolgreicher Code-Login → erneuter `verify-code` mit gleichem Code → `400 invalid_code` (Token `used_at` gesetzt, kein zweiter Session-Mint). | `tests/test_login_code.py::test_code_single_use` |
| AK-V3-AUTH-15 | **Anti-Enumeration:** `verify-code` für nicht-existente Email und für existente Email mit falschem Code liefern identischen Status/Body (`400 invalid_code`). | `tests/test_login_code.py::test_no_enumeration` |
| AK-V3-AUTH-16 | **Brute-Force-Rate-Limit:** 6. `verify-code` für dieselbe Email innerhalb 1 min → `429` + `Retry-After` (greift vor/zusätzlich zum Per-Token-Lockout). | `tests/test_login_code.py::test_email_rate_limit` |
| AK-V3-AUTH-17 | **Format-Validierung zählt nicht:** `code="abc"` bzw. `"123"` → `400 invalid_code`, aber `attempt_count` bleibt unverändert. | `tests/test_login_code.py::test_bad_format_no_attempt` |
| AK-V3-AUTH-18 | **Code an Email gebunden:** Gültiger Code von Email A gegen Email B → `400 invalid_code` (kein Login). | `tests/test_login_code.py::test_code_bound_to_email` |

---

### 2.A.3 Login-Mail mit Link UND Code

| Req | Beschreibung |
|---|---|
| **F-AUTH-26** | **Mail-Inhalt:** Die Magic-Link-Mail (M1 F-MAIL-9) wird erweitert: sie enthält BEIDE — den Login-Button/Link UND den 6-stelligen Code groß/monospace dargestellt, plus Hinweistext „Code gültig 10 Minuten, Link gültig 30 Minuten, jeweils einmalig." `email_service.send_magic_link(settings, email, login_url, code)` bekommt den Code als zusätzliches Argument; Plaintext- und HTML-Teil zeigen beides. Lokalisierung gemäß `users.locale` (DE/EN, v3 i18n-Baustein). |
| **F-AUTH-27** | **CLI-Parität:** `python -m plantpal.cli issue-login-link --email <addr>` (M1 F-AUTH-11) druckt zusätzlich den Code in stdout (Fallback ohne Resend). |

**Akzeptanzkriterium:**

| ID | Szenario | Test-Datei |
|---|---|---|
| AK-V3-AUTH-19 | **Mail enthält Code:** `request-login` → gemockter `send_magic_link` wird mit nicht-leerem 6-stelligem `code` und korrekter `login_url` aufgerufen; der übergebene Code verifiziert erfolgreich gegen die DB-Row. | `tests/test_login_code.py::test_mail_carries_code` |

---

### 2.A.4 Email-Adresse ändern (Request → Verify an neue Adresse → Confirm)

Doppelt bestätigter Wechsel: ein eingeloggter User fordert die neue Adresse an; ein Bestätigungs-Link **und** ein 6-stelliger Code gehen an die NEUE Adresse; erst die Bestätigung übernimmt die Adresse. Die ALTE Adresse erhält parallel eine Security-Notice (kein Bestätigungs-Recht, nur Information + Hinweis bei unautorisierter Änderung).

| Req | Beschreibung |
|---|---|
| **F-AUTH-28** | **Request:** `POST /api/account/email { new_email }` (Auth + CSRF, Rate `RL_EMAIL_CHANGE_USER` Default `3/h`). Validierung: `new_email` ist valide (`EmailStr`), `normalize_email(new_email) != current.email`, und es existiert noch kein aktiver User mit dieser Adresse → sonst `409 email_taken` (generisch, da der Requester ohnehin eingeloggt ist, ist hier kein Enumeration-Risiko Dritter). Erzeugt `email_change_requests`-Row: `user_id`, `new_email` (normalisiert), `token_hash = hash_token(raw)`, `code_hash = hash_token(code)`, `expires_at = now + EMAIL_CHANGE_TTL_MIN` (Default 30), `attempt_count=0`, `used_at=NULL`. Offene frühere Requests desselben Users werden invalidiert (`used_at = now`). Antwort `200 { ok: true }`. |
| **F-AUTH-29** | **Verify-Mail an NEUE Adresse:** `email_service.send_email_change_verify(settings, new_email, confirm_url, code)` schickt an die NEUE Adresse: Bestätigungs-Link `GET /api/account/email/confirm?token=<raw>` (Browser-Flow) UND den 6-stelligen Code (für `POST /api/account/email/confirm`). Parallel `email_service.send_email_change_notice(settings, old_email, new_email)` an die ALTE Adresse: „Es wurde eine Änderung deiner PlantPal-Email zu <maskiert> beantragt. Warst du das nicht, ignoriere diese Mail / ändere die Adresse zurück." (rein informativ, kein Aktions-Link). |
| **F-AUTH-30** | **Confirm:** Zwei Wege auf denselben Row: (a) `GET /api/account/email/confirm?token=<raw>` (Klick aus der neuen-Adresse-Mail; Auth NICHT zwingend, da der Besitz des Tokens den Besitz der neuen Mailbox beweist; race-safe Consume) und (b) `POST /api/account/email/confirm { code }` (Auth + CSRF, eingeloggter User gibt Code ein). Beide: Lockout-Check (`attempt_count >= EMAIL_CHANGE_MAX_ATTEMPTS`, Default 5 → `423`), Ablauf-Check (`410 change_expired`), bei Erfolg atomarer Consume `UPDATE email_change_requests SET used_at = ? WHERE id = ? AND used_at IS NULL` (`rowcount==1`) + `UPDATE users SET email = ? WHERE id = ?` in EINER `BEGIN IMMEDIATE`-Transaktion. Schlägt das User-Update an `UNIQUE(email)` fehl (Adresse wurde zwischenzeitlich vergeben) → Rollback + `409 email_taken`. Erfolg: `200 { ok: true, email: new_email }` (Browser-Flow: `303` → `/settings?email_changed=1`). Falscher Code → `attempt_count += 1`, `400 invalid_code`. |
| **F-AUTH-31** | **Session-/Token-Hygiene:** Bei erfolgreicher Änderung bleiben bestehende Sessions des Users gültig (User-ID unverändert), ABER alle offenen `login_tokens` der ALTEN Email werden invalidiert (`used_at = now WHERE email = old AND used_at IS NULL`), damit alte Magic-Links/Codes nicht mehr greifen. Die neue Adresse ist ab sofort für `request-login` zuständig. |
| **F-AUTH-32** | **Anti-Enumeration & Leak:** `new_email` in der Notice an die alte Adresse wird maskiert dargestellt (z.B. `j***@example.com`). `confirm`-Fehler verraten nicht, ob ein Request offen ist (`400 invalid_code` / `410 change_expired` generisch). Der `GET …/confirm`-Link ist single-use + TTL-begrenzt + gehasht gespeichert (analog Magic-Link). |

**Endpoint-Specs — Email-Change:**
```
POST /api/account/email           Auth+CSRF, Rate 3/h
   Body { "new_email": "new@example.com" }
   200 { ok:true } | 409 email_taken | 422 validation_error | 429 rate_limited

GET  /api/account/email/confirm?token=<raw>     (cookie-los erlaubt; Besitz=Beweis)
   303 → /settings?email_changed=1 | 410 change_expired | 423 code_locked | 400 invalid_token | 409 email_taken

POST /api/account/email/confirm   Auth+CSRF
   Body { "code": "042913" }
   200 { ok:true, email:"new@example.com" } | 400 invalid_code | 410 change_expired
   | 423 code_locked | 409 email_taken
```

**Schema-Delta (Migration 002) — Email-Change:**
```sql
CREATE TABLE email_change_requests (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id       INTEGER NOT NULL,
  new_email     TEXT NOT NULL COLLATE NOCASE,
  token_hash    TEXT NOT NULL UNIQUE,            -- HMAC des Bestätigungs-Link-Tokens
  code_hash     TEXT NOT NULL,                   -- HMAC des 6-stelligen Codes
  attempt_count INTEGER NOT NULL DEFAULT 0,
  expires_at    TEXT NOT NULL,
  used_at       TEXT,
  created_at    TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX idx_email_change_open ON email_change_requests(user_id) WHERE used_at IS NULL;
```

**Config-Delta (`config.py`):**
```python
# Email-Adresse ändern
EMAIL_CHANGE_TTL_MIN: int = 30
EMAIL_CHANGE_MAX_ATTEMPTS: int = 5
RL_EMAIL_CHANGE_USER: str = "3/h"
```

**Akzeptanzkriterien:**

| ID | Szenario | Test-Datei |
|---|---|---|
| AK-V3-AUTH-20 | **Happy-Path Code:** Eingeloggter User `POST /api/account/email {new_email}` → 200; Verify-Mail an NEUE Adresse gemockt (mit Code); `POST …/confirm {code}` → 200 + `users.email` ist neu. | `tests/test_email_change.py::test_change_via_code` |
| AK-V3-AUTH-21 | **Happy-Path Link:** Wie oben, aber Bestätigung via `GET …/confirm?token=<raw>` (ohne Cookie) → `303` → `users.email` neu. | `tests/test_email_change.py::test_change_via_link` |
| AK-V3-AUTH-22 | **Notice an alte Adresse:** Beim Request wird `send_email_change_notice` mit der ALTEN Adresse und maskierter neuer Adresse aufgerufen. | `tests/test_email_change.py::test_old_address_notice` |
| AK-V3-AUTH-23 | **Kollision:** Zweiter aktiver User hat bereits `new_email` → Request → `409 email_taken`; `users.email` unverändert. | `tests/test_email_change.py::test_email_taken_on_request` |
| AK-V3-AUTH-24 | **Race auf Adresse:** Adresse wird NACH Request, VOR Confirm vergeben → Confirm → `409 email_taken` (UNIQUE-Verletzung sauber abgefangen, Rollback). | `tests/test_email_change.py::test_email_taken_on_confirm` |
| AK-V3-AUTH-25 | **TTL:** Request-Row 31 min alt (TTL 30) → Confirm → `410 change_expired`. | `tests/test_email_change.py::test_change_ttl` |
| AK-V3-AUTH-26 | **Lockout:** 5 falsche Codes → 6. Confirm-Versuch → `423 code_locked`. | `tests/test_email_change.py::test_change_lockout` |
| AK-V3-AUTH-27 | **Alte Login-Tokens tot:** Nach erfolgreichem Wechsel sind offene `login_tokens` der alten Email invalidiert; ein vor dem Wechsel angeforderter Magic-Link der alten Adresse → `410/409`. Login via NEUER Adresse (`request-login` → `verify`/`verify-code`) funktioniert. | `tests/test_email_change.py::test_old_tokens_invalidated` |
| AK-V3-AUTH-28 | **Single-use Confirm:** Erfolgreicher Confirm → erneuter Confirm mit gleichem Token/Code → `400 invalid_code`/`410` (kein zweiter Wechsel). | `tests/test_email_change.py::test_confirm_single_use` |

---

### 2.A.5 DB-Hygiene-Erweiterung (Housekeeping)

| Req | Beschreibung |
|---|---|
| **F-AUTH-33** | Der tägliche Housekeeping-Cron (Decision-Log §1) löscht zusätzlich zu M1: abgelaufene/aufgebrauchte `invite_tokens` (`expires_at < now` ODER (`used_count >= max_uses`)) inkl. ihrer `invite_redemptions` (FK CASCADE), abgelaufene/aufgebrauchte `login_tokens` (inkl. `code_hash`-Rows), und abgelaufene/benutzte `email_change_requests` (`used_at IS NOT NULL` ODER `expires_at < now`). Implementiert als parametrisierte `DELETE`s in `reminder_service`/`housekeeping`-Job; idempotent. |

**Akzeptanzkriterium:**

| ID | Szenario | Test-Datei |
|---|---|---|
| AK-V3-AUTH-29 | **Housekeeping räumt Auth-Artefakte:** Nach Housekeeping-Run sind abgelaufene `invite_tokens`, voll ausgeschöpfte Invites, abgelaufene `login_tokens` und benutzte `email_change_requests` entfernt; aktive Sessions/offene Invites bleiben. | `tests/test_housekeeping.py::test_auth_cleanup` |

---

### 2.A.6 Endpoint-Übersicht (Auth v3, neu/geändert)

| Methode | Pfad | Auth | CSRF | Rate-Limit | Zweck |
|---|---|---|---|---|---|
| POST | `/auth/request-login` | — | — | `3/email/h` + `10/ip/h` | Login: Link **und** Code erzeugen+mailen (M1, erweitert) |
| GET | `/auth/verify?token=` | — | — | `10/ip/m` | Magic-Link-Login (M1, unverändert) |
| POST | `/auth/verify-code` | — | — | `10/ip/m` + `5/email/m` | **NEU** 6-stelligen Code einlösen |
| POST | `/auth/register` | — | — | `10/ip/h` | Invite-Register, Mehrfach-Link (M1-Endpoint, erweitert) |
| POST | `/api/invites` | ✔ | ✔ | `30/user/m` | **NEU** Invite (Mehrfach-Link) erzeugen, Quota-geprüft |
| GET | `/api/invites` | ✔ | — | — | **NEU** eigene Invites + `used_count`/Status listen |
| POST | `/api/invites/{id}/revoke` | ✔ | ✔ | `30/user/m` | **NEU** eigenes Invite widerrufen |
| POST | `/api/account/email` | ✔ | ✔ | `3/user/h` | **NEU** Email-Änderung anfordern |
| GET | `/api/account/email/confirm?token=` | — | — | `10/ip/m` | **NEU** Email-Änderung per Link bestätigen |
| POST | `/api/account/email/confirm` | ✔ | ✔ | `30/user/m` | **NEU** Email-Änderung per Code bestätigen |
| POST | `/api/admin/invites` | admin | ✔ | `30/user/m` | M1, bleibt (Admin-Invites, keine Quota) |

Neue Endpoint-Zahl: M1 hat 18 Endpoints; v3-Auth fügt 6 hinzu (`verify-code`, `POST/GET /api/invites`, `invites/{id}/revoke`, `POST /api/account/email`, `GET+POST …/email/confirm` = 6 neue), bleibt unter der „Domain-Split bei >8 Endpoints im selben File"-Schwelle pro Domain — Routes bleiben in `main.py` (M1-Konvention), Logik in `auth_service.py` (Invites/Code) bzw. neuem schlanken `account_service.py`-Block oder als Erweiterung von `auth_service.py`.

---

### 2.A.7 Models-Delta (`models.py`)

```python
# --- Invites (User-UI) ---
class InviteCreateRequest(BaseModel):           # ersetzt M1-Admin-only-Variante für /api/invites
    max_uses: int = Field(default=1, ge=1, le=20)
    expires_in_days: int | None = Field(default=None, ge=1, le=90)

class InviteResponse(BaseModel):
    invite_url: str
    max_uses: int
    used_count: int
    expires_at: str

class InviteListItem(BaseModel):
    id: int
    max_uses: int
    used_count: int
    expires_at: str
    revoked_at: str | None
    created_at: str
    status: str                                  # active | exhausted | expired | revoked

# --- Login-Code ---
class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")

# --- Email-Change ---
class EmailChangeRequest(BaseModel):
    new_email: EmailStr

class EmailChangeConfirm(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")
```

---

### 2.A.8 Sicherheits-/Failure-Mode-Ergänzungen

| # | Failure / Angriff | Mitigation v3 |
|---|---|---|
| A1 | **Online-Brute-Force des 6-stelligen Codes** | Per-Token-Lockout (5 Versuche, F-AUTH-23) + Email/IP-Rate-Limit (F-AUTH-22) + kurze TTL (10 min) + Token-Verbrennung beim Lockout. Effektive Rate-Erfolgswahrscheinlichkeit ≤ 5·10⁻⁶/Token. |
| A2 | **Invite-Quota-Umgehung via Parallel-Requests** | `BEGIN IMMEDIATE` um Quota-Berechnung + Insert (F-AUTH-14): serialisierter Writer (Decision-Log §1), kein TOCTOU. |
| A3 | **Doppel-Einlösung des letzten Invite-Platzes** | Atomarer `UPDATE … WHERE used_count < max_uses` + `rowcount==1` (F-AUTH-16/17). |
| A4 | **Account-Übernahme via Email-Change** | Doppelte Bestätigung (Besitz der neuen Mailbox via Link/Code), Security-Notice an alte Adresse, Lockout, kurze TTL, UNIQUE-Race sauber abgefangen (F-AUTH-28..32). |
| A5 | **Enumeration über Code-/Change-Fehler** | Generische `400 invalid_code`, konstant-zeitlicher Vergleich, keine Verbleib-Zahlen im Body (F-AUTH-24, F-AUTH-32). |
| A6 | **Geleakter DB-Dump** | Codes/Tokens nur als HMAC (`code_hash`, `token_hash`); Klartext existiert nur transient in Mail/URL (M1-Konvention fortgeführt). |

---

**Sign-off-Hinweis (für dieses Modul):** Alle FRs F-AUTH-13…F-AUTH-33 sind ohne TBD spezifiziert; Schema-Deltas sind Teil der idempotenten Migration `002_v3.sql` (gemeinsam mit den übrigen v3-Modulen; in `_migrations` getrackt). Akzeptanzkriterien AK-V3-AUTH-1…29 sind backend-testbar via pytest + pytest-asyncio + httpx(ASGI) mit `db`(tmp_path)+`client`-Fixtures (`mode=auto`), inklusive Race-Tests (parallele Requests) und freezegun für TTL/Lockout.



# Teil 3 — Backend-Erweiterungen v3

# PlantPal PRD v3 — Baustein: Backend-Erweiterungen

> **Status:** v3 — Erweiterung der implementierten M1-Baseline (Decision-Log 2026-06-03).
> **Phase-Zuordnung:** Phase A (Schema + Backend). Voraussetzung für Phase B/C/D.
> **Konvention:** Erweitert M1, ersetzt nicht. Alle neuen Datetimes naiv Berlin (`now_berlin()`/`today_berlin()`), Soft-Delete via `is_active=0`, Token-Hash via HMAC mit `TOKEN_PEPPER`, parametrisierte SQL, Service-Funktionen `async def f(db: aiosqlite.Connection, ...)`, Routes in `main.py`, Migration `002` idempotent in `_migrations` getrackt.

---

## B.0 Scope & Prinzip

Dieser Baustein liefert die Backend-Substanz für v3: **Gieß-Historie**, **reichhaltige Stats**, **Standort/Raum mit Gruppierung**, **tägliches Housekeeping (DB-Hygiene-Cron)**, **DB-Concurrency (WAL + parallele Reads / ein Writer)**, **strukturiertes Logging + erweiterter Healthcheck** und **DSGVO-Daten-Export (JSON + Bilder als ZIP)**.

**Leitprinzip (verbindlich, Decision-Log §3):** Das Backend wird **vollständig, sauber und getestet** gebaut — **auch die Teile, die das Frontend (Phase C) zunächst nicht anzeigt**. Reichhaltige Stats (Streak, Konsistenz %, am-längsten-überfällig, Avg-Intervall) sind komplett spezifiziert, implementiert und durch Unit-Tests abgedeckt; das Frontend zeigt davon in v3 nur eine Teilmenge (Kernzahlen + Streak + am-längsten-überfällig). Die Stats-Berechnung lebt im Service-Layer und ist unabhängig vom HTTP-Response testbar.

**Nicht-Ziele dieses Bausteins:** Auth-Erweiterungen (Login-Code, Email-Change, Multi-Use-Invites → Phase B), Frontend/i18n/PWA (Phase C), Deploy/cloudflared/Legal-Seiten (Phase D). Schema-Deltas für Auth/Invite (`login_tokens.code`, `email_change_requests`, `invite_tokens.max_uses` etc.) gehören in **dieselbe Migration 002**, werden aber in den jeweiligen Phase-B-Bausteinen funktional beschrieben; hier werden nur die backend-eigenen Tabellen `waterings` und die Spalten `plants.location_room`, `users.locale|reminder_hour|theme|invite_quota` plus das `reminder_hour`-Verhalten des Reminder-Crons (Cross-Referenz Phase B/Reminder) angefasst.

---

## B.1 Gieß-Historie (`waterings`)

### Funktionale Requirements

| Req | Beschreibung |
|---|---|
| **F-HIST-1** | **Neue Tabelle `waterings`** (Schema-Delta B.8). Eine Zeile = ein Gieß-Ereignis: `plant_id`, `user_id`, `watered_at` (naiv Berlin), `created_at`. `user_id` wird denormalisiert mitgeschrieben (kein JOIN über `plants` für User-Scope-Stats/Export nötig und überlebt Plant-Hard-Delete-Rollback nicht — siehe F-HIST-4). |
| **F-HIST-2** | **`/water` schreibt Historie UND updated `plants.last_watered_at`** in **einer** Transaktion: erst `INSERT INTO waterings`, dann `UPDATE plants SET last_watered_at = ?`, mit identischem `now_berlin()`-Zeitstempel für beide. Ist die Plant nicht vorhanden/nicht `is_active=1`/cross-user → `404 plant_not_found`, **kein** `waterings`-Insert. Bestehende `plant_service.water_plant()` wird entsprechend erweitert; Signatur und 404-Verhalten (rowcount-Check) bleiben. |
| **F-HIST-3** | **Backfill-Eintrag beim Anlegen:** `POST /api/plants` setzt wie in M1 `last_watered_at = now_berlin()` und schreibt **eine** korrespondierende `waterings`-Zeile (Annahme aus M1 F-PLANT-2: User legt direkt nach Gießen an). So ist die Historie ab Tag 1 konsistent mit `last_watered_at`. Schlägt der Bild-Upload fehl und die Plant wird zurückgerollt (`hard_delete_plant`), entfernt **FK `ON DELETE CASCADE`** die `waterings`-Zeile automatisch — kein verwaister Historien-Eintrag. |
| **F-HIST-4** | **Soft-Delete:** Soft-Delete einer Pflanze (`is_active=0`) **behält** die `waterings`-Zeilen (für Undo, F-PLANT-Restore in Phase C, und für Account-Export). Verlaufs-Endpoint liefert für soft-deletete Pflanzen `404`. **Hard-Delete** (Account-Löschung) entfernt `waterings` per FK-Cascade über `users`. |
| **F-HIST-5** | **Verlaufs-Endpoint** `GET /api/plants/{id}/waterings`: liefert die Gieß-Ereignisse **einer** Pflanze, neueste zuerst (`ORDER BY watered_at DESC, id DESC`). User-scoped: cross-user oder nicht-existent → `404 plant_not_found`. **Keine Pagination** (Decision-Log §1): vollständige Liste; bei sehr alten Accounts via Index performant. Response: `{ "items": [WateringResponse, ...], "count": <int> }`. |
| **F-HIST-6** | **`WateringResponse`-Schema:** `{ id: int, watered_at: str, created_at: str }`. `plant_id`/`user_id` werden im Single-Plant-Endpoint nicht wiederholt (redundant zum Pfad). |
| **F-HIST-7** | **Konsistenz-Invariante:** `plants.last_watered_at` ist **immer** gleich dem `MAX(watered_at)` der zugehörigen nicht-zurückgerollten `waterings`-Zeilen (garantiert durch F-HIST-2/3, gemeinsame Transaktion). Diese Invariante wird in Tests verifiziert (AK-HIST-3). |
| **F-HIST-8** | **Mehrfach-Gießen pro Tag erlaubt** (M1 F-WATER-4, kein Lock): jeder `/water`-Klick erzeugt eine eigene `waterings`-Zeile, auch mehrfach am selben Tag. Stats mit Tagesgranularität (B.2) deduplizieren bei Bedarf selbst auf Kalendertag. |

### Akzeptanzkriterien

| ID | Szenario | Test-Datei |
|---|---|---|
| **AK-HIST-1** | `POST /api/plants/{id}/water` → `200` + Plant-Response; danach `GET /api/plants/{id}/waterings` enthält **genau eine** zusätzliche Zeile mit `watered_at == plants.last_watered_at`. | `tests/test_watering_history.py::test_water_writes_history` |
| **AK-HIST-2** | Neu angelegte Pflanze → `GET …/waterings` liefert `count == 1` (Backfill F-HIST-3) mit `watered_at == created_at`-Tag. | `tests/test_watering_history.py::test_create_backfills_history` |
| **AK-HIST-3** | Drei `/water`-Calls an verschiedenen Tagen (freezegun) → Historie hat 4 Zeilen (1 Backfill + 3), `DESC` sortiert, `plants.last_watered_at == MAX(watered_at)`. | `tests/test_watering_history.py::test_history_invariant` |
| **AK-HIST-4** | User B ruft `GET /api/plants/{A_plant}/waterings` → `404` (kein Existenz-Leak, M1 F-AUTH-9). | `tests/test_watering_history.py::test_history_user_scope` |
| **AK-HIST-5** | Failed-Upload-Rollback bei Create: `waterings` hat **0** Zeilen für die zurückgerollte Plant-ID (FK-Cascade). | `tests/test_watering_history.py::test_history_rollback_no_orphan` |
| **AK-HIST-6** | Soft-Delete → `GET …/waterings` liefert `404`; DB enthält die Zeilen aber weiterhin (`SELECT COUNT` > 0). | `tests/test_watering_history.py::test_history_survives_soft_delete` |

---

## B.2 Reichhaltige Stats

Alle Stats sind **User-scoped** und werden **server-side derived** (kein gespeichertes Stats-Feld, analog M1 F-THIRST-3). Berechnungsbasis: aktive Pflanzen (`is_active=1`) + deren `waterings`-Historie. Granularität: **Kalendertag in Berlin** (M1 Thirsty-Mechanik). Die Berechnung lebt in `plant_service` als reine, einzeln testbare Funktionen.

### Funktionale Requirements

| Req | Beschreibung |
|---|---|
| **F-STAT-1** | **`total_plants`** — Anzahl aktiver Pflanzen (M1, unverändert). |
| **F-STAT-2** | **`thirsty_count`** — Anzahl aktuell durstiger aktiver Pflanzen (M1, unverändert). |
| **F-STAT-3** | **`watering_streak_days`** — **Gieß-Streak**: Anzahl aufeinanderfolgender Kalendertage **bis einschließlich heute (Berlin)**, an denen **mindestens eine** Pflanze gegossen wurde (irgendeine Pflanze des Users; ein Tag mit ≥1 `waterings`-Zeile zählt). Definition: betrachte die Menge distinkter Gieß-Kalendertage; zähle rückwärts ab heute, solange lückenlos. **Heute ohne Gießung bricht nicht ab, solange gestern gegossen wurde** — d.h. der Streak gilt als „lebendig", wenn entweder heute **oder** gestern gegossen wurde (Kulanz-Tag, damit ein noch nicht erledigter Gieß-Tag den Streak morgens nicht fälschlich auf 0 setzt). Wurde weder heute noch gestern gegossen → `0`. |
| **F-STAT-4** | **`watering_consistency_pct`** — **Gieß-Konsistenz** in Prozent (Integer 0–100, gerundet): Anteil der „erwarteten" Gießungen, die **rechtzeitig** erfolgten, über ein **30-Tage-Fenster** (`today − 29 … today`, Berlin). Pro aktiver Pflanze: erwartete Gieß-Slots im Fenster = `floor(30 / interval_days)` (mind. 0). Erfüllte Slots = Anzahl Kalendertage im Fenster mit ≥1 Gießung dieser Pflanze, gekappt auf die erwartete Slot-Zahl. `consistency = round(100 * sum(erfüllt) / sum(erwartet))`. **Sonderfall** `sum(erwartet) == 0` (keine Pflanze oder alle Intervalle > 30 → kein Slot im Fenster) → `consistency = 100` (nichts war fällig, also „perfekt"; nie Division durch 0). |
| **F-STAT-5** | **`longest_overdue`** — **am-längsten-überfällige Pflanze**: die aktive Pflanze mit dem größten `days_overdue` (M1-Derivation `thirsty_state`). Response-Objekt `{ plant_id: int, name: str, days_overdue: int }` **oder `null`**, wenn keine Pflanze überfällig ist (alle `days_overdue == 0`). Bei Gleichstand: kleinste `days_overdue`-Mehrdeutigkeit nach `name` (case-insensitive) deterministisch auflösen. |
| **F-STAT-6** | **`avg_interval_days`** — **Durchschnitts-Intervall**: Mittelwert der **tatsächlich beobachteten** Gieß-Abstände über alle aktiven Pflanzen, in ganzen Tagen (Float, eine Nachkommastelle). Berechnung: pro Pflanze die Differenzen aufeinanderfolgender distinkter Gieß-Kalendertage in Tagen; alle Differenzen über alle Pflanzen sammeln, Mittelwert bilden. **Sonderfall** keine Pflanze hat ≥2 distinkte Gieß-Tage → `null` (kein beobachteter Abstand). Dieses Feld misst echtes Nutzerverhalten und ist bewusst **getrennt** vom konfigurierten `interval_days` (Soll vs. Ist). |
| **F-STAT-7** | **`avg_configured_interval_days`** — Mittelwert des **konfigurierten** `interval_days` über aktive Pflanzen (Float, eine Nachkommastelle) oder `null` bei 0 Pflanzen. Billig zu berechnen, vervollständigt das Soll/Ist-Paar. |
| **F-STAT-8** | **Performance:** Alle Stats werden aus **maximal zwei** Queries gewonnen: (1) aktive Pflanzen des Users, (2) deren `waterings` im benötigten Zeitfenster (`watered_at >= today−29` für Konsistenz/Streak; für `avg_interval_days` volle Historie der aktiven Pflanzen). Aggregation in Python (kleine Datenmengen, ein Worker). Index `idx_waterings_plant_watered` (B.8) bedient beide. Keine N+1-Query pro Pflanze. |
| **F-STAT-9** | **Response-Schema `StatsResponse` (erweitert):** `{ total_plants: int, thirsty_count: int, watering_streak_days: int, watering_consistency_pct: int, longest_overdue: LongestOverdue \| null, avg_interval_days: float \| null, avg_configured_interval_days: float \| null }`. Erweitert das bestehende M1-Schema **additiv** (bestehende Felder bleiben, kein Breaking Change für M1-Clients). Endpoint bleibt `GET /api/stats`. |

### Akzeptanzkriterien

| ID | Szenario | Test-Datei |
|---|---|---|
| **AK-STAT-1** | `GET /api/stats` enthält **alle** Felder aus F-STAT-9 mit korrekten Typen; `total_plants`/`thirsty_count` identisch zu M1-Verhalten. | `tests/test_stats.py::test_stats_shape` |
| **AK-STAT-2** | **Streak:** Gießungen an Tagen `D-2, D-1, D` (freezegun „heute = D") → `watering_streak_days == 3`. Lücke an `D-1` → `1` (nur heute) bzw. Kulanz: nur `D-1` gegossen, heute nicht → `>=1`. | `tests/test_stats.py::test_streak` |
| **AK-STAT-3** | **Streak-Kulanz:** gestern gegossen, heute nicht → Streak > 0; weder gestern noch heute → `0`. | `tests/test_stats.py::test_streak_grace_day` |
| **AK-STAT-4** | **Konsistenz:** 1 Pflanze `interval_days=10`, im 30-Tage-Fenster an 3 passenden Tagen gegossen (erwartet `floor(30/10)=3`) → `100`; nur 2 von 3 → `67`. | `tests/test_stats.py::test_consistency_pct` |
| **AK-STAT-5** | **Konsistenz Sonderfall:** 0 Pflanzen **oder** alle `interval_days > 30` → `watering_consistency_pct == 100`, keine ZeroDivision. | `tests/test_stats.py::test_consistency_no_expected_slots` |
| **AK-STAT-6** | **longest_overdue:** zwei überfällige Pflanzen (5 / 12 Tage) → Objekt mit `days_overdue == 12` und passendem `name`; keine überfällig → `null`. | `tests/test_stats.py::test_longest_overdue` |
| **AK-STAT-7** | **avg_interval_days:** Pflanze mit Gießungen an `D-10, D-4, D` → Abstände 6 und 4 → `avg == 5.0`; Pflanze mit nur 1 Gießung trägt nichts bei; gar keine ≥2-Tage-Pflanze → `null`. | `tests/test_stats.py::test_avg_observed_interval` |
| **AK-STAT-8** | **avg_configured_interval_days:** Intervalle `[7, 14]` → `10.5`; 0 Pflanzen → `null`. | `tests/test_stats.py::test_avg_configured_interval` |
| **AK-STAT-9** | **Service-Direkttest (Frontend-unabhängig):** `plant_service.compute_stats(db, user_id)` liefert ein vollständiges `StatsResponse`-Objekt; alle Felder werden ohne HTTP getestet (Prinzip „Backend voll, auch was FE nicht zeigt"). | `tests/test_stats.py::test_compute_stats_service_level` |

---

## B.3 Standort/Raum + Gruppierung

### Funktionale Requirements

| Req | Beschreibung |
|---|---|
| **F-LOC-1** | **Neue Spalte `plants.location_room TEXT`** (nullable, ≤ 80 chars; Schema-Delta B.8). Optionales Freitextfeld („Wohnzimmer", „Küche-Fensterbank"). Kein FK, keine separate Räume-Tabelle (Decision-Log: minimal, Freitext genügt für 100–1000 User). |
| **F-LOC-2** | **`PlantCreate`/`PlantUpdate` erweitert** um `location_room: str \| None = Field(default=None, max_length=80)`. Editierbar via `PATCH /api/plants/{id}` (M1-PATCH-Pfad, `model_dump(exclude_unset=True)` deckt das Feld automatisch ab — `location_room` wird damit auch bewusst auf `null` setzbar). |
| **F-LOC-3** | **`PlantResponse` erweitert** um `location_room: str \| None`. `plant_service.to_response()` mappt die Spalte direkt. |
| **F-LOC-4** | **Gruppierung in Liste:** `GET /api/plants` akzeptiert optionalen Query-Param `group_by` mit Wert `room`. Bei `group_by=room` liefert die Antwort zusätzlich ein Feld `groups`: Liste von `{ location_room: str \| null, plant_ids: [int, ...] }`, sortiert nach `location_room` (case-insensitive, `null`/leer → Gruppe „Ohne Raum" zuletzt). Die flache `items`-Liste bleibt **immer** vorhanden (Rückwärtskompatibilität M1-Client); `groups` ist additiv und nur bei gesetztem Param befüllt. Innerhalb einer Gruppe gilt die M1-Sortierung (thirsty zuerst, dann alphabetisch). |
| **F-LOC-5** | **Gruppierung in Stats:** `GET /api/stats` akzeptiert optionalen Query-Param `by_room=true`. Wenn gesetzt, enthält die Antwort zusätzlich `rooms`: Liste von `{ location_room: str \| null, total_plants: int, thirsty_count: int }` pro Raum (gleiche Sortierregel wie F-LOC-4). Die Top-Level-Aggregat-Felder (B.2) bleiben unverändert. Default (`by_room` nicht gesetzt) → `rooms` weggelassen/`null`, identisch zu B.2. |
| **F-LOC-6** | **Whitespace-Normalisierung:** `location_room` wird beim Schreiben getrimmt; leerer/whitespace-only String wird als `null` gespeichert (eine kanonische „kein Raum"-Repräsentation, damit Gruppierung nicht „" und `null` trennt). |

### Akzeptanzkriterien

| ID | Szenario | Test-Datei |
|---|---|---|
| **AK-LOC-1** | `POST /api/plants` mit `location_room="Küche"` → Response enthält `location_room == "Küche"`; `PATCH` ändert auf `"Bad"` → persistiert; `PATCH` mit `location_room=""` → gespeichert als `null` (F-LOC-6). | `tests/test_location.py::test_location_crud` |
| **AK-LOC-2** | `GET /api/plants?group_by=room` → `groups` korrekt partitioniert; Pflanzen ohne Raum in Gruppe `location_room=null` **zuletzt**; `items` weiterhin vollständig + M1-sortiert. | `tests/test_location.py::test_group_by_room` |
| **AK-LOC-3** | `GET /api/plants` **ohne** Param → Response **ohne** `groups`-Feld bzw. `groups=null`, byte-kompatibel zum M1-Verhalten (nur additives Feld). | `tests/test_location.py::test_list_backcompat` |
| **AK-LOC-4** | `GET /api/stats?by_room=true` → `rooms`-Aggregate stimmen mit manueller Zählung; Top-Level-Stats unverändert gegenüber `by_room` aus. | `tests/test_location.py::test_stats_by_room` |
| **AK-LOC-5** | `location_room` mit 81 Zeichen → `422` (Pydantic `max_length`). | `tests/test_location.py::test_location_max_length` |

---

## B.4 Tägliches Cleanup / DB-Hygiene-Cron (Housekeeping)

### Funktionale Requirements

| Req | Beschreibung |
|---|---|
| **F-HK-1** | **Neuer Service `housekeeping_service.py`** mit `async def run_housekeeping(db, settings, now=None) -> dict[str, int]`. Löscht abgelaufene/verbrauchte transiente Zeilen und gibt pro Kategorie die Anzahl gelöschter Zeilen zurück (für Logging + Tests). |
| **F-HK-2** | **Gelöscht werden** (Decision-Log §1, alle Bedingungen relativ zu `now_berlin()`): **(a)** `login_tokens` mit `expires_at < now` **oder** `used_at IS NOT NULL` (verbrauchte Magic-Links + Codes); **(b)** `invite_tokens` mit (`expires_at < now`) **oder** (`revoked_at IS NOT NULL`) **oder** (`used_at IS NOT NULL`) — bei Multi-Use-Invites (Phase B) zusätzlich `used_count >= max_uses`, aber nur wenn zugleich `expires_at < now` **oder** explizit aufgebraucht **und** abgelaufen, damit aktive Mehrfach-Links nicht gelöscht werden; **(c)** `sessions` mit `revoked_at IS NOT NULL` **oder** `hard_expires_at < now` (endgültig tote Sessions); **(d)** `reminder_send_log`-Zeilen mit `reminder_date < today − HK_REMINDER_LOG_RETENTION_DAYS`; **(e)** `rate_limits` mit `expires_at < <unix-now>` (numerischer Epoch-Vergleich, wie M1). |
| **F-HK-3** | **Referentielle Sicherheit:** `invite_redemptions` (Phase B) hängt per FK `ON DELETE CASCADE` an `invite_tokens` — Löschen eines Invites räumt seine Redemptions mit ab. `login_tokens`-Löschung berührt keine Sessions (Magic-Link ist nach Konsum entkoppelt). Housekeeping löscht **niemals** `users`, `plants`, `waterings` oder Bilder (kein Daten-/Historienverlust; Account-/Plant-Löschung läuft ausschließlich über die expliziten Delete-Pfade). |
| **F-HK-4** | **Batch-Sicherheit & Writer-Serialisierung:** Housekeeping läuft als **Writer** und damit über die serialisierte Writer-Connection (B.5). Jede Kategorie ist ein einzelnes `DELETE … WHERE …`, committet einzeln; ein Fehler in einer Kategorie wird geloggt und bricht die übrigen **nicht** ab (defensive Iteration, analog Reminder-Cron). |
| **F-HK-5** | **Scheduling:** Eigener APScheduler-`CronTrigger(hour=HK_HOUR_BERLIN, minute=HK_MINUTE_BERLIN, timezone="Europe/Berlin")`, Default **03:30 Berlin** (Nachtfenster, kollidiert nicht mit dem 08:00-Digest). Job-`id="daily_housekeeping"`. Wird in `_start_scheduler()` (main.py) **zusätzlich** zum `daily_digest`-Job registriert; läuft nur außerhalb `APP_ENV="test"` (wie der Digest). |
| **F-HK-6** | **Reboot-Robustheit:** Housekeeping ist **idempotent** und rein „löschend nach Ablauf" — ein verpasster Lauf (Pi-Reboot) ist unkritisch; der nächste Lauf holt alles nach. **Kein** Catch-up nötig (anders als beim Reminder). Optional beim App-Start ein einmaliger Lauf, **deaktiviert per Default** (`HK_RUN_ON_STARTUP=false`), um Startzeit nicht zu belasten. |
| **F-HK-7** | **Beobachtbarkeit:** Jeder Lauf loggt **eine** strukturierte Zeile `event="housekeeping_done"` mit den Lösch-Counts pro Kategorie und der Gesamtdauer (B.6). Fehler pro Kategorie → `event="housekeeping_error"` mit `category` + `error`. |

### Konfig-Delta

```python
# Housekeeping (B.4)
HK_HOUR_BERLIN: int = Field(default=3, ge=0, le=23)
HK_MINUTE_BERLIN: int = Field(default=30, ge=0, le=59)
HK_REMINDER_LOG_RETENTION_DAYS: int = 90   # reminder_send_log älter als das wird gelöscht
HK_RUN_ON_STARTUP: bool = False
```

### Akzeptanzkriterien

| ID | Szenario | Test-Datei |
|---|---|---|
| **AK-HK-1** | Abgelaufenes `login_token` (`expires_at` in Vergangenheit) + ein frisches gültiges → `run_housekeeping` löscht **nur** das abgelaufene; Rückgabe-Dict meldet `login_tokens: 1`. | `tests/test_housekeeping.py::test_login_tokens` |
| **AK-HK-2** | Verbrauchtes `login_token` (`used_at` gesetzt, noch nicht expired) wird gelöscht. | `tests/test_housekeeping.py::test_used_login_token` |
| **AK-HK-3** | Revoked **und** hart-abgelaufene Session werden gelöscht; eine aktive Session bleibt. | `tests/test_housekeeping.py::test_sessions` |
| **AK-HK-4** | Abgelaufenes/revoked Invite gelöscht; aktiver Mehrfach-Invite mit Restkontingent (`used_count < max_uses`, nicht expired) **bleibt**. | `tests/test_housekeeping.py::test_invites` |
| **AK-HK-5** | `reminder_send_log`-Zeile mit `reminder_date` älter als Retention gelöscht; jüngere bleibt. | `tests/test_housekeeping.py::test_reminder_log_retention` |
| **AK-HK-6** | Abgelaufene `rate_limits`-Zeile (numerischer `expires_at` < now-epoch) gelöscht. | `tests/test_housekeeping.py::test_rate_limits` |
| **AK-HK-7** | Housekeeping berührt `users`/`plants`/`waterings` **nicht** (Counts unverändert). | `tests/test_housekeeping.py::test_preserves_user_data` |
| **AK-HK-8** | Fehler in einer Kategorie (z. B. simuliert) bricht die anderen nicht ab; Rückgabe enthält die erfolgreichen Counts, Fehler wird geloggt. | `tests/test_housekeeping.py::test_partial_failure_isolated` |

---

## B.5 DB-Concurrency: WAL + parallele Reads / ein Writer

### Funktionale Requirements

| Req | Beschreibung |
|---|---|
| **F-DB-1** | **Kein Postgres, keine Pagination** (Decision-Log §1). SQLite bleibt, mit **WAL** (bereits in M1 `db.py` gesetzt: `journal_mode=WAL`, `busy_timeout=5000`, `synchronous=NORMAL`, `foreign_keys=ON`). WAL erlaubt **gleichzeitige Reader während ein Writer schreibt**. |
| **F-DB-2** | **Connection-Modell „Read-Pool + ein Writer":** Statt einer einzigen geteilten `app.state.db` führt v3 zwei Rollen ein: **(a)** ein **Reader-Pool** (`app.state.db_readers`) mit `DB_READ_POOL_SIZE` Read-Connections (Default 4), die parallel `SELECT`-lastige Endpoints bedienen; **(b)** **eine** dedizierte, **serialisierte Writer-Connection** (`app.state.db_writer`), durch einen `asyncio.Lock` geschützt, über die **alle** mutierenden Operationen (INSERT/UPDATE/DELETE inkl. `/water`, Plant-CRUD, Auth-Token-Consume, Reminder-Log, Housekeeping) laufen. Begründung: SQLite erlaubt nur **einen** Writer; Serialisierung über einen App-Lock vermeidet `SQLITE_BUSY` unter Last und hält die M1-Garantie „kurze Transaktionen, ein Worker" bei, skaliert aber Reads. |
| **F-DB-3** | **Dependency-Split:** Neue FastAPI-Dependencies `db_read` (vergibt eine Reader-Connection aus dem Pool) und `db_write` (vergibt die Writer-Connection **und** hält den Writer-Lock für die Dauer des Requests). Bestehende Routen werden zugeordnet: reine GETs → `db_read`; alle Routen mit `require_csrf`/Mutation → `db_write`. Das ersetzt das M1-`_db`-Dependency abwärtskompatibel (Service-Signatur `db: aiosqlite.Connection` bleibt unverändert — Services wissen nichts vom Pool). |
| **F-DB-4** | **Writer-Lock-Semantik:** `db_write` umschließt den Request-Handler mit `async with app.state.writer_lock:`. Innerhalb des Locks gelten weiterhin kurze Transaktionen (M1-Pattern: `execute` + `commit`). Token-/Session-Consume und `/water` (Multi-Statement) laufen so **garantiert serialisiert**, ohne `BEGIN IMMEDIATE`-Races zwischen App-Connections. Der Lock ist **fair genug** (asyncio-FIFO) und wird nie über `await`-Punkte außerhalb des DB-Zugriffs gehalten (kein Netzwerk-I/O wie Resend **innerhalb** des Writer-Locks — Mail-Versand passiert außerhalb). |
| **F-DB-5** | **Lifecycle:** `init_db()`/`db.py` bekommt `connect_reader_pool(settings) -> list[Connection]` und `connect_writer(settings) -> Connection`. **Migrationen laufen genau einmal** über die Writer-Connection beim Start (vor Pool-Aufbau), wie in M1 dokumentiert (ein Worker). Alle Connections setzen dieselben PRAGMAs. Beim Shutdown werden Writer + alle Reader sauber geschlossen. |
| **F-DB-6** | **Test-Kompatibilität:** In Tests (`APP_ENV=test`, `conftest.db`-Fixture) bleibt **eine** geteilte Connection, die **sowohl** als Reader **als auch** als Writer injiziert wird (Pool-Größe 1, no-op-Lock). So bleiben alle bestehenden M1-Tests und das `client`-Fixture unverändert gültig; die Concurrency-Maschinerie ist nur in `APP_ENV != test` aktiv. `create_app(settings, db=...)` akzeptiert weiterhin eine Einzel-Connection und verteilt sie auf beide Rollen. |
| **F-DB-7** | **Begründung dokumentiert:** WAL-Checkpointing bleibt SQLite-automatisch (`synchronous=NORMAL`); der tägliche Backup-Cron (separater Baustein/Phase D) nutzt `sqlite3 .backup`, das WAL-konsistent ist. **Keine** zusätzliche `wal_autocheckpoint`-Tuning-Pflicht in v3 (Default genügt bei dieser Last). |

### Konfig-Delta

```python
# DB concurrency (B.5)
DB_READ_POOL_SIZE: int = Field(default=4, ge=1, le=16)
```

### Akzeptanzkriterien

| ID | Szenario | Test-Datei |
|---|---|---|
| **AK-DB-1** | PRAGMA-Check: jede Reader- und die Writer-Connection meldet `journal_mode=wal`, `foreign_keys=1`, `busy_timeout=5000`. | `tests/test_db_concurrency.py::test_pragmas_all_connections` |
| **AK-DB-2** | **Parallele Reads:** N gleichzeitige `GET /api/plants` (httpx, `asyncio.gather`) liefern alle `200` ohne `SQLITE_BUSY`/500. | `tests/test_db_concurrency.py::test_parallel_reads` |
| **AK-DB-3** | **Serialisierter Writer:** zwei gleichzeitige `/water`-Requests auf dieselbe Pflanze → beide `200`, Historie hat **genau zwei** zusätzliche Zeilen, `last_watered_at` konsistent (keine verlorene Schreibung). | `tests/test_db_concurrency.py::test_serialized_writes` |
| **AK-DB-4** | **Read-while-Write:** ein langsamer Writer (künstlich verzögert) blockiert parallele Reads nicht (Reads kommen vor Writer-Commit zurück, WAL). | `tests/test_db_concurrency.py::test_reads_not_blocked_by_writer` |
| **AK-DB-5** | Bestehende M1-Test-Suite läuft mit der Single-Connection-Fixture unverändert grün (Regression). | (gesamte bestehende Suite) |

---

## B.6 Strukturiertes Logging (structlog) + erweiterter Healthcheck

### Funktionale Requirements

| Req | Beschreibung |
|---|---|
| **F-LOG-1** | **`structlog`-Setup** (M1 NFR-8 fordert es; v3 implementiert es vollständig) in neuem `logging_setup.py`: `configure_logging(settings)` — JSON-Renderer in Production (`APP_ENV=production`), farbiger Console-Renderer in Dev/Test. Prozessoren: Zeitstempel (ISO, Berlin-naiv via `now_berlin`), Log-Level, Logger-Name, `event`-Key, Exception-Rendering. Aufruf im Lifespan-Start (`create_app`). |
| **F-LOG-2** | **Kein PII/Secrets in Logs:** Email-Adressen werden **nur** als HMAC-Hash geloggt (Wiederverwendung des M1-`hash_ip`-Musters → neuer Helper `hash_email_for_log(email)` in `security.py`, HMAC mit `TOKEN_PEPPER`, gekürzt auf 12 hex-Zeichen). Magic-Link-/Session-/CSRF-Tokens, `RESEND_API_KEY`, `location_room`-Freitext und `notes` werden **nie** geloggt. Log-Level via `LOG_LEVEL` (Default `INFO`). |
| **F-LOG-3** | **Request-Logging-Middleware:** eine strukturierte Zeile pro abgeschlossenem Request mit `event="request"`, `method`, `path`-Template (nicht die rohe URL mit IDs → niedrige Kardinalität, z. B. `/api/plants/{plant_id}/water`), `status`, `duration_ms`, `user_id` (falls authentifiziert, sonst weggelassen), `ip_hash`. **Nie** Query-/Body-Inhalte. Greift nach der bestehenden `_renew_cookie`-Middleware. |
| **F-LOG-4** | **Domänen-Logs:** strukturierte Events für sicherheits-/betriebsrelevante Vorgänge: `event="login_requested"` / `"login_verified"` / `"login_failed"` (mit `reason`-Code, `email_hash`), `"rate_limited"` (mit `scope`), `"reminder_run"` (mit `sent`/`skipped`/`failed`-Counts), `"housekeeping_done"` (B.4), `"image_rejected"` (mit `reason`: `mime`/`too_large`/`bomb`/`corrupt`). Ersetzt etwaige Print-/Bare-Logging-Aufrufe. |
| **F-LOG-5** | **Erweiterter Healthcheck `GET /api/health`:** Response-Schema additiv erweitert auf `{ status, db_ok, scheduler_running, jobs: {digest: bool, housekeeping: bool}, db_writable: bool, version: str, reminder_last_run: str \| null, wal_mode: bool }`. **`db_ok`** = `SELECT 1` auf Reader (M1). **`db_writable`** = best-effort Schreibprobe (z. B. `PRAGMA user_version` lesen + ein No-op auf Writer in `BEGIN`/`ROLLBACK`, ohne Datenänderung) — erkennt „Disk voll / read-only FS". **`jobs`** spiegelt, ob beide Cron-Jobs im Scheduler registriert **und** der Scheduler running ist. **`wal_mode`** = `PRAGMA journal_mode` == `wal`. `status="ok"` nur wenn `db_ok && db_writable`; sonst `"degraded"`. |
| **F-LOG-6** | **`version`** kommt aus einer Config-/Build-Konstante (`APP_VERSION`, Default `"3.0.0"`); ermöglicht dem externen Uptime-Monitor (UptimeRobot, Decision-Log §1) und Deploy-Checks, die laufende Version zu sehen. |
| **F-LOG-7** | **Healthcheck bleibt unauthenticated** (von Docker-`HEALTHCHECK` + externem Monitor genutzt, M1 NFR-9) und **leakt keine** sensiblen Details (keine Pfade, keine Counts von User-Daten, keine Emails). `reminder_last_run` ist ein Datum/Zeit, kein PII. |

### Konfig-Delta

```python
# Observability (B.6)
LOG_LEVEL: str = "INFO"          # DEBUG|INFO|WARNING|ERROR
LOG_JSON: bool | None = None     # None → JSON in prod, console sonst
APP_VERSION: str = "3.0.0"
```

### Akzeptanzkriterien

| ID | Szenario | Test-Datei |
|---|---|---|
| **AK-LOG-1** | `GET /api/health` → `200` + alle Felder aus F-LOG-5; `db_ok=true`, `db_writable=true`, `wal_mode=true`, `version="3.0.0"`. | `tests/test_health.py::test_health_extended_shape` |
| **AK-LOG-2** | Mit gestartetem Scheduler (Integrationstest): `jobs.digest=true` **und** `jobs.housekeeping=true`, `scheduler_running=true`. | `tests/test_health.py::test_health_jobs` |
| **AK-LOG-3** | `hash_email_for_log("a@b.de")` ist deterministisch, ≠ Klartext, enthält kein „@", 12 Zeichen; gleiche Email → gleicher Hash, andere Email → anderer Hash. | `tests/test_logging.py::test_email_hash` |
| **AK-LOG-4** | Request-Log-Zeile (capture via structlog-Test-Capture) enthält `event="request"`, `path`-Template **ohne** rohe ID, `status`, `duration_ms`; **kein** `email`-Klartext, **kein** Token. | `tests/test_logging.py::test_request_log_fields` |
| **AK-LOG-5** | Abgelehnter Upload (Polyglot) erzeugt `event="image_rejected"` mit `reason="mime"`; kein Dateiinhalt im Log. | `tests/test_logging.py::test_image_rejected_log` |
| **AK-LOG-6** | `status="degraded"`, wenn `db_writable` fehlschlägt (simuliert read-only). | `tests/test_health.py::test_health_degraded_on_readonly` |

---

## B.7 DSGVO Daten-Export (JSON + Bilder als ZIP)

Self-Service-Export nach **DSGVO Art. 15 (Auskunft) / Art. 20 (Datenübertragbarkeit)**. Ergänzt die in M1 bestehende Account-Löschung (Art. 17) und die in Phase B kommende Email-Änderung.

### Funktionale Requirements

| Req | Beschreibung |
|---|---|
| **F-EXP-1** | **Endpoint `GET /api/account/export`** (Auth required; **kein** CSRF nötig, da kein State-Change; rate-limited `EXPORT_RATE` Default `3/h` pro User gegen Missbrauch). Liefert **ein ZIP** (`Content-Type: application/zip`, `Content-Disposition: attachment; filename="plantpal-export-<user_id>-<YYYY-MM-DD>.zip"`) mit dem **vollständigen** personenbezogenen Datenbestand des aufrufenden Users. |
| **F-EXP-2** | **ZIP-Inhalt:** **(a)** `export.json` — ein strukturiertes JSON mit allen User-Daten; **(b)** `images/{plant_id}.png` — alle Bilder der (auch soft-deleteten) Pflanzen des Users, 1:1 vom Filesystem (`data/images/{user_id}/`). Enthält eine `README.txt` mit Erzeugungsdatum, Format-Beschreibung und Hinweis auf das Schema von `export.json`. |
| **F-EXP-3** | **`export.json`-Struktur (User-scoped, alles `user_id`-gefiltert):** `{ "export_format_version": 1, "generated_at": "<iso Berlin>", "account": { id, email, is_admin, email_reminders_enabled, reminder_channel, reminder_hour, locale, theme, created_at, last_login_at }, "plants": [ { id, name, interval_days, location_room, notes, water_amount_ml, last_watered_at, created_at, is_active, image_file: "images/{id}.png"\|null, waterings: [ { id, watered_at, created_at }, ... ] }, ... ], "invites_created": [ { id, email_hint, created_at, expires_at, used_at } ... ], "sessions": [ { created_at, last_seen_at, expires_at } ... ] }`. Enthält **soft-deletete** Pflanzen (Art. 15 verlangt **alle** gespeicherten Daten) mit `is_active`-Flag. **Keine** Token-Hashes/Secrets, keine anderen User. |
| **F-EXP-4** | **ZIP-Erzeugung speicher- & loop-schonend:** Aufbau via `zipstream`/`StreamingResponse` **oder** in einem temporären File über `await asyncio.to_thread(...)` (Bild-Bytes nicht blockierend in den Event-Loop ziehen, analog M1-Image-Pipeline `asyncio.to_thread`). Bei vielen Pflanzen kein Vollständig-in-RAM-Halten aller Bilder gleichzeitig. |
| **F-EXP-5** | **Robustheit gegen fehlende Dateien:** Fehlt eine erwartete Bilddatei auf der Platte (Inkonsistenz), wird `image_file` im JSON auf `null` gesetzt und das Bild im ZIP ausgelassen — **kein** 500. Plant ohne Bild (`image_path` null) → `image_file: null`, kein ZIP-Eintrag. |
| **F-EXP-6** | **Sicherheit:** Liest **ausschließlich** aus `data/images/{user_id}/` (Integer-ID im Pfad, kein Traversal — Wiederverwendung M1-`image_service.image_file_path`). Cross-User-Daten sind durch die `user_id`-Filterung **strukturell** ausgeschlossen. Reads laufen über den Reader-Pool (B.5). |
| **F-EXP-7** | **Reader-Service `account_export_service.py`** mit `async def build_export(db, settings, user_id) -> ExportBundle` (sammelt JSON-Datenstruktur) und einer ZIP-Packfunktion. Reine Lese-Operation (keine Mutation, kein Writer-Lock). Testbar ohne HTTP (Service-Level). |

### Konfig-Delta

```python
# Data export (B.7)
EXPORT_RATE: str = "3/h"   # pro User, anti-abuse für den ZIP-Export
```

### Akzeptanzkriterien

| ID | Szenario | Test-Datei |
|---|---|---|
| **AK-EXP-1** | User mit 2 Pflanzen (je 1 Bild) + Gieß-Historie ruft `GET /api/account/export` → `200`, `Content-Type: application/zip`; ZIP enthält `export.json`, `images/{id}.png` (×2), `README.txt`. | `tests/test_account_export.py::test_export_zip_contents` |
| **AK-EXP-2** | `export.json` enthält **alle** Pflanzen des Users inkl. **soft-deleteter** (mit `is_active=0`) und deren vollständige `waterings`; **keine** Daten anderer User. | `tests/test_account_export.py::test_export_includes_soft_deleted_and_scopes_user` |
| **AK-EXP-3** | `export.json` enthält **keinen** Token-Hash, kein `session_hash`, keinen `RESEND_API_KEY`, keine fremde Email (Secret-Scan über den JSON-String). | `tests/test_account_export.py::test_export_no_secrets` |
| **AK-EXP-4** | Pflanze, deren Bilddatei fehlt → `image_file: null`, kein ZIP-Bildeintrag, Response trotzdem `200`. | `tests/test_account_export.py::test_export_missing_image_graceful` |
| **AK-EXP-5** | User B kann via Export **nur** eigene Daten ziehen; User A's `plant_id` taucht in B's `export.json` nicht auf. | `tests/test_account_export.py::test_export_user_isolation` |
| **AK-EXP-6** | 4. Export-Request innerhalb 1 h → `429 + Retry-After`. | `tests/test_account_export.py::test_export_rate_limit` |
| **AK-EXP-7** | Service-Direkttest: `build_export(db, settings, user_id)` liefert die vollständige Struktur (F-EXP-3) ohne HTTP. | `tests/test_account_export.py::test_build_export_service_level` |

---

## B.8 Schema-Delta — Migration `002_v3_backend.sql`

Idempotent, in `_migrations` getrackt (M1-Runner `db.run_migrations` wendet `*.sql` numerisch sortiert an, splittet auf `;`, committet pro Migration atomisch). **Konvention:** Datetimes naiv Berlin von Python gesetzt (nie SQLite `datetime('now')` — das wäre UTC). Indizes additiv. Die `ALTER`s sind in SQLite einzeln und idempotenzsicher gehalten (siehe Hinweis unten).

> **Idempotenz-Hinweis:** SQLite kennt kein `ADD COLUMN IF NOT EXISTS` und kein `CREATE INDEX IF NOT EXISTS … WHERE` Problem nicht — `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` werden genutzt. Da der `_migrations`-Tracker jede Datei nur **einmal** anwendet, ist die Datei als Ganzes idempotent; die `IF NOT EXISTS`-Klauseln sind zusätzliche Absicherung gegen einen halb-migrierten Altzustand. Die nackten `ALTER TABLE … ADD COLUMN` laufen daher genau einmal.

```sql
-- 002_v3_backend.sql — PlantPal v3 Backend-Erweiterungen.
-- Datetimes are naive Berlin (ISO-8601, no tz suffix), written by Python.

-- B.1 Gieß-Historie
CREATE TABLE IF NOT EXISTS waterings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plant_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,           -- denormalized for user-scoped stats/export
  watered_at TEXT NOT NULL,           -- naive Berlin, = plants.last_watered_at on insert
  created_at TEXT NOT NULL,
  FOREIGN KEY (plant_id) REFERENCES plants(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_waterings_plant_watered ON waterings(plant_id, watered_at);
CREATE INDEX IF NOT EXISTS idx_waterings_user_watered  ON waterings(user_id, watered_at);

-- B.3 Standort/Raum
ALTER TABLE plants ADD COLUMN location_room TEXT;   -- nullable, app-trimmed, <=80 chars

-- v3 user preferences (B.3/Reminder/Phase-C cross-refs; backend owns the columns + defaults)
ALTER TABLE users ADD COLUMN invite_quota   INTEGER NOT NULL DEFAULT 3;
ALTER TABLE users ADD COLUMN locale          TEXT    NOT NULL DEFAULT 'de';
ALTER TABLE users ADD COLUMN reminder_hour   INTEGER NOT NULL DEFAULT 8;
ALTER TABLE users ADD COLUMN theme           TEXT    NOT NULL DEFAULT 'dark';

-- Note: CHECK-Constraints für locale ('de','en'), theme ('dark','light') und
-- reminder_hour (0..23) werden auf Pydantic-Ebene erzwungen (M1-Konvention:
-- Validierung in den Modellen). SQLite ALTER ADD COLUMN unterstützt keine
-- nachträglichen Table-CHECKs ohne Table-Rebuild — bewusst vermieden.
```

> **Abgrenzung (in diesem Baustein nur referenziert, im selben `002` ergänzt von den Phase-B-Bausteinen):** `invite_tokens.max_uses|used_count`, `invite_redemptions`, `login_tokens.code|attempt_count`, `email_change_requests`. Der Housekeeping-Service (B.4) und der Reminder-Cron (`reminder_hour`) sind **forward-kompatibel** zu diesen Spalten formuliert (B.4 F-HK-2b nutzt `max_uses/used_count` defensiv). Die `reminder_hour`-Auswertung im Cron (stündlicher Trigger, fällige User filtern) ist im **Reminder-Baustein** spezifiziert; backend-seitig liefert dieser Baustein nur die Spalte + Default 8.

### Akzeptanz Schema

| ID | Szenario | Test-Datei |
|---|---|---|
| **AK-MIG-1** | Frische DB → `run_migrations` wendet `001` + `002` an; `waterings` existiert mit beiden Indizes; `plants.location_room` und die vier `users`-Spalten existieren mit korrekten Defaults (`invite_quota=3`, `locale='de'`, `reminder_hour=8`, `theme='dark'`). | `tests/test_db.py::test_migration_002_applies` |
| **AK-MIG-2** | `run_migrations` zweimal hintereinander auf derselben DB → idempotent, keine Exception, `_migrations` enthält `002_v3_backend.sql` genau einmal. | `tests/test_db.py::test_migration_002_idempotent` |
| **AK-MIG-3** | Bestehende M1-DB (nur `001` angewandt) → `002` migriert sauber nach, vorhandene `plants`/`users`-Zeilen bleiben erhalten, neue Spalten bekommen ihre Defaults. | `tests/test_db.py::test_migration_002_upgrades_existing` |
| **AK-MIG-4** | FK-Cascade: Lösche eine `users`-Zeile → zugehörige `waterings`-Zeilen verschwinden (Account-Hard-Delete-Pfad bleibt vollständig). | `tests/test_db.py::test_waterings_cascade_on_user_delete` |

---

## B.9 Endpoint-Delta (Übersicht)

| Methode | Pfad | Rolle (B.5) | Auth | CSRF | Rate-Limit | Status |
|---|---|---|---|---|---|---|
| POST | `/api/plants/{id}/water` | **write** | ✓ | ✓ | `30/user/min` | **erweitert** (schreibt `waterings` + update) |
| POST | `/api/plants` | **write** | ✓ | ✓ | `30/user/min` | **erweitert** (`location_room` + Backfill-`watering`) |
| PATCH | `/api/plants/{id}` | **write** | ✓ | ✓ | `30/user/min` | **erweitert** (`location_room` editierbar) |
| GET | `/api/plants` | **read** | ✓ | – | – | **erweitert** (`?group_by=room` → `groups`) |
| GET | `/api/plants/{id}/waterings` | **read** | ✓ | – | – | **neu** (B.1) |
| GET | `/api/stats` | **read** | ✓ | – | – | **erweitert** (reichhaltig + `?by_room=true`) |
| GET | `/api/account/export` | **read** | ✓ | – | `3/h/user` | **neu** (B.7) |
| GET | `/api/health` | **read** | – | – | – | **erweitert** (B.6) |

**Schema-Modelle (in `models.py`, additiv):** `WateringResponse`, `LongestOverdue`, `PlantGroup`, `RoomStats`; erweitert: `PlantCreate`/`PlantUpdate`/`PlantResponse` (`location_room`), `StatsResponse` (B.2-Felder + optional `rooms`), `HealthResponse` (B.6-Felder), neuer `PlantListResponse` mit optionalem `groups`.

---

## B.10 Test- & Qualitäts-Anker (Phase A)

| Req | Beschreibung |
|---|---|
| **F-QA-1** | **Alle** oben gelisteten AKs sind als `pytest`-Tests umgesetzt (`pytest-asyncio mode=auto`, `db`/`client`-Fixtures aus `conftest.py`, `freezegun` für Kalender-/Streak-Tests). Neue Test-Dateien: `test_watering_history.py`, `test_stats.py`, `test_location.py`, `test_housekeeping.py`, `test_db_concurrency.py`, `test_logging.py`, `test_account_export.py`; erweitert: `test_health.py`, `test_db.py`, `test_main.py`. |
| **F-QA-2** | **Coverage** des Backends bleibt ≥ 90 % (M1-Ziel, README). Stats- und Export-Service werden **direkt** (Service-Level) getestet, nicht nur über HTTP — sichert das Prinzip „Backend voll + getestet, auch was das Frontend nicht zeigt". |
| **F-QA-3** | **Lint clean:** `ruff check` + `ruff format --check` grün; parametrisierte SQL only (kein f-string-SQL außer dem bestehenden, kommentierten `# noqa: S608`-Dynamic-Update-Pattern in `plant_service.update_plant`, das `location_room` automatisch mitführt). |
| **F-QA-4** | **Regression:** Die komplette bestehende M1-Suite bleibt grün (additive Erweiterungen, keine Breaking Changes an M1-Schemas/Endpoints). |



# Teil 4 — Frontend v3

# 8. Frontend v3

**Status:** v3 — erweitert die M1-Baseline (`docs/PRD_M1.md` §6). 
**Stand:** 2026-06-03 (Decision-Log Grill 2026-06-03). 
**Prinzip:** Backend liefert die volle Funktion und Datenmenge; das Frontend zeigt in v3 eine bewusst gewählte **Teilmenge** (insb. bei Stats und der Tropfen-Status-Anzeige). Was hier als „Spec für später" markiert ist, wird vollständig spezifiziert, aber in v3 noch nicht implementiert.

## 8.0 Baseline (M1, bereits implementiert)

Diese Stand-Beschreibung ist die Ausgangsbasis, die v3 erweitert — kein Neubau.

- **Stack:** Vite 5 + React 18 + TypeScript 5 + Tailwind v4 (`@theme`-Layer in `frontend/src/index.css`) + Custom Pixel-CSS, React Router v6, Tanstack Query v5, sonner (Toasts). Dev-Proxy `/api` + `/auth` → `:8000` (`frontend/vite.config.ts`).
- **Routen (`frontend/src/App.tsx`):** `/login`, `/register`, `/` (Plantdex), `/settings`, `/stats`, Fallback → `/`. `RequireAuth` gated über `GET /api/me`.
- **Pages/Components:** `LoginPage`, `RegisterPage`, `PlantdexPage`, `SettingsPage`, `StatsPage`; `AddPlantModal`, `PlantDetailModal`, `ThirstySection`, `PlantCard`.
- **API-Client (`frontend/src/api.ts`):** zentral, sendet `X-CSRF-Token` aus dem `plantpal_csrf`-Cookie bei jeder Nicht-GET-Mutation, `credentials: "include"`. `ApiError{status, code, message}`.
- **Theme:** ausschließlich Dunkelgrün + Gold, Pixel-Font „Press Start 2P" (Fallback `VT323`), Vine-Wallpaper. Strings sind **hartkodiert Deutsch** (z. B. „Lade…").
- **Status heute:** binär — Wassertropfen-Icon + Hervorhebung in der THIRSTY-Section (M1 F-THIRST-4).
- **Stats heute:** Total + Thirsty (M1 F-STAT-1/2).
- **Lücken, die v3 schließt:** keine i18n; Pflanze nicht im UI editierbar (Endpoints `PATCH /api/plants/{id}` und `POST /api/plants/{id}/image` existieren ungenutzt); keine Suche/Sortierung/Filter; minimale Lösch-UX; kein Light-Mode; kein Empty-State-Onboarding; keine PWA.

## 8.1 Internationalisierung (i18n)

| Req | Beschreibung |
|---|---|
| **F-I18N-1** | **Library:** `i18next` + `react-i18next` + `i18next-browser-languagedetector`. Zwei Locales: **`de`** und **`en`**. Keine weiteren Sprachen in v3. Init in neuem Modul `frontend/src/i18n/index.ts`, importiert in `main.tsx` vor dem Render. |
| **F-I18N-2** | **Ressourcen:** Statische JSON-Bundles `frontend/src/i18n/locales/{de,en}.json`, in den Build gebundelt (kein Lazy-HTTP-Load — store-ready/offline). Flache, namespaced Keys (`plant.add`, `settings.language`, `delete.undo`, …). **Vollständige Parität:** jeder Key existiert in beiden Dateien; ein CI-Check (`npm run i18n:check`, Node-Script) failt, wenn Key-Sets divergieren. |
| **F-I18N-3** | **Default-Locale:** Browser-Locale via `languagedetector` (Reihenfolge: persistierte User-Wahl → `navigator.language`). **Fallback `de`** (`fallbackLng: "de"`), auch für jeden fehlenden Key. Unbekannte Sprachen (z. B. `fr`) → `de`. |
| **F-I18N-4** | **Persistenz & Quelle der Wahrheit:** Eingeloggt ist `users.locale` (Backend, s. §8.8) maßgeblich. Beim App-Start nach erfolgreichem `GET /api/me` wird die Server-`locale` via `i18n.changeLanguage()` angewandt und überschreibt die Detector-Heuristik. Zusätzlich Spiegelung in `localStorage("plantpal_locale")` für den Pre-Auth-Zustand (Login/Register) und sofortigen Render ohne Flash. |
| **F-I18N-5** | **Umschalter in Settings:** Segmented Control / Select „Deutsch ⋅ English". Wechsel ruft sofort `i18n.changeLanguage()` (optimistisch) **und** persistiert via `PATCH /api/settings { locale }`. Bei API-Fehler: Rollback der UI-Sprache + Fehler-Toast. Pre-Auth (LoginPage) bietet denselben Umschalter rein clientseitig (nur `localStorage`). |
| **F-I18N-6** | **Abdeckung:** Alle nutzersichtbaren Strings laufen über `t()` — inkl. Toasts, Validierungs-/Fehlermeldungen, Empty-States, Buttons, `aria-label`s, `<title>`/Meta. **Keine** hartkodierten Anzeigetexte mehr (der M1-String „Lade…" u. ä. werden migriert). API-`error.code`s werden über eine `errors.<code>`-Key-Map auf lokalisierte Texte gemappt; unbekannte Codes → generischer `errors.generic`-Fallback. |
| **F-I18N-7** | **Plurale & Interpolation:** i18next-Pluralregeln für zählbare Texte (z. B. „1 Pflanze hat Durst" / „{{count}} Pflanzen haben Durst", „vor {{days}} Tag(en) fällig"). Keine manuelle String-Konkatenation. |
| **F-I18N-8** | **`<html lang>`:** wird bei jedem Sprachwechsel auf den aktiven Locale-Code gesetzt (a11y/SEO). `document.dir` bleibt `ltr` (beide Sprachen LTR). |
| **F-I18N-9** | **Mail-Kopplung (Hinweis, Umsetzung Backend):** Reminder-/Magic-Link-Mails werden serverseitig nach `users.locale` lokalisiert (Decision-Log §4; Backend-Baustein). Das Frontend liefert dafür ausschließlich den korrekt persistierten `locale`-Wert; keine Mail-Templates im Frontend. |

## 8.2 Pflanze voll editierbar (Edit-Modal inkl. Bild-Tausch)

| Req | Beschreibung |
|---|---|
| **F-FE-EDIT-1** | **Edit-Modal:** Neuer Modus im `PlantDetailModal` (oder neues `EditPlantModal`), geöffnet über „Bearbeiten" in der Detailansicht. Editierbar: **`name`, `interval_days`, `notes`, `water_amount_ml`, `location_room`** (neues Feld, s. §8.8) **und das Bild**. `last_watered_at` ist **nicht** über das Edit-Modal änderbar (nur via Gießen-Aktion — Vertrag M1 F-PLANT-3). |
| **F-FE-EDIT-2** | **Formular:** `react-hook-form`, vorbefüllt aus der Plant-Response. Clientseitige Validierung spiegelt die Server-Constraints: `name` 1–100, `interval_days` 1–365, `notes` ≤500, `water_amount_ml` 1–5000 (oder leer), `location_room` ≤80 (oder leer). Submit deaktiviert solange invalid oder unverändert (dirty-check). |
| **F-FE-EDIT-3** | **Persistenz Felder:** Submit sendet **nur geänderte Felder** als `PATCH /api/plants/{id}`. Tanstack-Query: optimistic Update der `["plants"]`-Liste **und** des `["plant", id]`-Caches; Rollback + lokalisierter Fehler-Toast bei Misserfolg; `invalidateQueries` nach Erfolg. |
| **F-FE-EDIT-4** | **Bild-Tausch:** Separater „Bild ändern"-Block mit Datei-Picker. Clientseitige Pre-Validierung (Typ ∈ jpeg/png/webp, ≤10 MB) **vor** Upload; bei Verstoß lokalisierter Toast statt Request. Upload via `POST /api/plants/{id}/image` (multipart). Live-Preview des gewählten Files (`URL.createObjectURL`, revoke nach Render). Nach Erfolg: Bild-Cache-Bust durch versionierten Query-Param `?<plant.updated_or_watered_ts>` an der `image_url`, damit der Browser das überschriebene 96er-PNG neu lädt (gleicher Pfad, M1 F-IMG-6). |
| **F-FE-EDIT-5** | **Bild-Tausch-UX:** Bild-Upload und Feld-Speichern sind unabhängige Aktionen mit je eigenem Lade-/Fehlerzustand (ein fehlgeschlagener Upload verwirft nicht die Feld-Änderungen und umgekehrt). Während eines Uploads: Spinner/disabled-State, kein Doppel-Submit. |
| **F-FE-EDIT-6** | **Fehlerbilder:** API-`error.code`s (`413` upload_too_large, `415`, `422`/`400` invalid_image, `404`) werden über die `errors.<code>`-Map (F-I18N-6) lokalisiert angezeigt; das Modal bleibt offen und editierbar. |

## 8.3 Suche, Sortierung, Thirsty-Filter

| Req | Beschreibung |
|---|---|
| **F-FE-LIST-1** | **Clientseitig:** Suche/Sort/Filter arbeiten rein auf der bereits geladenen `GET /api/plants`-Liste (Decision-Log §1: **keine Pagination**, Datensätze pro User klein). Kein neuer Endpoint, keine Server-Query-Params in v3. |
| **F-FE-LIST-2** | **Suche:** Textfeld filtert case-insensitive über `name` **und** `location_room`. Debounce 150 ms. Live-Ergebnis. Leerer Suchstring = kein Filter. Diakritika-tolerant (Normalisierung via `toLocaleLowerCase`). |
| **F-FE-LIST-3** | **Sortierung:** Auswahl (Select/Segmented) mit drei Modi: **Durst** (`days_overdue` DESC, dann Name A→Z — entspricht der M1-Default-Server-Sortierung), **Name** (A→Z), **Zuletzt gegossen** (`last_watered_at` DESC). Default = **Durst**. Sortier-Labels lokalisiert. |
| **F-FE-LIST-4** | **Thirsty-Filter:** Toggle „Nur durstige". Aktiv ⇒ nur `is_thirsty === true`. Kombiniert sich mit Suche und Sortierung (alle drei gleichzeitig wirksam). |
| **F-FE-LIST-5** | **UI-State-Persistenz:** Aktiver Suchtext, Sortiermodus und Filter-Toggle überleben Navigation innerhalb der Session (React-State/URL-Searchparams), gehen aber bei vollem Reload nicht zwingend verloren-frei — Reset auf Default ist akzeptabel. Die separate THIRSTY-Section (M1) bleibt unabhängig oben sichtbar; der Filter wirkt nur auf das Plantdex-Grid. |
| **F-FE-LIST-6** | **Leeres Filterergebnis:** Eigener Zustand „Keine Pflanze passt zu deiner Suche/Filter" mit „Filter zurücksetzen"-Button — abgegrenzt vom Onboarding-Empty-State (§8.5), der nur bei 0 Pflanzen insgesamt erscheint. |

## 8.4 Lösch-UX

| Req | Beschreibung |
|---|---|
| **F-FE-DEL-1** | **Pflanze — sofort + Undo:** Löschen entfernt die Pflanze **sofort** aus dem UI (optimistisches Entfernen aus `["plants"]`), ruft `DELETE /api/plants/{id}` (Soft-Delete, `is_active=0`, M1 F-PLANT-4) und zeigt einen sonner-Undo-Toast „Pflanze gelöscht — Rückgängig" mit ~6 s Dauer. |
| **F-FE-DEL-2** | **Undo-Mechanik:** „Rückgängig" stellt die Pflanze wieder her. Da der Soft-Delete-Endpoint serverseitig kein Restore exponiert (M1-Baseline), nutzt das Frontend den **deferred-commit-Ansatz:** Der `DELETE`-Request wird erst nach Ablauf der Toast-Frist (oder beim Toast-Dismiss) abgesetzt; „Rückgängig" innerhalb der Frist canceled den ausstehenden Request und re-inserted die optimistisch entfernte Pflanze. Schließt der User die App vor Fristablauf, wird der Delete beim Unmount synchron nachgeholt (kein „Zombie"). *(Falls Backend in Phase A ein Restore/Reactivate ergänzt, darf alternativ sofort gelöscht + per Restore zurückgeholt werden; Verhalten nach außen identisch.)* |
| **F-FE-DEL-3** | **Kein Browser-`confirm()`** für Pflanzen-Löschung — der Undo-Toast ersetzt die Bestätigung. |
| **F-FE-DEL-4** | **Account — harter Dialog:** Account-Löschung (`DELETE /api/account`, Hard-Delete, M1 F-SET-5) nutzt einen **eigenen modalen Confirm-Dialog** (kein `window.confirm`). Anforderungen: explizite Warnung über Irreversibilität (Pflanzen, Bilder, Account), **Tipp-Bestätigung** (User muss das Wort `LÖSCHEN`/`DELETE` je nach Locale eintippen) ODER zweistufiger Bestätigungs-Button; primärer Zerstör-Button visuell als „danger" (rot) abgesetzt; „Abbrechen" als Default-Fokus. |
| **F-FE-DEL-5** | **Account-Lösch-Folge:** Nach Erfolg sofortiger Client-Logout: alle Query-Caches leeren (`queryClient.clear()`), Redirect `/login`, lokalisierter Bestätigungs-Toast. Cookies werden serverseitig invalidiert (M1). |

## 8.5 Theme-Politur + Light-Mode

| Req | Beschreibung |
|---|---|
| **F-FE-THEME-1** | **Themable Tokens:** Die heute in `@theme` hartkodierten Farben (`--color-pp-*`) werden zu CSS-Custom-Properties, die pro Theme über `[data-theme="dark"]` / `[data-theme="light"]` auf `:root`/`<html>` definiert werden. Tailwind-`@theme`-Tokens referenzieren diese Variablen, sodass bestehende `pp-*`-Utility-Klassen unverändert weiterfunktionieren. |
| **F-FE-THEME-2** | **Dark (Default):** bestehende Palette beibehalten — Dunkelgrün (`#0d2018`…`#1d4634`), Gold (`#e0b53d`), Vine-Wallpaper. Gilt als Default, wenn keine Wahl vorliegt. |
| **F-FE-THEME-3** | **Light-Mode:** neue, abgestimmte helle Pixel-Palette (heller Beige/Creme-Grund, kräftigeres Grün für Rahmen/Text, Gold-Akzent erhalten), ausreichender Kontrast (Text/Background ≥ WCAG AA 4.5:1 für Body-Text). Vine-Wallpaper im Light-Mode abgedimmt/optional ausgeblendet, damit Text lesbar bleibt. |
| **F-FE-THEME-4** | **Toggle + Persistenz:** Light/Dark-Umschalter (Settings + erreichbar im Header). Setzt `document.documentElement.dataset.theme`, persistiert in `localStorage("plantpal_theme")` **und**, falls eingeloggt, via `PATCH /api/settings { theme }` (→ `users.theme`, s. §8.8). Initial-Auflösung beim Boot: Server-`theme` (falls vorhanden) → `localStorage` → `prefers-color-scheme` → `dark`. Anwendung **vor** First Paint (Inline-Script/Init im `index.html` bzw. `main.tsx`) zur Vermeidung von Theme-Flash (FOUC). |
| **F-FE-THEME-5** | **Politur (gilt für beide Themes):** konsistente Abstände (Spacing-Skala), **Touch-Targets ≥ 44×44 px** (Buttons, Icon-Buttons, Wasser-Action), sichtbarer **`:focus-visible`-Ring** auf allen interaktiven Elementen (Tastatur-Bedienbarkeit), **Mobile-Safe-Areas** via `env(safe-area-inset-*)` (Notch/Home-Indicator) auf Header/Footer/Floating-Buttons. |
| **F-FE-THEME-6** | **`<meta name="theme-color">`** wird passend zum aktiven Theme gesetzt (Dark/Light), damit Browser-Chrome (mobil) und PWA-Statusbar harmonieren. |

## 8.6 Onboarding-Empty-State + CTA

| Req | Beschreibung |
|---|---|
| **F-FE-ONB-1** | **Erst-Empty-State:** Hat ein eingeloggter User **0 aktive Pflanzen**, zeigt die Plantdex-Page statt eines leeren Grids einen freundlichen Onboarding-Block: Pixel-Illustration/Maskottchen, lokalisierte Begrüßung, Erklärsatz. |
| **F-FE-ONB-2** | **Erste-Pflanze-CTA:** prominenter Primär-Button „Erste Pflanze hinzufügen" öffnet direkt das `AddPlantModal`. |
| **F-FE-ONB-3** | **2–3 Tipps:** kurze, lokalisierte Hinweisliste (z. B. „Foto wird zu einem 96×96-Pixel-Icon", „Setze ein realistisches Gieß-Intervall", „Aktiviere den Email-Reminder in den Einstellungen"). |
| **F-FE-ONB-4** | **Abgrenzung:** Der Onboarding-Empty-State erscheint **nur** bei insgesamt 0 Pflanzen — nicht bei leeren Such-/Filterergebnissen (das ist F-FE-LIST-6). Die THIRSTY-Section ist im Empty-State ausgeblendet. |
| **F-FE-ONB-5** | **Loading-Abgrenzung:** Während des initialen `GET /api/plants` werden Skeleton-Cards (M1) gezeigt; der Empty-State erscheint erst nach erfolgreichem Load mit leerer Liste (kein Flackern des Onboardings während des Ladens). |

## 8.7 PWA (installierbar, store-ready, TEMP-Icons)

| Req | Beschreibung |
|---|---|
| **F-FE-PWA-1** | **Plugin:** `vite-plugin-pwa` (Workbox) in `frontend/vite.config.ts`, `registerType: "autoUpdate"`. Generiert Service-Worker + injiziertes Manifest in den `dist`-Build (der von FastAPI als SPA aus `STATIC_DIR` ausgeliefert wird, M1 `spa.py`). |
| **F-FE-PWA-2** | **Manifest:** `name: "PlantPal"`, `short_name: "PlantPal"`, `start_url: "/"`, `scope: "/"`, `display: "standalone"`, `background_color`/`theme_color` passend zum Dark-Theme, `lang` neutral, Beschreibung lokalisiert-neutral. Installierbar auf Android/Chrome und iOS-Safari (Add-to-Home-Screen). |
| **F-FE-PWA-3** | **Icons (TEMP):** Platzhalter-Icons in `192×192`, `512×512` und ein `512×512` **maskable** (safe-zone-konform), plus `apple-touch-icon` (180×180). **Explizit temporär** — echtes Logo folgt später (eigene Iteration, Higgsfield MCP). Icons im `pixelated`-Stil, aber als statische PNGs unter `frontend/public/icons/`. Ein Code-Kommentar/TODO markiert sie als Platzhalter. |
| **F-FE-PWA-4** | **Service-Worker-Scope:** Precache nur den statischen App-Shell (JS/CSS/HTML/Fonts/Icons). **`/api/*` und `/auth/*` werden NICHT gecacht** (NetworkOnly) — keine veralteten/cross-user Daten, keine gecachten Auth-Antworten oder Bilder. Plant-Bilder (`/api/plants/{id}/image`) sind user-scoped und werden ebenfalls nicht vom SW gecacht. |
| **F-FE-PWA-5** | **Update-Flow:** Bei neuem SW (autoUpdate) übernimmt die App nach Reload die neue Version; optional dezenter „Neue Version verfügbar – neu laden"-Toast (lokalisiert). Kein Offline-Daten-Modus in v3 (Decision-Log: keine Web-Push; Offline bleibt wie M1 nur Verbindungs-Banner). |
| **F-FE-PWA-6** | **Store-ready-Kriterien:** valides Manifest (alle Pflichtfelder + Icons), HTTPS (Prod via Cloudflare-Tunnel), installierbares Lighthouse-PWA-Audit „pass" für Installability. **Keine** Web-Push-Registrierung, **keine** Notification-Permission-Abfrage. |

## 8.8 Status-Anzeige: Tropfen-Wasserstand *(Spec — Umsetzung später)*

Ersetzt konzeptionell die binäre Tropfen-Anzeige (M1 F-THIRST-4) durch eine graduelle. **In v3 noch nicht implementiert** — vollständig spezifiziert für die nachfolgende Iteration. Die Daten dafür liefert die bestehende Plant-Response bereits (`last_watered_at`, `interval_days`, `is_thirsty`, `days_overdue`); **kein Backend-Delta nötig**.

| Req | Beschreibung |
|---|---|
| **F-FE-DROP-1** | **Füllgrad-Modell:** `fill = clamp(elapsed / interval, 0, 1)` mit `elapsed = (now − last_watered_at)` in Tagen (Berlin-Tagesgranularität, konsistent zur Thirsty-Logik). `fill = 0` direkt nach dem Gießen, `fill → 1` bei Erreichen des Intervalls. |
| **F-FE-DROP-2** | **Darstellung:** Reihe fester Anzahl Tropfen-Icons (Vorgabe: 5). Anteilige Füllung = `round(fill · N)` volle Tropfen; verbleibende leer. Pixel-Stil, an der Plant-Card. |
| **F-FE-DROP-3** | **Überfällig-Zustand:** Sobald `is_thirsty` (also `days_overdue ≥ 0`), wird die Tropfen-Reihe durch eine **welke Blüte** ersetzt **und** „X Tage überfällig" lokalisiert angezeigt (`days_overdue`, Plural via F-I18N-7). |
| **F-FE-DROP-4** | **A11y:** semantisches Äquivalent (`aria-label`/`title`) mit Prozent bzw. „N Tage überfällig"; Information nicht ausschließlich über Farbe (Icon-Form + Text). |
| **F-FE-DROP-5** | **Migrationspfad:** Bis zur Umsetzung bleibt die binäre M1-Anzeige aktiv. Die Komponente wird isoliert (`WaterLevel`-Component) gebaut, sodass der Austausch ohne Page-Umbau möglich ist. |

## 8.9 Stats-UI (Teilmenge)

Backend liefert in v3 die **vollen** Kennzahlen (Decision-Log §3: Streak, Gieß-Konsistenz %, am-längsten-überfällig, Durchschnitts-Intervall — Backend-Baustein, getestet). Das Frontend zeigt **jetzt nur die Kernteilmenge**; der Rest (Charts/Verlauf/Konsistenz-%) folgt später.

| Req | Beschreibung |
|---|---|
| **F-FE-STAT-1** | **Sichtbar in v3:** (a) **Total Plants** (aktiv), (b) **Currently Thirsty** (Anzahl), (c) **Gieß-Streak** (aufeinanderfolgende Tage mit ≥1 Gießung, aus erweitertem Stats-Endpoint), (d) **am-längsten-überfällige Pflanze** (Name + `days_overdue`, oder leer-Hinweis wenn nichts überfällig). |
| **F-FE-STAT-2** | **Datenquelle:** erweiterter `GET /api/stats` (s. Delta unten). Das Frontend liest aus der vollen Response **nur** die vier Kernfelder; zusätzliche Felder werden ignoriert (vorwärtskompatibel, kein Breaking bei späterem Ausbau). |
| **F-FE-STAT-3** | **Darstellung:** Pixel-Stat-Kacheln (Grid), lokalisierte Labels, Plural-korrekt. Loading = Skeleton; Fehler = lokalisierter Retry. Bei 0 Pflanzen: dezenter Hinweis statt Nullen-Wand, mit Link zum Onboarding. |
| **F-FE-STAT-4** | **Bewusst NICHT in v3-UI:** Gieß-Konsistenz %, Durchschnitts-Intervall, Charts/History-Visualisierung. Diese sind backendseitig vorhanden und werden später nachgezogen — als TODO im Code markiert. |

## 8.10 Querschnitt / Konsistenz

| Req | Beschreibung |
|---|---|
| **F-FE-X-1** | **API-Client-Erweiterung (`frontend/src/api.ts`):** `updatePlant` um `location_room` erweitern; `updateSettings` von `{email_reminders_enabled}` auf das volle Settings-Patch-Objekt `{ email_reminders_enabled?, locale?, reminder_hour?, theme? }` (Partial) erweitern; `getStats` auf erweiterte Response typisieren. CSRF-/Credentials-Verhalten unverändert. |
| **F-FE-X-2** | **Typen (`frontend/src/types.ts`):** `Plant.location_room: string | null`; `UserSettings` um `locale`, `reminder_hour`, `theme`; `Stats` um die neuen Kernfelder (mind. `watering_streak_days`, `longest_overdue: {name, days_overdue} | null`) erweitern. |
| **F-FE-X-3** | **Settings-Page-Layout:** neue Settings gruppiert: „Sprache" (§8.1), „Theme" (§8.5), „Reminder" (Email-Toggle **plus** Reminder-Uhrzeit-Auswahl 0–23 → `reminder_hour`, Decision-Log §5), „Account" (Export — falls Frontend-Hook vorhanden — + Account löschen §8.4). Jede Mutation einzeln optimistisch + Rollback. |
| **F-FE-X-4** | **Footer & Legal-Links:** globaler Footer mit lokalisierten Links „Impressum" / „Datenschutz" (statische Seiten/Routen, Decision-Log §6). Reine Anzeige im Frontend; Inhalte als statische Routen `/impressum` (`/legal/notice`) und `/datenschutz` (`/legal/privacy`), beide ohne Auth erreichbar. |
| **F-FE-X-5** | **Kein Cookie-Banner:** Es werden ausschließlich technisch notwendige Cookies gesetzt (`plantpal_session`, `plantpal_csrf`) — keine Tracking-/Analytics-Cookies, keine `localStorage`-Nutzung zu Tracking-Zwecken (nur funktionale Locale/Theme-Spiegel). Daher entfällt ein Consent-Banner (Begründung im Datenschutz-Text, Decision-Log §6). |

## 8.11 Schema-/Config-/Endpoint-Deltas (relevant fürs Frontend)

> Vollständige Migration `002` und die Backend-Implementierung liegen im Backend-/Schema-Baustein. Hier nur die für das Frontend konsumierten Verträge.

**Schema (Auszug Migration `002`, idempotent, in `_migrations` getrackt):**

```sql
ALTER TABLE plants ADD COLUMN location_room TEXT;          -- ≤80 Zeichen (App-validiert)
ALTER TABLE users  ADD COLUMN locale       TEXT NOT NULL DEFAULT 'de';   -- 'de' | 'en'
ALTER TABLE users  ADD COLUMN theme        TEXT NOT NULL DEFAULT 'dark'; -- 'dark' | 'light'
ALTER TABLE users  ADD COLUMN reminder_hour INTEGER NOT NULL DEFAULT 8;  -- 0..23
```

**Pydantic-Modelle (`src/plantpal/models.py`) — Frontend-relevante Felder:**

```python
class PlantCreate / PlantUpdate:
    location_room: str | None = Field(default=None, max_length=80)

class PlantResponse:
    location_room: str | None

class SettingsResponse:
    email_reminders_enabled: bool
    reminder_channel: str
    locale: str          # 'de' | 'en'
    theme: str           # 'dark' | 'light'
    reminder_hour: int   # 0..23

class SettingsUpdate:                         # alle optional (partielles Patch)
    email_reminders_enabled: bool | None = None
    locale: str | None = Field(default=None, pattern="^(de|en)$")
    theme: str | None = Field(default=None, pattern="^(dark|light)$")
    reminder_hour: int | None = Field(default=None, ge=0, le=23)

class StatsResponse:                          # Backend voll; Frontend liest Teilmenge
    total_plants: int
    thirsty_count: int
    watering_streak_days: int
    longest_overdue: LongestOverdue | None    # { name: str, days_overdue: int }
    # + weitere Backend-Felder (consistency_pct, avg_interval_days, …) — v3-UI ignoriert sie
```

**Endpoints (bestehende, jetzt vom Frontend genutzt/erweitert):**

| Endpoint | Methode | v3-Frontend-Nutzung |
|---|---|---|
| `PATCH /api/plants/{id}` | PATCH | jetzt aus Edit-Modal aufgerufen; akzeptiert zusätzlich `location_room` |
| `POST /api/plants/{id}/image` | POST (multipart) | jetzt aus Edit-Modal (Bild-Tausch) aufgerufen |
| `GET /api/plants/{id}/image` | GET | Cache-Bust via Query-Param nach Tausch |
| `PATCH /api/settings` | PATCH | erweitertes Body-Schema (`locale`, `theme`, `reminder_hour`) |
| `GET /api/settings` | GET | liefert zusätzlich `locale`, `theme`, `reminder_hour` |
| `GET /api/stats` | GET | erweiterte Response; Frontend liest 4 Kernfelder |

**Frontend-Build (`frontend/`):** neue Dev-Deps `i18next`, `react-i18next`, `i18next-browser-languagedetector`, `vite-plugin-pwa`; neue Scripts `i18n:check`; `react-hook-form` (M1-Stack laut Konvention vorgesehen) wird für Edit-Form genutzt (ggf. als Dependency ergänzen, falls noch nicht installiert).

## 8.12 Akzeptanzkriterien (Frontend v3)

Frontend-AKs werden per **Vitest** (Komponenten/Logik) bzw. **Playwright** (E2E gegen Backend mit tmp-DB) verifiziert; reine Spec-Items (§8.8) sind als solche markiert und in v3 nicht test-pflichtig.

| ID | Szenario | Verifikation |
|---|---|---|
| **AK-FE-1** | **i18n-Default DE:** Browser-Locale `de-DE`, kein persistierter Wert → UI rendert deutsch; `<html lang>`=`de`. | `tests/e2e/i18n.spec.ts` |
| **AK-FE-2** | **i18n-EN-Detect:** Browser-Locale `en-US`, kein persistierter Wert → UI rendert englisch. | Vitest (detector init) |
| **AK-FE-3** | **i18n-Fallback:** Browser-Locale `fr` → UI fällt auf `de` zurück. | Vitest |
| **AK-FE-4** | **Sprach-Umschalter persistiert:** Settings → „English" → `PATCH /api/settings {locale:"en"}` gesendet, UI sofort englisch; Reload → bleibt englisch (aus Server-`locale`). | `tests/e2e/i18n.spec.ts` |
| **AK-FE-5** | **Key-Parität:** `npm run i18n:check` ist grün; künstliches Entfernen eines Keys aus `en.json` lässt den Check failen. | CI-Script-Test |
| **AK-FE-6** | **Keine Hardkodierung:** `me`-Lade-Text & mind. Buttons/Toasts kommen aus `t()` (kein literal „Lade…"). | Vitest (render-snapshot, key-presence) |
| **AK-FE-7** | **Plant-Edit-Felder:** Detail → „Bearbeiten" → `name`/`interval_days`/`notes`/`water_amount_ml`/`location_room` ändern → Speichern → `PATCH` nur mit geänderten Feldern → Liste/Detail zeigen neue Werte. | `tests/e2e/plant_edit.spec.ts` |
| **AK-FE-8** | **Bild-Tausch:** im Edit-Modal neues gültiges PNG wählen → `POST /api/plants/{id}/image` → Card-Bild aktualisiert (Cache-Bust greift, neue URL-Version). | `tests/e2e/plant_edit.spec.ts` |
| **AK-FE-9** | **Bild-Tausch-Client-Reject:** 11-MB-Datei oder `.txt` als Bild → lokalisierter Fehler-Toast, **kein** Request abgesetzt, Modal bleibt offen. | Vitest (Upload-Handler) |
| **AK-FE-10** | **Edit-Validierung:** `name` leer / `interval_days`=0 / `notes`>500 → Submit disabled + Inline-Fehler; kein Request. | Vitest |
| **AK-FE-11** | **Suche:** Tippen filtert über `name` und `location_room` (case-insensitive, debounced); leeres Feld zeigt alle. | Vitest |
| **AK-FE-12** | **Sortierung:** Umschalten Durst/Name/Zuletzt-gegossen ordnet das Grid entsprechend; Default = Durst (= Server-Order). | Vitest |
| **AK-FE-13** | **Thirsty-Filter:** Toggle „Nur durstige" zeigt ausschließlich `is_thirsty` und kombiniert sich mit Suche. | Vitest |
| **AK-FE-14** | **Leeres Filterergebnis ≠ Onboarding:** Suche ohne Treffer (bei >0 Pflanzen) → „Keine Pflanze passt" + Reset-Button; **nicht** der Onboarding-CTA. | Vitest |
| **AK-FE-15** | **Pflanze löschen + Undo:** „Löschen" → Pflanze sofort weg + Undo-Toast → „Rückgängig" innerhalb der Frist → Pflanze wieder da, **kein** `DELETE` am Server angekommen. | `tests/e2e/plant_delete.spec.ts` |
| **AK-FE-16** | **Pflanze löschen ohne Undo:** „Löschen" → Toast-Frist abgelaufen → `DELETE /api/plants/{id}` gesendet, Pflanze bleibt weg auch nach Reload. | `tests/e2e/plant_delete.spec.ts` |
| **AK-FE-17** | **Account-Lösch-Dialog:** „Account löschen" öffnet eigenen modalen Dialog (kein `window.confirm`); Zerstör-Button erst nach Tipp-Bestätigung aktiv. | Vitest |
| **AK-FE-18** | **Account-Lösch-Folge:** Bestätigung → `DELETE /api/account` → Caches geleert + Redirect `/login`. | `tests/e2e/account_delete.spec.ts` |
| **AK-FE-19** | **Theme-Toggle + Persistenz:** Light umschalten → `<html data-theme="light">` + `PATCH /api/settings {theme:"light"}`; Reload → bleibt light (aus Server-`theme`); `theme-color`-Meta aktualisiert. | `tests/e2e/theme.spec.ts` |
| **AK-FE-20** | **Kein Theme-Flash:** initiale Theme-Auflösung vor First Paint (data-theme bereits beim ersten gerenderten Frame gesetzt). | Vitest (boot-init unit) |
| **AK-FE-21** | **Onboarding-Empty-State:** frischer User, 0 Pflanzen, Load fertig → Onboarding mit „Erste Pflanze hinzufügen"-CTA + Tipps; THIRSTY-Section ausgeblendet. | `tests/e2e/onboarding.spec.ts` |
| **AK-FE-22** | **Onboarding nicht während Loading:** während `GET /api/plants` pending → Skeletons, **kein** Onboarding-Flash. | Vitest |
| **AK-FE-23** | **PWA-Manifest:** Build erzeugt valides `manifest.webmanifest` mit `name`, `short_name`, `start_url`, `display:standalone`, ≥1 maskable Icon. | Build-Assertion / Vitest (manifest parse) |
| **AK-FE-24** | **SW cached keine API/Auth:** Workbox-Runtime-Config enthält keine `/api`/`/auth`-Cache-Route (NetworkOnly); App-Shell precached. | Config-Assertion |
| **AK-FE-25** | **Stats-UI-Teilmenge:** `/stats` zeigt Total, Durstig, Streak, am-längsten-überfällig (Name + Tage); zusätzliche Backend-Felder werden nicht gerendert, ohne Fehler. | Vitest (mocked stats) |
| **AK-FE-26** | **Legal-Footer:** Footer zeigt lokalisierte „Impressum"/„Datenschutz"-Links; Routen ohne Auth erreichbar. | `tests/e2e/legal.spec.ts` |
| **AK-FE-27** | **Reminder-Uhrzeit:** Settings → Stunde 7 wählen → `PATCH /api/settings {reminder_hour:7}`; nach Reload selektiert 7. | `tests/e2e/settings.spec.ts` |
| **AK-FE-28** | **(Spec, später) Tropfen-Wasserstand:** Modell `fill=clamp(elapsed/interval,0,1)`, N=5 → korrekte Anzahl voller Tropfen; ab überfällig welke Blüte + „X Tage überfällig". *(Nicht in v3 implementiert — Akzeptanz greift erst bei Umsetzung der Komponente.)* | *(deferred)* |

## 8.13 Out-of-Scope (Frontend v3)

- Web-Push / Notification-Permissions (Decision-Log: nur Email-Reminder).
- Echtes Offline-Daten-Caching / Mutation-Queueing (nur Verbindungs-Banner wie M1; SW cached nur App-Shell).
- Finales Logo/Branding-Icons (TEMP-Platzhalter; echte Icons später via Higgsfield-MCP-Iteration).
- Tropfen-Wasserstand-**Implementierung** (nur Spec §8.8; binäre M1-Anzeige bleibt aktiv).
- Stats-Charts, Gieß-Konsistenz-% und Durchschnitts-Intervall in der UI (Backend liefert sie; UI später).
- Weitere Sprachen außer DE/EN; RTL-Layout.
- Standort-Gruppierung als eigene visuelle Sektion (Decision-Log nennt Gruppierung für Liste/Stats; in v3 deckt das Frontend `location_room` über Suchfeld + Edit ab — visuelle Gruppen-Header sind späterer Ausbau).

---

Quellen, die ich selbst gelesen habe (Ground Truth): `/home/kipoc/Schreibtisch/projects/plantpal/docs/PRD_M1.md`, `/home/kipoc/Schreibtisch/projects/plantpal/migrations/001_initial.sql`, `/home/kipoc/Schreibtisch/projects/plantpal/src/plantpal/config.py`, `/home/kipoc/Schreibtisch/projects/plantpal/src/plantpal/models.py`, `/home/kipoc/Schreibtisch/projects/plantpal/src/plantpal/main.py`, `/home/kipoc/Schreibtisch/projects/plantpal/README.md`, `/home/kipoc/Schreibtisch/projects/plantpal/docs/BACKEND_ARCHITECTURE.md`, sowie die bestehende Frontend-Baseline unter `/home/kipoc/Schreibtisch/projects/plantpal/frontend/` (`src/api.ts`, `src/types.ts`, `src/index.css`, `src/App.tsx`, `vite.config.ts`, `package.json`).



# Teil 5 — Datenmodell & Migration 002

# PlantPal PRD v3 — Baustein: Datenmodell & Migration 002

**Status:** v3 Draft — erweitert die implementierte M1-Baseline
**Stand:** 2026-06-03
**Basis:** Decision-Log v3 (Grill 2026-06-03) · Ground-Truth: `migrations/001_initial.sql`, `src/plantpal/{db,models,time_utils,config}.py`
**Scope dieses Bausteins:** Alle DB-Schema-Deltas für v3 (Gieß-Historie, Standort, User-Präferenzen, Mehrfach-Invites, Login-Code, Email-Change) als eine numbered Migration `002_v3.sql` + betroffene Pydantic-Modelle.

---

## D.0 Baseline (implementiert in M1)

Das v3-Schema **erweitert** das M1-Schema; es ersetzt nichts. Relevante Eigenschaften der Baseline (`001_initial.sql`), die jede v3-Änderung respektieren muss:

- Alle Tabellen: Surrogat-PK `id INTEGER PRIMARY KEY AUTOINCREMENT`.
- Tokens liegen als `token_hash TEXT UNIQUE` in DB (HMAC-SHA256, `TOKEN_PEPPER`), Klartext nur im Cookie/Link. Tabellen heißen `invite_tokens`, `login_tokens`, `sessions`.
- Datetimes: **naive Berlin** (`Europe/Berlin`), ISO-8601 ohne TZ-Suffix, in Python via `now_berlin()`/`to_iso()` gesetzt. **Nie** SQLite `CURRENT_TIMESTAMP`/`datetime('now')` (das wäre UTC).
- Email-Spalten: `COLLATE NOCASE`.
- Soft-Delete: `plants.is_active = 0`. User-Hard-Delete (`DELETE /api/account`) verlässt sich auf `ON DELETE CASCADE` der Kind-Tabellen.
- Migration-Runner (`db.run_migrations`): wendet jede `migrations/NNN_*.sql` **genau einmal** an, getrackt in `_migrations(filename PK, applied_at)`, pro Datei atomar (alle Statements + Marker in einer Transaktion, sonst Rollback). Der Runner splittet das Skript: er **entfernt zuerst alle `--`-Kommentare zeilenweise** (auch inline) und teilt dann an `;`. Daraus folgen **harte Constraints** für `002_v3.sql` (siehe F-DB-12).

---

## D.1 Functional Requirements — Schema-Deltas

### D.1.1 Gieß-Historie

| Req | Beschreibung |
|---|---|
| **F-DB-1** | **Neue Tabelle `waterings`** persistiert jedes Gieß-Ereignis als unveränderliche Append-Row. Spalten: `id INTEGER PK AUTOINCREMENT`, `plant_id INTEGER NOT NULL` (FK→`plants.id` `ON DELETE CASCADE`), `user_id INTEGER NOT NULL` (FK→`users.id` `ON DELETE CASCADE`), `watered_at TEXT NOT NULL` (naive Berlin), `created_at TEXT NOT NULL` (naive Berlin, Insert-Zeitpunkt). `user_id` ist denormalisiert mitgeführt (kein Join über `plants` für User-skopierte Stats-Queries nötig und überlebt einen späteren Plant-Hard-Delete-Pfad nicht — siehe F-DB-3). |
| **F-DB-2** | **Schreibpfad:** `POST /api/plants/{id}/water` schreibt **in einer Transaktion** (a) eine `waterings`-Row mit `watered_at = created_at = now_berlin()` **und** (b) `UPDATE plants SET last_watered_at = ?` auf denselben Wert. `plants.last_watered_at` bleibt der Single-Source-of-Truth für die Thirsty-Berechnung (F-THIRST-* unverändert); `waterings` ist die additive Historie für Stats. Beide Werte sind nach jedem Water-Call identisch. |
| **F-DB-3** | **Lösch-Semantik:** Soft-Delete einer Pflanze (`is_active=0`) lässt `waterings`-Rows **unangetastet** (Undo muss Historie wiederherstellen). Erst Plant-**Hard**-Delete (heute nur über User-Account-Hard-Delete-Kaskade) entfernt sie via `ON DELETE CASCADE`. Account-Hard-Delete (`DELETE /api/account`) entfernt `waterings` doppelt abgesichert (CASCADE über `plant_id` **und** über `user_id`). |
| **F-DB-4** | **Indexe:** `idx_waterings_plant ON waterings(plant_id, watered_at DESC)` (Historie/Avg-Intervall pro Pflanze) und `idx_waterings_user ON waterings(user_id, watered_at DESC)` (Streak/Konsistenz pro User). |

### D.1.2 Pflanzen-Standort

| Req | Beschreibung |
|---|---|
| **F-DB-5** | **`plants.location_room TEXT NULL`** — frei wählbarer Standort/Raum (z. B. „Wohnzimmer"). NULL = ohne Standort. Pydantic-Validierung `max_length=80`, getrimmt; leerer String → NULL (kein DB-CHECK, Validierung in `PlantCreate`/`PlantUpdate`). Dient Gruppierung in Liste & Stats (Frontend-Baustein). Default existierender Rows: NULL (ALTER ADD COLUMN ohne DEFAULT). |

### D.1.3 User-Präferenzen

| Req | Beschreibung |
|---|---|
| **F-DB-6** | **`users.invite_quota INTEGER NOT NULL DEFAULT 3`** — verbleibendes Einlade-Kontingent. Jeder User darf einladen (Decision-Log §2). Quota wird beim **Erstellen** eines Invite-Links dekrementiert, nicht pro Redemption (ein Mehrfach-Link kostet 1 Quota — siehe F-DB-9 / Auth-Baustein). `CHECK (invite_quota >= 0)`. Bestehende M1-User erhalten beim Migrieren 3. |
| **F-DB-7** | **`users.locale TEXT NOT NULL DEFAULT 'de'`** mit `CHECK (locale IN ('de','en'))` — gewählte Sprache für UI-Default-Sync & **lokalisierte Mail-Templates** (Magic-Link, Login-Code, Reminder). Browser-Locale ist nur Erst-Default im Frontend; persistierte Quelle für serverseitige Mails ist diese Spalte. |
| **F-DB-8** | **`users.reminder_hour INTEGER NOT NULL DEFAULT 8`** mit `CHECK (reminder_hour BETWEEN 0 AND 23)` — pro-User wählbare Reminder-Stunde (Berlin, fix TZ). Ersetzt die globale `REMINDER_HOUR_BERLIN`-Semantik als **Per-User-Wert**; der Config-Wert bleibt nur noch als Spalten-Default-Fallback (Reminder-Baustein: Cron läuft stündlich, filtert `reminder_hour = aktuelle_Berlin_Stunde`). `users.theme TEXT NOT NULL DEFAULT 'dark'` mit `CHECK (theme IN ('dark','light'))` — persistierte Theme-Präferenz (optional vom Frontend genutzt; Hauptspeicher bleibt clientseitig, Spalte synchronisiert Cross-Device). |

### D.1.4 Mehrfach-Invite-Links + Redemptions

| Req | Beschreibung |
|---|---|
| **F-DB-9** | **`invite_tokens.max_uses INTEGER NOT NULL DEFAULT 1`** + **`invite_tokens.used_count INTEGER NOT NULL DEFAULT 0`** mit `CHECK (max_uses >= 1)` und `CHECK (used_count >= 0 AND used_count <= max_uses)`. Ein Invite ist **einlösbar**, solange `used_count < max_uses AND revoked_at IS NULL AND expires_at > now`. Das bestehende `used_at`/`used_by_user_id`-Spaltenpaar bleibt erhalten und wird nun als **„zuletzt/erstmals eingelöst"-Marker** weitergeführt (Backward-Compat zu M1-Code, der den Einmal-Token-Pfad nutzte): `used_at` wird beim **ersten** Redeem gesetzt; ein Invite mit `max_uses=1` verhält sich exakt wie der M1-Einmal-Token. Default existierender M1-Invites: `max_uses=1`, `used_count = (used_at IS NOT NULL ? 1 : 0)` — siehe F-DB-13 (Daten-Backfill in der Migration). |
| **F-DB-10** | **Neue Tabelle `invite_redemptions`** trackt jede Einlösung: `id INTEGER PK`, `invite_id INTEGER NOT NULL` (FK→`invite_tokens.id` `ON DELETE CASCADE`), `user_id INTEGER NOT NULL` (FK→`users.id` `ON DELETE CASCADE`), `redeemed_at TEXT NOT NULL` (naive Berlin). `UNIQUE (invite_id, user_id)` — derselbe User kann denselben Link nicht doppelt einlösen. Index `idx_invite_redemptions_invite ON invite_redemptions(invite_id)`. Der atomare Redeem-Pfad (Auth-Baustein) macht in einer `BEGIN IMMEDIATE`-Transaktion: `UPDATE invite_tokens SET used_count = used_count + 1, used_at = COALESCE(used_at, ?), used_by_user_id = ? WHERE id = ? AND used_count < max_uses AND revoked_at IS NULL AND expires_at > ?` → bei `rowcount==1` Insert in `invite_redemptions`. |

### D.1.5 Login-Code (6-stellig) als Magic-Link-Alternative

| Req | Beschreibung |
|---|---|
| **F-DB-11** | **`login_tokens.code TEXT NULL`** + **`login_tokens.attempt_count INTEGER NOT NULL DEFAULT 0`**. `code` ist der **HMAC-Hash** (gleiche `hash_token`-Funktion wie `token_hash`, mit `TOKEN_PEPPER`) eines 6-stelligen numerischen Codes — **nie Klartext** (Decision-Log §2 „SICHERHEIT: an login_token/email gebunden"). Beide Werte (`token_hash` für den Link, `code` für die manuelle Eingabe) gehören zu **derselben** `login_tokens`-Row und teilen `email`, `expires_at`, `used_at` → eine Mail enthält Link UND Code, beide lösen dieselbe Anmeldung aus; das erste eingelöste invalidiert das andere atomar (`used_at`-Set). `attempt_count` zählt **Fehlversuche** der Code-Eingabe; ab Schwelle (Auth-Baustein, `LOGIN_CODE_MAX_ATTEMPTS`, Default 5) wird die Row als verbraucht behandelt (Lockout). `code` ist NULL für M1-Tokens und für Tokens, die ohne Code-Pfad erzeugt würden. **Kein** `UNIQUE` auf `code` (6 Ziffern kollidieren über die Zeit; Bindung erfolgt über `email`+`code`+Gültigkeit, nicht global). Index `idx_login_tokens_code ON login_tokens(email, expires_at) WHERE used_at IS NULL AND code IS NOT NULL` für die Lookup-Query der Code-Verifikation. |

### D.1.6 Email-Änderung

| Req | Beschreibung |
|---|---|
| **F-DB-12** | **Neue Tabelle `email_change_requests`** für den verifizierten Email-Wechsel (Verify-Mail an die **neue** Adresse; Auth-Baustein). Spalten: `id INTEGER PK`, `user_id INTEGER NOT NULL` (FK→`users.id` `ON DELETE CASCADE`), `new_email TEXT NOT NULL COLLATE NOCASE`, `token_hash TEXT NOT NULL UNIQUE` (HMAC des Verify-Tokens im Bestätigungslink), `code TEXT NULL` (HMAC eines optionalen 6-stelligen Codes, analog F-DB-11), `expires_at TEXT NOT NULL`, `used_at TEXT NULL`, `created_at TEXT NOT NULL`. Indexe: `idx_email_change_user ON email_change_requests(user_id)` und `idx_email_change_unused ON email_change_requests(expires_at) WHERE used_at IS NULL`. Eindeutigkeit der finalen Adresse wird beim Commit gegen `users.email UNIQUE` erzwungen (Race-Schutz im Auth-Service per `BEGIN IMMEDIATE`); diese Tabelle hält **kein** `UNIQUE(new_email)`, da parallele Requests auf dieselbe Zieladresse zulässig sind, aber nur der erste Commit gewinnt. |

### D.1.7 Migrations-Mechanik (binding)

| Req | Beschreibung |
|---|---|
| **F-DB-13** | **`migrations/002_v3.sql`** ist die einzige neue Migration. Sie wird vom bestehenden Runner getrackt (Eintrag in `_migrations`) und läuft **genau einmal** je DB. **Idempotenz auf Datei-Ebene** kommt vom Tracker; zusätzlich nutzt das Skript `CREATE TABLE IF NOT EXISTS` und `CREATE INDEX IF NOT EXISTS` als Belt-and-Suspenders. **Achtung SQLite-Eigenheit:** `ALTER TABLE … ADD COLUMN` kennt **kein** `IF NOT EXISTS` — ein erneutes Ausführen würde fehlschlagen. Das ist akzeptabel und beabsichtigt: Der Tracker garantiert, dass die `ALTER`-Statements nie zweimal laufen (Re-Run wird per `_migrations`-Filter übersprungen). Würde ein Betreiber 002 manuell/teilweise re-applyen, ist das ein Bedienfehler außerhalb des Idempotenz-Vertrags. Der **Daten-Backfill** für `used_count` bestehender Invites (F-DB-9) erfolgt im selben Skript per `UPDATE invite_tokens SET used_count = 1 WHERE used_at IS NOT NULL`. |
| **F-DB-14** | **Runner-Kompatibilität (HARTE Regeln für das SQL-Skript):** (a) **Keine** `--`-Kommentare, die ein `;` enthalten (der Runner schneidet Kommentare zeilenweise ab, splittet dann an `;` — ein `;` im Kommentar ist bereits entfernt, aber zur Sicherheit meiden). (b) **Jedes** Statement endet mit `;`. (c) **Keine** Trigger, **keine** `BEGIN/COMMIT` im Skript (der Runner umklammert selbst mit einer Transaktion), **keine** `;` innerhalb von String-Literalen. (d) `CHECK`-Constraints, die in einer Column-Definition stehen, sind erlaubt; neue CHECKs auf **bestehende** Spalten via `ALTER` sind in SQLite nicht möglich und werden daher nur auf **neuen** Spalten/Tabellen definiert. |

---

## D.2 `migrations/002_v3.sql` (vollständig, konkret)

> Konventionsgemäß: naive-Berlin-Datetimes werden von Python gesetzt (kein `CURRENT_TIMESTAMP`). Das Skript erfüllt F-DB-14 (jedes Statement `;`-terminiert, keine Trigger, keine Transaktionsklammern, keine `;` in Kommentaren/Literalen).

```sql
-- PlantPal migration 002 (v3). Extends the M1 baseline. Datetimes are naive Berlin,
-- set by Python; this script never calls CURRENT_TIMESTAMP. Tracked once in _migrations.

-- 1. Watering history (F-DB-1 .. F-DB-4)
CREATE TABLE IF NOT EXISTS waterings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plant_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  watered_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (plant_id) REFERENCES plants(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_waterings_plant ON waterings(plant_id, watered_at DESC);
CREATE INDEX IF NOT EXISTS idx_waterings_user ON waterings(user_id, watered_at DESC);

-- 2. Plant location (F-DB-5)
ALTER TABLE plants ADD COLUMN location_room TEXT;

-- 3. User preferences (F-DB-6 .. F-DB-8)
ALTER TABLE users ADD COLUMN invite_quota INTEGER NOT NULL DEFAULT 3 CHECK (invite_quota >= 0);
ALTER TABLE users ADD COLUMN locale TEXT NOT NULL DEFAULT 'de' CHECK (locale IN ('de', 'en'));
ALTER TABLE users ADD COLUMN reminder_hour INTEGER NOT NULL DEFAULT 8 CHECK (reminder_hour BETWEEN 0 AND 23);
ALTER TABLE users ADD COLUMN theme TEXT NOT NULL DEFAULT 'dark' CHECK (theme IN ('dark', 'light'));

-- 4. Multi-use invite links (F-DB-9)
ALTER TABLE invite_tokens ADD COLUMN max_uses INTEGER NOT NULL DEFAULT 1 CHECK (max_uses >= 1);
ALTER TABLE invite_tokens ADD COLUMN used_count INTEGER NOT NULL DEFAULT 0 CHECK (used_count >= 0);
UPDATE invite_tokens SET used_count = 1 WHERE used_at IS NOT NULL;

-- 5. Invite redemptions (F-DB-10)
CREATE TABLE IF NOT EXISTS invite_redemptions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  invite_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  redeemed_at TEXT NOT NULL,
  FOREIGN KEY (invite_id) REFERENCES invite_tokens(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  UNIQUE (invite_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_invite_redemptions_invite ON invite_redemptions(invite_id);

-- 6. Login code alternative (F-DB-11): code is an HMAC hash, never plaintext
ALTER TABLE login_tokens ADD COLUMN code TEXT;
ALTER TABLE login_tokens ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_login_tokens_code ON login_tokens(email, expires_at)
  WHERE used_at IS NULL AND code IS NOT NULL;

-- 7. Email change requests (F-DB-12)
CREATE TABLE IF NOT EXISTS email_change_requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  new_email TEXT NOT NULL COLLATE NOCASE,
  token_hash TEXT NOT NULL UNIQUE,
  code TEXT,
  expires_at TEXT NOT NULL,
  used_at TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_email_change_user ON email_change_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_email_change_unused ON email_change_requests(expires_at)
  WHERE used_at IS NULL;
```

> **Hinweis CHECK-on-ADD-COLUMN:** SQLite erlaubt einen `CHECK`-Constraint **innerhalb** einer `ADD COLUMN`-Definition (gilt für ab dann eingefügte/aktualisierte Rows). Bestehende Rows erhalten den `NOT NULL DEFAULT`-Wert und erfüllen den CHECK trivial. Das ist verifiziert kompatibel mit dem zeilenweisen Statement-Splitter des Runners, da jede `ALTER`-Zeile ein einzelnes `;`-terminiertes Statement ist.

---

## D.3 Betroffene Pydantic-Modelle (`src/plantpal/models.py`)

Pydantic-Modelle sind zugleich DB-Row-Mapping **und** API-Schema (Konvention). v3-Deltas (Felder, die andere Bausteine als API-Vertrag konsumieren):

```python
# --- Plants ---  (location_room ergänzt)
class PlantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    interval_days: int = Field(ge=1, le=365)
    notes: str | None = Field(default=None, max_length=500)
    water_amount_ml: int | None = Field(default=None, ge=1, le=5000)
    location_room: str | None = Field(default=None, max_length=80)  # NEW (F-DB-5)

class PlantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    interval_days: int | None = Field(default=None, ge=1, le=365)
    notes: str | None = Field(default=None, max_length=500)
    water_amount_ml: int | None = Field(default=None, ge=1, le=5000)
    location_room: str | None = Field(default=None, max_length=80)  # NEW

class PlantResponse(BaseModel):
    id: int
    name: str
    interval_days: int
    image_url: str | None
    last_watered_at: str
    created_at: str
    notes: str | None
    water_amount_ml: int | None
    location_room: str | None      # NEW
    is_thirsty: bool
    days_overdue: int

# --- Settings ---  (locale / reminder_hour / theme + email read; reminders unverändert)
class SettingsResponse(BaseModel):
    email: str
    email_reminders_enabled: bool
    reminder_channel: str
    locale: str                    # NEW (F-DB-7)
    reminder_hour: int             # NEW (F-DB-8)
    theme: str                     # NEW (F-DB-8)
    invite_quota: int              # NEW (F-DB-6) — read-only Anzeige im Settings-UI

class SettingsUpdate(BaseModel):
    email_reminders_enabled: bool | None = None      # nun optional (Partial-Update)
    locale: Literal["de", "en"] | None = None        # NEW
    reminder_hour: int | None = Field(default=None, ge=0, le=23)  # NEW
    theme: Literal["dark", "light"] | None = None    # NEW

# --- Invites ---  (Mehrfach-Link: max_uses + Restkontingent)
class InviteCreateRequest(BaseModel):
    email_hint: str | None = Field(default=None, max_length=200)
    max_uses: int = Field(default=1, ge=1, le=50)    # NEW (F-DB-9)

class InviteResponse(BaseModel):
    invite_url: str
    expires_at: str
    max_uses: int                  # NEW
    used_count: int                # NEW
    remaining_quota: int           # NEW — users.invite_quota nach Erzeugung

# --- Watering history (neues Read-Modell, vom Stats/Plant-Detail-Baustein genutzt) ---
class WateringEntry(BaseModel):    # NEW (F-DB-1)
    id: int
    watered_at: str

# --- Login code + Email change (vom Auth-Baustein konsumiert) ---
class LoginCodeVerifyRequest(BaseModel):   # NEW (F-DB-11)
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")

class EmailChangeRequestBody(BaseModel):   # NEW (F-DB-12)
    new_email: EmailStr
```

> `Literal` und `WateringEntry` erfordern den Import `from typing import Literal`. Die Auth-/Settings-/Stats-Bausteine spezifizieren die zugehörigen Endpoints; dieser Baustein liefert nur die Datenträger-Schemas, die direkt aus den Schema-Deltas folgen.

---

## D.4 Akzeptanzkriterien

Jede AK ist als Backend-Test (pytest + pytest-asyncio + httpx ASGI, `conftest` `db`/`client`-Fixtures, `mode=auto`) verifizierbar. Test-IDs setzen die M1-Nummerierung fort.

| ID | Szenario | Test-Datei (Vorschlag) |
|---|---|---|
| **AK-M2-1** | **Migration idempotent & getrackt:** Frische M1-DB → `run_migrations` → `002_v3.sql` steht in `_migrations`; zweiter `run_migrations`-Aufruf ist No-Op (kein Fehler, keine doppelten Spalten). | `tests/test_migration_002.py::test_applies_once` |
| **AK-M2-2** | **Alle Spalten/Tabellen existieren:** Nach 002 hat `plants` `location_room`; `users` hat `invite_quota,locale,reminder_hour,theme`; `invite_tokens` hat `max_uses,used_count`; `login_tokens` hat `code,attempt_count`; `waterings`, `invite_redemptions`, `email_change_requests` existieren. (`PRAGMA table_info` / `sqlite_master`.) | `tests/test_migration_002.py::test_schema_shape` |
| **AK-M2-3** | **Defaults für Bestandsdaten:** Ein vor 002 angelegter User hat nach Migration `invite_quota=3`, `locale='de'`, `reminder_hour=8`, `theme='dark'`. | `tests/test_migration_002.py::test_user_defaults` |
| **AK-M2-4** | **Invite-Backfill:** Ein vor 002 als `used_at` markierter Invite hat nach Migration `used_count=1`, `max_uses=1`; ein unbenutzter hat `used_count=0`. | `tests/test_migration_002.py::test_invite_backfill` |
| **AK-M2-5** | **Water schreibt Historie + Spiegel:** `POST /api/plants/{id}/water` erzeugt **eine** `waterings`-Row und setzt `plants.last_watered_at` auf denselben `now_berlin()`-Wert; zweimal Gießen → zwei Rows, `last_watered_at` = letzter Wert. | `tests/test_watering_history.py::test_water_writes_history` |
| **AK-M2-6** | **Soft-Delete bewahrt Historie:** Pflanze gießen → soft-delete (`is_active=0`) → `waterings`-Rows bleiben; Account-Hard-Delete → `waterings`-Rows weg (CASCADE). | `tests/test_watering_history.py::test_softdelete_keeps_hard_cascade` |
| **AK-M2-7** | **CHECK greift:** `INSERT`/`UPDATE` mit `users.locale='fr'`, `reminder_hour=24`, `theme='blue'`, `invite_quota=-1` oder `invite_tokens.max_uses=0` → `IntegrityError`. | `tests/test_migration_002.py::test_checks_enforced` |
| **AK-M2-8** | **Redemption-Uniqueness:** Zweimal `invite_redemptions` mit gleichem `(invite_id,user_id)` → `IntegrityError`; `used_count` lässt sich nicht über `max_uses` treiben (conditional `UPDATE` liefert `rowcount=0`). | `tests/test_invite_multiuse.py::test_redemption_unique` |
| **AK-M2-9** | **Berlin-TZ-Stempel:** `waterings.watered_at`/`created_at` sind naive Berlin-ISO ohne TZ-Suffix und matchen `now_berlin()` (kein UTC-Versatz). | `tests/test_watering_history.py::test_naive_berlin` |
| **AK-M2-10** | **Login-Code-Hash:** Eine erzeugte `login_tokens`-Row mit Code hält in `code` **nicht** die Klartext-Ziffern (HMAC ≠ 6 Digits); `idx_login_tokens_code` existiert. | `tests/test_migration_002.py::test_login_code_hashed_index` |

---

## D.5 Hinweise an abhängige Bausteine

- **Auth-Baustein:** konsumiert F-DB-9/10 (atomarer Multi-Use-Redeem + `invite_redemptions`), F-DB-11 (`login_tokens.code`/`attempt_count`, Lockout über `attempt_count`, Config `LOGIN_CODE_MAX_ATTEMPTS=5`, `LOGIN_CODE_TTL_MIN` ≤ `LOGIN_TOKEN_TTL_MIN`), F-DB-12 (`email_change_requests`-Flow, `BEGIN IMMEDIATE` + `users.email UNIQUE` als finaler Race-Schutz) sowie F-DB-6 (Quota-Dekrement bei Invite-Erzeugung im User-Settings-UI).
- **Reminder-Baustein:** konsumiert F-DB-8 (`users.reminder_hour`); der stündliche Cron filtert User mit `reminder_hour = aktuelle_Berlin_Stunde` und `reminder_last_sent_date < today`. `users.locale` (F-DB-7) wählt das Mail-Template.
- **Frontend/Stats-Baustein:** konsumiert `waterings` (F-DB-1) für Streak/Konsistenz/Avg-Intervall, `plants.location_room` (F-DB-5) für Gruppierung, `users.theme`/`users.locale` (F-DB-7/8) für persistierte Präferenzen.
- **DB-Hygiene-Cron (Deploy-Baustein):** muss zusätzlich abgelaufene `email_change_requests` (`used_at IS NULL AND expires_at < now`) und vollständig aufgebrauchte/abgelaufene `invite_tokens` (`used_count >= max_uses OR expires_at < now`) löschen; `invite_redemptions` und `waterings` werden **nicht** vom Housekeeping angefasst (Historie/Audit bleibt).

**Relevante Dateien (absolut):**
- Neu: `/home/kipoc/Schreibtisch/projects/plantpal/migrations/002_v3.sql`
- Geändert: `/home/kipoc/Schreibtisch/projects/plantpal/src/plantpal/models.py`
- Unverändert genutzt (Mechanik): `/home/kipoc/Schreibtisch/projects/plantpal/src/plantpal/db.py`, `/home/kipoc/Schreibtisch/projects/plantpal/src/plantpal/time_utils.py`



# Teil 6 — Deployment & Betrieb v3

# Deployment & Betrieb v3

**Status:** PRD v3 — Baustein „Deployment & Betrieb" (erweitert die M1-Baseline)
**Stand:** 2026-06-03
**Basis:** Decision-Log v3 (Grill 2026-06-03), §1 Hosting & Betrieb + §7 Delivery (Phase D)
**Vorgängerdoku:** [`docs/PRD_M1.md`](PRD_M1.md) §5 (NFR-2/3/4/8/9), §7 Infra, §9 Config

> **Einordnung:** M1 ist vollständig implementiert und deployt **noch nie** (lief nur lokal). Dieser Baustein ist der erste echte Production-Go-Live. Er **ersetzt** die M1-Reverse-Proxy-Strategie (Caddy + Let's Encrypt + offene Ports 80/443) durch **Cloudflare Tunnel** und **ersetzt** Litestream als Default-Backup durch einen **Cron-basierten Snapshot+rsync** (DB **und** Bilder). Alles andere aus M1 (Single-Worker, SQLite WAL, APScheduler-Digest, `/api/health`, CLI-Bootstrap) bleibt unverändert gültig.

---

## D.1 Overview

### Problem
PlantPal soll von „läuft lokal auf `localhost:8000`" zu einer öffentlich erreichbaren Community-Instanz (100–1000 User) auf einem Pi/Mini-PC zuhause werden — **ohne** Portfreigaben im Heimrouter, mit gültigem TLS, verifizierter Absender-Domain für Mails, robustem Backup von **Daten und Bildern** sowie Außen-Monitoring.

### Solution
- **Ingress** via **Cloudflare Tunnel** (`cloudflared`-Container): kein offener Port am Heimanschluss, kein eigenes Zertifikatsmanagement. Cloudflare terminiert TLS am Edge; der Tunnel reicht den Klartext-Request an die App auf **`127.0.0.1`** im Compose-Netzwerk weiter.
- **Domain** `getplantpal.com`, registriert beim **Cloudflare-Registrar** (DNS, Tunnel-Routing, Edge-TLS aus einer Hand).
- **Mail** über Resend mit **eigener verifizierter Domain** (`getplantpal.com`): SPF + DKIM + DMARC, damit Magic-Link- und Reminder-Mails zustellbar sind und nicht im Spam landen.
- **Backup** als **täglicher Cron** auf dem Host: `sqlite3 .backup` (konsistenter Snapshot trotz WAL) + `rsync` von **DB-Snapshot UND `data/images/`** auf ein zweites Ziel. **Litestream entfällt als Default** (optional/abschaltbar belassen, siehe D.6).
- **Monitoring** zweistufig: **`structlog`** für strukturierte App-Logs (in M1 war structlog nur im Stack gelistet, aber **nicht verdrahtet** — v3 verdrahtet es real) + **UptimeRobot** als externer Heartbeat auf `GET /api/health`.

### Goals
1. Öffentlich erreichbar über `https://getplantpal.com` ohne Router-Portforwarding.
2. Gültiges, automatisch erneuertes TLS (Cloudflare Edge).
3. Zustellbare Mails (SPF/DKIM/DMARC grün, kein Spam-Foldering im Standardfall).
4. Tägliches, **wiederherstellbares** Backup von DB **und** Bildern auf zweitem Medium.
5. Außen-Monitoring meldet Ausfall < 5 min nach Eintritt.
6. Strukturierte Logs ohne PII/Secrets, Log-Level per ENV.
7. Reproduzierbarer Deploy nach README in einem Durchlauf.

### Non-Goals (v3)
- Kein Kubernetes, kein Multi-Host, kein Load-Balancer (Single-Box, Single-Worker bleibt — SQLite-Constraint aus M1).
- Kein Postgres (Decision-Log §1: WAL + serialisierter Writer reicht).
- Kein Cloudflare-Zero-Trust-Access-Gate vor der App (PlantPal hat eigene Auth; Tunnel ist reiner Ingress).
- Kein Self-hosted-SMTP (Resend bleibt, provider-agnostisch gekapselt).
- Keine Web-Push-/Status-Page-Infrastruktur über UptimeRobot hinaus.

---

## D.2 Functional Requirements

### D.2.1 Cloudflare Tunnel & Ingress

| Req | Beschreibung |
|---|---|
| **F-DEP-1** | **`cloudflared`-Service** wird als Container in `docker-compose.yml` aufgenommen (`image: cloudflare/cloudflared:latest`, `restart: unless-stopped`, `command: tunnel run`). Authentifizierung **token-basiert** via `TUNNEL_TOKEN` aus `.env` (Named Tunnel, in Cloudflare-Dashboard erstellt) — **keine** `cert.pem`/Credentials-Datei im Repo. |
| **F-DEP-2** | **Caddy entfällt.** Der `caddy`-Service, die Volumes `caddy-data`/`caddy-config` und die `Caddyfile` werden aus `docker-compose.yml` entfernt. Die Ports-Mappings **`80:80` und `443:443` werden ersatzlos gestrichen** — am Host wird kein eingehender Port mehr geöffnet. |
| **F-DEP-3** | **App nur Loopback.** Der `plantpal`-Service exponiert seinen Port **nicht** mehr per `ports:` nach außen. Erreichbarkeit ausschließlich über das interne Compose-Netz (Service-DNS-Name `plantpal:8000`), das `cloudflared` als Origin nutzt. Optionales `127.0.0.1:8000:8000`-Mapping nur für lokale Host-Health-Checks/Debug, niemals `0.0.0.0`. |
| **F-DEP-4** | **Tunnel-Routing** zeigt `getplantpal.com` (und optional `www.`) auf `http://plantpal:8000`. Konfiguriert wahlweise (a) im Cloudflare-Dashboard (Public Hostname → Service `http://plantpal:8000`) oder (b) lokal via `config.yml` (`ingress:`-Regeln) gemountet in den `cloudflared`-Container. README dokumentiert Variante (a) als Default. |
| **F-DEP-5** | **TLS-Mode = „Full (strict)" ODER „Full".** Da das Origin (App) HTTP auf Loopback spricht, terminiert Cloudflare TLS am Edge; der Tunnel selbst ist bereits TLS-gesichert (Origin-Pull über das Cloudflare-Backbone). Cloudflare-Edge-Zertifikat (Universal SSL) deckt `getplantpal.com` ab — kein Let's-Encrypt-Handling mehr in der App-Infra. |
| **F-DEP-6** | **`BASE_URL` bleibt `https://getplantpal.com`.** Obwohl die App intern HTTP/Loopback bedient, ist die öffentliche URL HTTPS. `Settings.secure_cookies` ⇒ `True` (greift über `BASE_URL.startswith("https://")`), `validate_runtime()` akzeptiert die Config (kein `localhost`/`127.0.0.1` in `BASE_URL`). **Kein** Code-Change an `config.py` nötig. |
| **F-DEP-7** | **Client-IP via `CF-Connecting-IP`.** Hinter dem Tunnel ist `request.client.host` die Container-interne Adresse. Damit IP-basiertes Rate-Limiting (`RL_LOGIN_REQUEST_IP`, `RL_LOGIN_VERIFY_IP`) wieder pro echtem Client greift, liest der `_client_ip()`-Pfad in `main.py` zuerst den Header **`CF-Connecting-IP`** (Fallback `request.client.host`), bevor er via `hash_ip()` gehasht wird. Quelle wird per Config-Flag `TRUST_CF_CONNECTING_IP: bool = True` abgesichert (im Tunnel-Setup immer vertrauenswürdig, da der einzige Ingress Cloudflare ist). |
| **F-DEP-8** | **Origin-Lockdown:** Da nur `cloudflared` das Origin erreicht und der Host keinen Port öffnet, ist die App von außen ausschließlich über Cloudflare erreichbar (kein direkter Origin-Zugriff möglich). Die M1-CSRF-Origin/Referer-Prüfung (`_origin_allowed` gegen `BASE_URL`) bleibt unverändert wirksam. |

### D.2.2 Domain & Mail-Domain-Verifizierung

| Req | Beschreibung |
|---|---|
| **F-DEP-9** | **Domain `getplantpal.com`** via Cloudflare-Registrar; DNS-Zone bei Cloudflare. Alle weiteren DNS-Records (Tunnel-CNAME automatisch durch `cloudflared`, Mail-Records) liegen in derselben Zone. |
| **F-DEP-10** | **Resend-Domain-Verifizierung** für `getplantpal.com`: die von Resend ausgegebenen DNS-Records werden in Cloudflare gesetzt — **SPF** (TXT `v=spf1 include:...resend... ~all`), **DKIM** (CNAME/TXT je nach Resend-Vorgabe), und ein **DMARC**-Record (TXT `_dmarc`, mind. `v=DMARC1; p=none; rua=mailto:dmarc@getplantpal.com` als Startpolicy). README listet die konkreten Record-Typen + den Verifikations-Klick in Resend. |
| **F-DEP-11** | **`RESEND_FROM_EMAIL`** wird auf eine Adresse der **verifizierten** Domain gesetzt, z. B. `PlantPal <noreply@getplantpal.com>`. Der M1-Default `noreply@localhost` ist Production-untauglich und wird in `.env.example` entsprechend ersetzt. |
| **F-DEP-12** | **Provider-Agnostik bleibt:** Versand läuft weiter ausschließlich über `email_service.py` (Resend-HTTP-API). Kein Resend-spezifischer Aufruf außerhalb dieses Moduls — Domain-Verifizierung ändert nur DNS + `RESEND_FROM_EMAIL`, keinen App-Code. |
| **F-DEP-13** | **Resend-Free-Limit dokumentiert:** Free = 100 Mails/**Tag**. Bei 100–1000 Usern kann ein Reminder-Tag das Limit überschreiten. README + `.env.example` weisen darauf hin; Upgrade auf Resend Pro ist eine reine Account-/`RESEND_API_KEY`-Änderung ohne Code-Change. (Reminder-Versandlogik selbst bleibt M1: idempotent via `reminder_send_log`, Retry bei 429.) |

### D.2.3 Backup (Snapshot + rsync, DB UND Bilder)

| Req | Beschreibung |
|---|---|
| **F-DEP-14** | **Backup-Cron auf dem Host** (nicht im App-Container): täglich um eine konfigurierbare Uhrzeit (Default 03:30 lokal). Ein Skript `scripts/backup.sh` führt aus: (1) konsistenter SQLite-Snapshot via `docker compose exec -T plantpal sqlite3 /data/plantpal.db ".backup /data/backup.db"` (WAL-sicher), (2) `rsync -a` des Snapshots **und** von `data/images/` (bzw. `/data/images` im Volume) auf das Backup-Ziel `BACKUP_DEST`, (3) Aufräumen alter Snapshots gemäß Retention (Default 14 Tage). |
| **F-DEP-15** | **Atomarität/Konsistenz:** Der `.backup`-Befehl erzeugt einen in sich konsistenten DB-Snapshot trotz laufendem WAL-Writer (keine Cold-Copy der `.db`/`.db-wal`/`.db-shm` einzeln). Der Snapshot wird **vor** dem rsync erzeugt; rsync kopiert den **fertigen** Snapshot (nie die Live-DB direkt). |
| **F-DEP-16** | **Bilder im Backup:** `data/images/{user_id}/{plant_id}.png` ist Teil des Backups und nicht aus der DB rekonstruierbar — `rsync` der Bild-Hierarchie ist Pflicht, nicht optional. Backup ist nur „grün", wenn **beides** (DB-Snapshot + Bilder) am Ziel liegt. |
| **F-DEP-17** | **Restore-Drill dokumentiert:** README beschreibt den vollständigen Restore (Container stoppen → Snapshot als `/data/plantpal.db` einspielen → `data/images/` zurückspielen → Container starten → Migrationen laufen idempotent → `/api/health` prüfen). |
| **F-DEP-18** | **Backup-Verifikation:** Das Backup-Skript prüft nach `.backup`, dass der Snapshot via `sqlite3 backup.db "PRAGMA integrity_check;"` `ok` liefert, sonst Exit-Code ≠ 0 (für Cron-Monitoring/Logs sichtbar). |
| **F-DEP-19** | **Litestream:** Default **AUS** (`LITESTREAM_ENABLED=false`, war in M1-Config schon der Default-Wert). Der `litestream`-Service in Compose bleibt als **optionales** Profil (`profiles: ["backup"]`) erhalten, ist aber **nicht** der empfohlene Default-Weg mehr. README markiert Cron+rsync als Default, Litestream als „optional/fortgeschritten". |

### D.2.4 Monitoring & Logging

| Req | Beschreibung |
|---|---|
| **F-DEP-20** | **`structlog` real verdrahten:** Ein `logging_setup.py` (flaches Modul unter `src/plantpal/`) konfiguriert `structlog` (JSON-Renderer in Prod, Konsolen-Renderer in Dev) und wird im Lifespan **vor** allem anderen aufgerufen. Log-Level via ENV `LOG_LEVEL` (Default `INFO`). M1 listete structlog nur im Stack, ohne es zu initialisieren — v3 schließt diese Lücke. |
| **F-DEP-21** | **Strukturierte Logs an Schlüsselstellen:** App-Start/-Stop, jede Migration (`filename`), Reminder-Cron-Run (`due_users`, `sent`, `failed`, `skipped`, `target_date`), Mail-Send-Failure (`user_id`, `error`, `retry_count`), Image-Pipeline-Reject (`reason`, `status`), Auth-Verify-Failure-Code, Rate-Limit-Hit (`scope`). **Niemals** Klartext-Emails, Tokens oder `TOKEN_PEPPER`/`CSRF_SECRET` in Logs — Emails nur als `hash_ip`-äquivalenter Hash bzw. weggelassen, Tokens nie. |
| **F-DEP-22** | **`GET /api/health`** bleibt der externe Heartbeat-Endpoint (existiert aus M1, liefert `{status, db_ok, scheduler_running}`, kostet keine Auth). **UptimeRobot** pollt ihn alle 5 min (HTTP-Keyword-Monitor: Status 200 **und** Body enthält `"status":"ok"`). Bei `degraded`/Timeout/Non-200 → Alert (Mail an Betreiber). |
| **F-DEP-23** | **Health bleibt billig & unauthentifiziert:** keine teuren Queries, kein Rate-Limit-Verbrauch, kein Logging-Spam pro Poll (Health-Requests werden **nicht** auf `INFO` geloggt, höchstens auf `DEBUG`). Damit erzeugt UptimeRobots 5-min-Poll keine Log-Flut. |
| **F-DEP-24** | **Docker-`HEALTHCHECK`** im `Dockerfile` (existiert aus M1, curlt `/api/health`) bleibt unverändert und ist die **interne** Ebene; UptimeRobot ist die **externe** Ebene. `cloudflared` und `plantpal` laufen mit `restart: unless-stopped`, sodass der Pi nach Stromausfall/Reboot beide Container automatisch wieder hochfährt (App-Catch-up für verpasste Reminder greift aus M1). |

### D.2.5 DB-Housekeeping-Cron

| Req | Beschreibung |
|---|---|
| **F-DEP-25** | **Täglicher Housekeeping-Lauf** (Decision-Log §1 DB-Hygiene) löscht abgelaufene/verbrauchte Datensätze: `login_tokens` mit `expires_at < now` ODER `used_at` gesetzt; `invite_tokens` mit `expires_at < now` ODER `revoked_at` gesetzt ODER (`max_uses` erreicht); `sessions` mit `revoked_at` gesetzt ODER `hard_expires_at < now`; `reminder_send_log` älter als 90 Tage; `rate_limits` mit `expires_at < now()`. |
| **F-DEP-26** | **Ausführung:** als zusätzlicher **APScheduler-Job** im selben Single-Worker-Prozess (täglich, Berlin-TZ, z. B. 03:00) — analog zum Digest-Job in `main.py:_start_scheduler`. Kapselung in `reminder_service`-Nachbarschaft bzw. einem `housekeeping_service.py` (flaches Modul). **Alternativ** als CLI-Command `python -m plantpal.cli housekeeping` (per Host-Cron), falls Betreiber den Scheduler-Weg nicht will — README dokumentiert den Scheduler-Default. |
| **F-DEP-27** | **Sicher gegen Datenverlust:** Housekeeping löscht **nur** Auth-/Rate-/Log-Datensätze, **niemals** `users`, `plants`, `waterings` oder Bilder. Single-Writer-Serialisierung (M1 WAL + ein Writer) verhindert Konflikte mit Live-Traffic; Deletes laufen in kurzer Transaktion. |

---

## D.3 Konkrete Infra-Deltas

### D.3.1 `docker-compose.yml` (Ziel-Zustand v3)

**Entfernt:** kompletter `caddy`-Service, `ports: 80/443`, Volumes `caddy-data` + `caddy-config`, das `127.0.0.1:8000:8000`-Mapping am `plantpal`-Service (optional behalten nur für lokales Debug). **Hinzugefügt:** `cloudflared`-Service. **Behalten:** `plantpal`, `plantpal-data`-Volume, `litestream` (optionales Backup-Profil).

```yaml
services:
  plantpal:
    build: .
    restart: unless-stopped
    env_file: .env
    volumes:
      - plantpal-data:/data
    # KEIN ports: mehr nach außen. Erreichbar nur intern als plantpal:8000.
    # Optional für lokales Host-Debug (niemals 0.0.0.0):
    # ports:
    #   - "127.0.0.1:8000:8000"

  cloudflared:
    image: cloudflare/cloudflared:latest
    restart: unless-stopped
    command: tunnel run
    environment:
      - TUNNEL_TOKEN=${TUNNEL_TOKEN}
    depends_on:
      - plantpal
    # Routing (getplantpal.com -> http://plantpal:8000) im Cloudflare-Dashboard
    # als Public Hostname konfiguriert (Named Tunnel). Kein offener Host-Port.

  # Optional/fortgeschritten — NICHT der Default-Backup-Weg in v3.
  # Default-Backup ist scripts/backup.sh per Host-Cron (sqlite3 .backup + rsync).
  litestream:
    image: litestream/litestream:0.3
    restart: unless-stopped
    profiles: ["backup"]
    env_file: .env
    volumes:
      - plantpal-data:/data
      - ./litestream.yml:/etc/litestream.yml:ro
    command: replicate

volumes:
  plantpal-data:
  # caddy-data / caddy-config ENTFERNT
```

### D.3.2 `Dockerfile`

Keine strukturelle Änderung nötig — Single-Worker-`CMD`, `HEALTHCHECK` und Multi-Stage-Build bleiben aus M1. Klarstellung als Kommentar: Die App spricht weiter HTTP/`:8000`; TLS terminiert Cloudflare, nicht der Container.

### D.3.3 `Caddyfile`

**Datei wird gelöscht** (kein Reverse-Proxy mehr in der Infra). README-Verweise auf Caddy entfallen.

### D.3.4 `scripts/backup.sh` (neu)

```bash
#!/usr/bin/env sh
set -eu
# Tägliches Host-Backup: konsistenter SQLite-Snapshot + rsync von DB UND Bildern.
BACKUP_DEST="${BACKUP_DEST:?set BACKUP_DEST, e.g. /mnt/usb/plantpal-backups or user@nas:/vol/plantpal}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
STAMP="$(date +%F)"

# 1) WAL-sicherer Snapshot im Volume
docker compose exec -T plantpal sqlite3 /data/plantpal.db ".backup /data/backup.db"
# 2) Integritäts-Check (F-DEP-18)
docker compose exec -T plantpal sqlite3 /data/backup.db "PRAGMA integrity_check;" | grep -qx ok

# 3) Snapshot + Bilder aus dem Volume auf das Backup-Ziel (F-DEP-14/16)
VOL="$(docker volume inspect -f '{{ .Mountpoint }}' plantpal_plantpal-data)"
mkdir -p "${BACKUP_DEST}/${STAMP}"
rsync -a "${VOL}/backup.db"  "${BACKUP_DEST}/${STAMP}/plantpal.db"
rsync -a "${VOL}/images/"    "${BACKUP_DEST}/${STAMP}/images/"

# 4) Retention (F-DEP-14)
find "${BACKUP_DEST}" -maxdepth 1 -type d -mtime "+${RETENTION_DAYS}" -exec rm -rf {} +
```

Cron-Eintrag (Host, `crontab -e`):
```
30 3 * * *  BACKUP_DEST=/mnt/usb/plantpal-backups /opt/plantpal/scripts/backup.sh >> /var/log/plantpal-backup.log 2>&1
```

### D.3.5 `.env.example` — Deltas

```diff
- BASE_URL=https://plantpal.example.com
+ BASE_URL=https://getplantpal.com

- RESEND_FROM_EMAIL=PlantPal <noreply@plantpal.example.com>
+ # Absender MUSS auf der bei Resend verifizierten Domain liegen (SPF/DKIM/DMARC gesetzt).
+ RESEND_FROM_EMAIL=PlantPal <noreply@getplantpal.com>
+ # Resend Free = 100 Mails/TAG. Bei 100-1000 Usern ggf. Resend Pro (nur API-Key tauschen).

+ # --- Cloudflare Tunnel (Ingress; ersetzt Caddy + offene Ports 80/443) ---
+ TUNNEL_TOKEN=eyJ...   # Named-Tunnel-Token aus dem Cloudflare-Dashboard

+ # --- Monitoring / Logging ---
+ LOG_LEVEL=INFO
+ TRUST_CF_CONNECTING_IP=true   # echte Client-IP aus CF-Connecting-IP für Rate-Limits

+ # --- Backup (Cron-Default; Litestream optional/aus) ---
+ # BACKUP_DEST gehört in den Host-Cron, nicht in den Container.
- LITESTREAM_ENABLED=false
+ LITESTREAM_ENABLED=false   # bleibt aus; Default-Backup ist scripts/backup.sh
```

### D.3.6 `config.py` — Deltas

```python
    # Monitoring / Ingress (v3)
    LOG_LEVEL: str = "INFO"
    TRUST_CF_CONNECTING_IP: bool = True
```
`validate_runtime()` unverändert ausreichend: `BASE_URL=https://getplantpal.com` erfüllt die HTTPS-/Non-localhost-Checks; `secure_cookies` ⇒ `True`.

### D.3.7 `main.py` — Delta (echte Client-IP)

`_client_ip()` liest hinter dem Tunnel die Origin-IP aus `CF-Connecting-IP`:
```python
def _client_ip(request: Request) -> str:
    settings = request.app.state.settings
    ip = None
    if settings.TRUST_CF_CONNECTING_IP:
        ip = request.headers.get("cf-connecting-ip")
    ip = ip or (request.client.host if request.client else None)
    return hash_ip(ip)
```

### D.3.8 README-Deploy-Update (ersetzt M1-Abschnitt „Deployment")

Neuer Deploy-Ablauf (ersetzt Caddy/Ports-Voraussetzungen vollständig):

```bash
# 0) Domain getplantpal.com im Cloudflare-Registrar; Zone aktiv in Cloudflare.
# 1) Named Tunnel im Cloudflare-Dashboard anlegen, Public Hostname
#    getplantpal.com -> http://plantpal:8000, TLS-Mode "Full". Token kopieren.
cp .env.example .env            # BASE_URL=https://getplantpal.com, TUNNEL_TOKEN=..., Secrets
# 2) Resend: Domain getplantpal.com hinzufügen -> SPF/DKIM/DMARC-Records in
#    Cloudflare-DNS setzen -> in Resend "Verify" klicken. RESEND_FROM_EMAIL anpassen.
docker compose up -d --build    # plantpal + cloudflared (KEIN caddy, KEINE Ports 80/443)
docker compose exec plantpal python -m plantpal.cli bootstrap-admin --email du@getplantpal.com
# 3) UptimeRobot: HTTP-Keyword-Monitor auf https://getplantpal.com/api/health,
#    Keyword "status":"ok", Intervall 5 min.
# 4) Backup-Cron einrichten (scripts/backup.sh, BACKUP_DEST auf 2. Medium).
```
README-Voraussetzungen ändern sich: **statt** „offene Ports 80/443 + A/AAAA-Record" nun „Cloudflare-Account + Named-Tunnel-Token; **keine** Portfreigabe am Router nötig". Backup-Abschnitt: Cron+rsync als **Variante A (Default)**, Litestream als **Variante B (optional)** — die M1-Reihenfolge wird getauscht.

---

## D.4 Non-Functional Requirements

| Req | Beschreibung |
|---|---|
| **NFR-DEP-1** | **Keine offenen Inbound-Ports** am Heimanschluss/Host (Angriffsfläche minimiert; Tunnel ist Outbound-only). |
| **NFR-DEP-2** | **TLS** automatisch erneuert durch Cloudflare Universal SSL; kein Zertifikatsablauf-Risiko in der eigenen Infra. |
| **NFR-DEP-3** | **Mail-Zustellbarkeit:** SPF + DKIM aligned, DMARC vorhanden — Standard-Inbox-Platzierung bei Gmail/Outlook im Normalfall. |
| **NFR-DEP-4** | **Backup-Recovery-Ziel:** RPO ≤ 24 h (täglich), RTO ≤ 30 min (dokumentierter Restore-Drill). Backup umfasst zwingend DB **und** Bilder. |
| **NFR-DEP-5** | **Monitoring-Latenz:** Ausfall extern erkannt ≤ 5 min (UptimeRobot-Intervall). |
| **NFR-DEP-6** | **Logs:** strukturiert (JSON in Prod), PII-frei, Level per ENV; Health-Polls erzeugen keine Log-Flut. |
| **NFR-DEP-7** | **Reboot-Robustheit:** `restart: unless-stopped` für `plantpal` + `cloudflared`; nach Pi-Reboot kommt der Tunnel selbsttätig zurück, App-Catch-up sendet verpasste Reminder (M1). |
| **NFR-DEP-8** | **Secrets:** `TUNNEL_TOKEN`, `RESEND_API_KEY`, `TOKEN_PEPPER`, `CSRF_SECRET` nur in `.env` (gitignored), nie im Image/Repo; `.env.example` enthält nur Platzhalter. |

---

## D.5 Akzeptanzkriterien & Smoke-Tests

Manuelle Go-Live-Smoke-Tests sind als **Checkliste** ausgeführt (Infra ist nicht im pytest-Harness automatisierbar); App-seitige Deltas (IP-Header, Health-Body, Housekeeping) haben echte Tests.

| ID | Szenario | Verifikation |
|---|---|---|
| **AK-DEP-1** | **Public-Reachability:** `curl -sI https://getplantpal.com/api/health` → `200`, gültiges Cloudflare-Edge-Zertifikat (Kette valide, kein Ablauf), `cf-ray`-Header vorhanden. | Smoke (Shell) |
| **AK-DEP-2** | **Keine offenen Ports:** `nmap`/Port-Scan auf die öffentliche Heim-IP zeigt **80/443 geschlossen**; App ist nur über `getplantpal.com` (Cloudflare) erreichbar, nicht per Origin-IP direkt. | Smoke |
| **AK-DEP-3** | **Loopback-Origin:** Auf dem Host liefert `docker compose port plantpal 8000` **kein** öffentliches Mapping (bzw. nur `127.0.0.1`); `cloudflared`-Logs zeigen erfolgreiche Tunnel-Registrierung + Origin `http://plantpal:8000`. | Smoke |
| **AK-DEP-4** | **Echte Client-IP:** Request mit `CF-Connecting-IP: 9.9.9.9` an `/auth/request-login` → der Rate-Limit-Key basiert auf `hash_ip("9.9.9.9")`, nicht auf der Container-IP (4. Request derselben IP in 1 h → `429`). | `tests/test_proxy_ip.py` |
| **AK-DEP-5** | **Mail-Verifizierung:** Resend-Dashboard meldet `getplantpal.com` **verified**; ein über `cli issue-login-link --send` ausgelöster Magic-Link landet in der Gmail-**Inbox** (nicht Spam), `Authentication-Results` zeigt `spf=pass dkim=pass dmarc=pass`. | Smoke |
| **AK-DEP-6** | **Magic-Link-E2E über Tunnel:** Login-Mail klicken → `GET /auth/verify` redirectet zu `/`, Session-Cookie ist `Secure` gesetzt (über HTTPS-Edge). | Smoke |
| **AK-DEP-7** | **Backup erzeugt DB UND Bilder:** `scripts/backup.sh` läuft fehlerfrei, `PRAGMA integrity_check` = `ok`, im `BACKUP_DEST/<datum>/` liegen sowohl `plantpal.db` als auch ein nicht-leeres `images/`. | Smoke |
| **AK-DEP-8** | **Restore-Drill:** Frische DB + Bilder aus Backup in ein leeres Volume eingespielt → `docker compose up` → Migrationen idempotent angewandt → eine zuvor angelegte Pflanze inkl. 96×96-Bild ist via UI/`GET /api/plants/{id}/image` wieder sichtbar. | Smoke |
| **AK-DEP-9** | **UptimeRobot-Alert:** `plantpal`-Container gestoppt → UptimeRobot meldet „Down" ≤ 5 min, Recovery-Mail nach Neustart. | Smoke |
| **AK-DEP-10** | **Health-Body für Keyword-Monitor:** `GET /api/health` (gesund) → Body enthält `"status":"ok"`, `"db_ok":true`, `"scheduler_running":true`; DB künstlich gestört → `"status":"degraded"` + Non-„ok". | `tests/test_health.py` (erweitert) |
| **AK-DEP-11** | **Strukturierte Logs ohne PII:** Bei `LOG_LEVEL=INFO` enthalten App-Start-, Migration- und Reminder-Run-Logs JSON-Felder; ein Grep über die Logausgabe findet **keine** Klartext-Email-Adresse und **keinen** Token/`PEPPER`. | `tests/test_logging_setup.py` |
| **AK-DEP-12** | **Housekeeping löscht nur Müll:** Nach Einfügen abgelaufener `login_tokens`/`invite_tokens`/revoked `sessions`/alter `reminder_send_log`/abgelaufener `rate_limits` löscht der Housekeeping-Lauf genau diese, während `users`, `plants`, `waterings` und Bilder unangetastet bleiben. | `tests/test_housekeeping.py` |
| **AK-DEP-13** | **Reboot-Resilienz:** `docker compose restart` (bzw. simulierter Host-Reboot) bringt `plantpal` + `cloudflared` automatisch zurück (`restart: unless-stopped`); `https://getplantpal.com/api/health` wieder `200` ohne manuelles Eingreifen; ein im Reboot-Fenster fälliger Reminder wird durch Catch-up genau einmal nachgeholt. | Smoke + `tests/test_reminder_cron.py::test_catchup` (M1, weiter grün) |
| **AK-DEP-14** | **Caddy-frei:** `docker compose config` enthält **keinen** `caddy`-Service und **keine** `80:80`/`443:443`-Mappings mehr; `Caddyfile` existiert nicht mehr im Repo. | Smoke + Repo-Check |

---

## D.6 Out-of-Scope (v3 Deployment)

- Aktives Cloudflare WAF/Rate-Limiting-Regelwerk (App-eigenes SQLite-Rate-Limit aus M1 bleibt die Schutzschicht; Cloudflare-Edge-Schutz optional später).
- Cloudflare Zero-Trust-Access vor der App (PlantPal hat eigene Auth).
- Mehrere Hosts / Failover / HA (Single-Box, SQLite-Constraint).
- Metrics-Stack (Prometheus/Grafana) — `structlog` + UptimeRobot genügen für die Community-Größe.
- Litestream als Default (bewusst durch Cron+rsync ersetzt; bleibt nur optionales Profil).
- Automatisierte E2E-Infra-Tests gegen die Live-Cloudflare-Edge (Smoke-Checkliste statt CI).

---

## D.7 Failure-Mode-Ergänzungen (Deployment v3)

| # | Failure | Mitigation in v3 |
|---|---|---|
| 1 | **Heim-IP wechselt / kein Portforwarding möglich** | Cloudflare Tunnel ist Outbound-only — DDNS/Portforwarding entfällt komplett (F-DEP-1/2). |
| 2 | **`cloudflared` verliert Verbindung** | `restart: unless-stopped` + Cloudflares Reconnect; UptimeRobot meldet Außenausfall (F-DEP-22). |
| 3 | **Mails landen im Spam** | SPF/DKIM/DMARC auf eigener Domain (F-DEP-10); CLI-Fallback `issue-login-link` druckt Link unabhängig vom Versand (M1). |
| 4 | **Resend-Tageslimit (100) gerissen** | Dokumentiert (F-DEP-13); Reminder-Sends idempotent + Retry (M1); Upgrade auf Pro ohne Code-Change. |
| 5 | **SD-Karte/Disk stirbt** | Tägliches Cron-Backup von DB **und** Bildern auf zweitem Medium + Integrity-Check + Restore-Drill (F-DEP-14..18). |
| 6 | **Rate-Limit greift nicht hinter Tunnel** | Echte Client-IP via `CF-Connecting-IP` (F-DEP-7, AK-DEP-4). |
| 7 | **Pi-Stromausfall / Reboot** | `restart: unless-stopped` für App + Tunnel; Reminder-Catch-up (M1); Außen-Monitoring bestätigt Recovery (NFR-DEP-7, AK-DEP-13). |
| 8 | **Token/Secret-Leak via Logs** | `structlog`-Pipeline filtert PII/Secrets; Tests greppen dagegen (F-DEP-21, AK-DEP-11). |
| 9 | **Tabellen-Wildwuchs (Tokens/Sessions/Logs)** | Täglicher Housekeeping-Job löscht abgelaufenen Auth-/Rate-/Log-Müll, niemals Nutzdaten (F-DEP-25..27). |



# Teil 7 — Recht & DSGVO v3

## 6. Recht & DSGVO (v3)

**Status:** v3 — erweitert M1. Quelle: Decision-Log PlantPal v3 (Grill 2026-06-03), Abschnitt 6 + 2 (Email ändern).
**Geltung:** Zielgruppe ist eine kleine *öffentliche* Community (100–1000 User) auf `getplantpal.com`, betrieben aus Deutschland (Pi/Mini-PC zuhause + Cloudflare Tunnel). Damit greifen DDG (ex-TMG, Impressumspflicht) und DSGVO (Informationspflichten Art. 13, Betroffenenrechte Art. 15/17/20).

> **Kein-Anwalt-Hinweis (binding, steht so auch auf den Seiten):** Die in diesem Baustein gelieferten Vorlagentexte für Impressum und Datenschutzerklärung sind eine technische Arbeitsgrundlage, **keine Rechtsberatung**. Vor dem Public-Launch lässt der Betreiber (Marius Schwarzin) beide Texte final prüfen (z. B. anwaltliche Prüfung oder ein anerkannter Generator wie e-recht24/Dr. Schwenke) und füllt die mit `{{…}}`-Platzhaltern markierten Pflichtfelder mit echten Daten. Die Platzhalter sind die **einzig** erlaubten „Lücken" und müssen vor Launch ersetzt sein (F-LEGAL-9 erzwingt das in Prod).

### 6.0 Begründung: KEIN Cookie-Banner

PlantPal setzt **ausschließlich technisch notwendige Cookies** und keinerlei Tracking/Marketing/Analytics. Konkret existieren genau zwei First-Party-Cookies (beide bereits aus M1, siehe `main.py::_set_auth_cookies`):

| Cookie | Zweck | Flags | Lebensdauer |
|---|---|---|---|
| `plantpal_session` | Session-/Login-Zustand (Opaque-Token → DB-Lookup) | HttpOnly, Secure, SameSite=Lax, Path=/ | bis `SESSION_SOFT_CAP_DAYS` (90 d), sliding |
| `plantpal_csrf` | CSRF-Schutz (signed double-submit, an Session gebunden) | Secure, SameSite=Lax, Path=/ (nicht HttpOnly — Frontend liest) | analog Session |

Beide sind für den vom User **ausdrücklich angeforderten Dienst** (eingeloggte App-Nutzung, sichere Formular-Submits) **unbedingt erforderlich**. Nach § 25 Abs. 2 Nr. 2 TDDDG (Umsetzung der ePrivacy-Richtlinie) ist für „unbedingt erforderliche" Cookies **keine Einwilligung** nötig → **kein Cookie-Banner**. Es werden außerdem keine Drittanbieter-Skripte, keine externen Fonts-CDNs zur Laufzeit (Pixel-Font wird selbst gehostet, vgl. UI-Baustein), kein `localStorage`-Tracking und kein Fingerprinting eingesetzt. Persistierte UI-Präferenzen (Theme/Locale) liegen serverseitig in `users` (M3-Spalten `theme`/`locale`) bzw. — falls nicht eingeloggt — in `localStorage` als reine Funktions-/Komfort-Speicherung ohne Personenbezug; auch das ist einwilligungsfrei. **Diese Begründung steht wörtlich in der Datenschutzerklärung** (§ „Cookies & lokale Speicherung").

### 6.1 Functional Requirements

| Req | Beschreibung |
|---|---|
| **F-LEGAL-1** | **Statische Legal-Seiten als SPA-Routes.** Zwei neue Client-Routen `GET /legal/imprint` (Impressum) und `GET /legal/privacy` (Datenschutz) werden vom React-Router gerendert; das Backend liefert sie über den bestehenden SPA-Fallback (`spa.py::mount_spa`, History-API-Fallback auf `index.html`) — **kein** neuer Server-Endpoint nötig. Inhalte liegen als lokalisierte Markdown/TSX-Bausteine im Frontend (`frontend/src/pages/legal/`), DE + EN (i18n, vgl. Frontend-Baustein). Seiten sind **ohne Login** erreichbar (keine `current_user`-Dependency, da SPA-Route). |
| **F-LEGAL-2** | **Footer-Links global.** Ein persistenter App-Footer (in `App.tsx`-Layout, auf jeder Seite inkl. Login/Register sichtbar) enthält genau drei Links: „Impressum / Imprint" → `/legal/imprint`, „Datenschutz / Privacy" → `/legal/privacy", und einen `mailto:`-Link auf die Betreiber-Kontaktadresse. Links sind tastatur-fokussierbar und erfüllen die Touch-Target-/Fokus-Vorgaben des UI-Bausteins. |
| **F-LEGAL-3** | **Impressum (DDG/§ 5 DDG).** Die Impressums-Seite enthält die Pflichtangaben für einen geschäftsmäßig betriebenen, in der Regel gegen Entgelt angebotenen Telemediendienst bzw. — bei rein privatem Hobby-Betrieb — die freiwillig empfohlenen Anbieterangaben: Name & Anschrift des Diensteanbieters, Kontakt (E-Mail; Telefon optional), bei journalistisch-redaktionellen Inhalten ein inhaltlich Verantwortlicher (§ 18 Abs. 2 MStV). Vorlagentext in §6.3, Platzhalter `{{…}}`. |
| **F-LEGAL-4** | **Datenschutzerklärung (DSGVO Art. 13).** Die Privacy-Seite informiert vollständig nach Art. 13: Verantwortlicher + Kontakt; Zwecke & Rechtsgrundlagen jeder Verarbeitung (Account/Auth → Art. 6 (1) b Vertrag; Reminder-Mails → Art. 6 (1) b bzw. f; Sicherheits-Logs/Rate-Limits → Art. 6 (1) f berechtigtes Interesse); Empfänger/Auftragsverarbeiter (**Resend** für E-Mail-Versand, **Cloudflare** als Tunnel/Reverse-Proxy/DNS/Registrar); Drittlandübermittlung (USA) inkl. Grundlage (EU-US Data Privacy Framework und/oder Standardvertragsklauseln); Speicherdauer je Datenart (siehe Housekeeping-Cron Decision-Log §1); Betroffenenrechte (Auskunft, Berichtigung, Löschung, Einschränkung, Datenübertragbarkeit, Widerspruch, Widerruf, Beschwerde bei einer Aufsichtsbehörde); Hinweis, dass keine automatisierte Entscheidung/Profiling stattfindet. Vorlagentext in §6.4. |
| **F-LEGAL-5** | **Resend als Auftragsverarbeiter (Art. 28).** Die Datenschutzerklärung benennt Resend ausdrücklich als Auftragsverarbeiter für den Versand von Magic-Link-, Login-Code-, E-Mail-Änderungs- und Reminder-Mails, nennt die übermittelten Datenarten (E-Mail-Adresse des Empfängers, Mail-Inhalt inkl. kurzlebiger Login-Token/Code, Sende-Metadaten) und weist darauf hin, dass der Betreiber vor Produktivbetrieb einen **Auftragsverarbeitungsvertrag (AVV / DPA)** mit Resend abschließt. Der Betrieb ist **provider-agnostisch** (Decision-Log §1): Der Vorlagentext kapselt den Provider-Namen in einem `{{MAIL_PROVIDER}}`-Platzhalter mit Default „Resend, Inc.", damit ein späterer Provider-Wechsel nur eine Textstelle berührt. |
| **F-LEGAL-6** | **Daten-Export (Self-Service, Art. 15 + 20).** Neuer Endpoint `GET /api/account/export` (Auth, **kein** CSRF da idempotenter GET) erzeugt **on-the-fly** ein ZIP-Archiv mit (a) `plantpal-export.json` (alle personenbezogenen Daten des Users in maschinenlesbarem, strukturiertem Format — siehe F-LEGAL-7) und (b) allen Pflanzenbildern unter `images/{plant_id}.png`. Response: `200`, `Content-Type: application/zip`, `Content-Disposition: attachment; filename="plantpal-export-{YYYY-MM-DD}.zip"` (Datum via `now_berlin()`). ZIP wird in-memory (`io.BytesIO` + `zipfile`) gebaut, nichts persistiert. Rate-Limit `RL_EXPORT = "3/h"` pro User (neuer Config-Wert), um DoS/Disk-IO-Spam zu verhindern. |
| **F-LEGAL-7** | **Export-Format & -Umfang.** `plantpal-export.json` ist UTF-8, `ensure_ascii=False`, `indent=2`, mit `schema_version: 1` und `exported_at` (Berlin-ISO). Enthält:<br>• `account`: `email`, `is_admin`, `created_at`, `last_login_at`, `email_reminders_enabled`, `reminder_channel`, `reminder_hour`, `locale`, `theme`.<br>• `plants[]`: **alle** Pflanzen inkl. soft-deleted (`is_active`), je mit `id, name, interval_days, notes, water_amount_ml, last_watered_at, created_at, is_active, location_room, image_file` (Dateiname im ZIP oder `null`).<br>• `waterings[]` (sobald Historie-Tabelle aus v3-Schema existiert): `plant_id, watered_at` chronologisch.<br>• `invites_created[]`: vom User erzeugte Invites (`created_at, expires_at, max_uses, used_count`; **ohne** Klartext-Token — es liegt nur als Hash vor).<br>Alle Felder sind 1:1 die in der DB gespeicherten Werte; es werden **keine** fremden personenbezogenen Daten ausgegeben (z. B. nicht die E-Mail-Adressen eingeladener Personen). |
| **F-LEGAL-8** | **Account-Löschen (Art. 17) — Bestand + UX-Härtung.** Der bestehende Endpoint `DELETE /api/account` (M1, `main.py`, Auth + CSRF: Hard-Delete aller User-Daten via `plant_service.delete_account` + `image_service.delete_user_images`, sofortiger Logout) bleibt der maßgebliche „Recht auf Löschung"-Mechanismus. v3 ändert **nur** die UX: kein `window.confirm`, sondern ein expliziter App-Confirm-Dialog, in dem der User zur Bestätigung seine **E-Mail-Adresse abtippen** muss; erst dann wird der Button aktiv (vgl. Frontend-Baustein „Lösch-UX"). Serverseitig unverändert. Die Datenschutzerklärung beschreibt diesen Weg unter „Recht auf Löschung". |
| **F-LEGAL-9** | **Placeholder-Guard in Production.** `Settings.validate_runtime()` (in `config.py`, läuft beim Lifespan-Start wenn `APP_ENV=production`) wird erweitert: Sind die neuen Pflicht-Settings `LEGAL_OPERATOR_NAME` oder `LEGAL_CONTACT_EMAIL` leer **oder** enthalten noch eine `{{…}}`-Sequenz, schlägt der Start mit `ValueError("Legal imprint fields must be filled before production launch")` fehl. Das verhindert einen Public-Launch mit unausgefülltem Impressum. In `APP_ENV in {dev,test}` ist der Platzhalter erlaubt. |
| **F-LEGAL-10** | **Versionierung & „Stand"-Datum.** Beide Seiten zeigen unten ein „Stand: {{LEGAL_LAST_UPDATED}}"-Datum (Config-Wert, ISO `YYYY-MM-DD`). Bei inhaltlicher Änderung der Texte wird dieses Datum vom Betreiber hochgesetzt; eine Einwilligung/Re-Consent ist nicht erforderlich, da keine einwilligungsbasierte Verarbeitung stattfindet. |
| **F-LEGAL-11** | **Health/Reachability ohne Auth.** Die Legal-Seiten und der Footer dürfen **keine** authentifizierten API-Calls auslösen (sonst wären sie für Logged-out-Besucher kaputt). Die Seiten sind rein statisch gerendert; einziger erlaubter dynamischer Wert sind die aus dem Build eingebetteten Config-Platzhalter (zur Build-/Render-Zeit über `import.meta.env.VITE_LEGAL_*` injiziert, gespiegelt aus den Backend-Settings, siehe §6.5). |

### 6.2 Schema-/Endpoint-/Config-Deltas

**Schema:** **Keine** neue Migration für diesen Baustein nötig. Account-Löschen, Soft-Delete-Spalten und die für den Export gelesenen Spalten existieren bereits (M1) bzw. werden vom v3-Schema-Baustein (Migration `002`: `plants.location_room`, `waterings`, `users.reminder_hour/locale/theme`, `invite_tokens.max_uses/used_count`) bereitgestellt. Der Export liest diese Spalten nur lesend; er bringt selbst kein DDL mit.

**Neuer Endpoint (Ergänzung zur M1-Endpoint-Tabelle):**

| Endpoint | Method | Auth | CSRF | Rate-Limit | Errors |
|---|---|---|---|---|---|
| `/api/account/export` | GET | ✅ | – (idempotenter GET) | `3/user/hour` | `401`, `429`, `507 export_write_failed` (in-memory OOM/Disk → graceful 507 + Log) |

`DELETE /api/account` (M1) bleibt unverändert in Signatur und Verhalten; nur Frontend-UX ändert sich (F-LEGAL-8).

**Config-Deltas (`config.py`, additiv, mit ENV-Override):**

```python
    # Legal / Impressum (DDG) + Datenschutz (DSGVO) — Platzhalter in dev/test erlaubt,
    # in production via validate_runtime() erzwungen (F-LEGAL-9).
    LEGAL_OPERATOR_NAME: str = "{{NAME}}"            # Vor- und Nachname / Firma
    LEGAL_OPERATOR_ADDRESS: str = "{{STRASSE, PLZ ORT, LAND}}"
    LEGAL_CONTACT_EMAIL: str = "{{kontakt@getplantpal.com}}"
    LEGAL_CONTACT_PHONE: str = ""                    # optional
    LEGAL_RESPONSIBLE_PERSON: str = ""               # § 18 (2) MStV, optional
    LEGAL_LAST_UPDATED: str = "2026-06-03"           # "Stand"-Datum (F-LEGAL-10)
    MAIL_PROVIDER: str = "Resend, Inc."              # provider-agnostisch (F-LEGAL-5)

    # Export
    RL_EXPORT: str = "3/h"                           # pro User (F-LEGAL-6)
```

Ergänzung in `validate_runtime()` (innerhalb des `if self.is_production:`-Blocks):

```python
            for name, value in (
                ("LEGAL_OPERATOR_NAME", self.LEGAL_OPERATOR_NAME),
                ("LEGAL_OPERATOR_ADDRESS", self.LEGAL_OPERATOR_ADDRESS),
                ("LEGAL_CONTACT_EMAIL", self.LEGAL_CONTACT_EMAIL),
            ):
                if not value or "{{" in value:
                    raise ValueError(
                        "Legal imprint fields must be filled before production launch "
                        f"({name} still empty or contains a placeholder)"
                    )
```

**Frontend-Config-Spiegelung:** Die anzuzeigenden Legal-Stammdaten werden als `VITE_LEGAL_OPERATOR_NAME`, `VITE_LEGAL_OPERATOR_ADDRESS`, `VITE_LEGAL_CONTACT_EMAIL`, `VITE_LEGAL_CONTACT_PHONE`, `VITE_LEGAL_RESPONSIBLE_PERSON`, `VITE_LEGAL_LAST_UPDATED`, `VITE_MAIL_PROVIDER` zur Build-Zeit gesetzt (Spiegel der Backend-Werte, in `docker-compose.yml`/`.env` gepflegt). So bleibt es ein statischer Build ohne Laufzeit-API (F-LEGAL-11). Die `mailto:`-Adresse im Footer nutzt `VITE_LEGAL_CONTACT_EMAIL`.

### 6.3 Vorlagentext — Impressum (DE)

> Wird auf `/legal/imprint` gerendert; EN-Spiegelung „Imprint / Legal Notice" analog. `{{…}}` = vor Launch ersetzen.

```markdown
# Impressum

Angaben gemäß § 5 DDG (Digitale-Dienste-Gesetz)

{{NAME}}
{{STRASSE}}
{{PLZ ORT}}
{{LAND}}

## Kontakt
E-Mail: {{kontakt@getplantpal.com}}
Telefon: {{optional — sonst Zeile entfernen}}

## Verantwortlich für den Inhalt nach § 18 Abs. 2 MStV
{{NAME, Anschrift wie oben — nur falls journalistisch-redaktionelle Inhalte}}

## Haftung für Inhalte
Als Diensteanbieter sind wir gemäß § 7 Abs. 1 DDG für eigene Inhalte auf diesen
Seiten nach den allgemeinen Gesetzen verantwortlich. Nach §§ 8 bis 10 DDG sind wir
als Diensteanbieter jedoch nicht verpflichtet, übermittelte oder gespeicherte fremde
Informationen zu überwachen oder nach Umständen zu forschen, die auf eine
rechtswidrige Tätigkeit hinweisen.

## Haftung für Links
Unser Angebot enthält ggf. Links zu externen Websites Dritter, auf deren Inhalte wir
keinen Einfluss haben. Deshalb können wir für diese fremden Inhalte auch keine Gewähr
übernehmen. Für die Inhalte der verlinkten Seiten ist stets der jeweilige Anbieter
oder Betreiber der Seiten verantwortlich.

## Hinweis zur EU-Streitschlichtung
Plattform der EU-Kommission zur Online-Streitbeilegung (OS):
https://ec.europa.eu/consumers/odr/. Wir sind nicht verpflichtet und nicht bereit,
an Streitbeilegungsverfahren vor einer Verbraucherschlichtungsstelle teilzunehmen.

Stand: {{LEGAL_LAST_UPDATED}}

> Hinweis: Dieser Text ist eine technische Vorlage und keine Rechtsberatung. Bitte vor
> der Veröffentlichung anwaltlich oder über einen anerkannten Impressums-Generator prüfen
> und alle {{…}}-Felder ausfüllen.
```

### 6.4 Vorlagentext — Datenschutzerklärung (DE, gekürzt-vollständig)

> Wird auf `/legal/privacy` gerendert; EN-Spiegelung „Privacy Policy" analog. Speicherdauern spiegeln den Housekeeping-Cron (Decision-Log §1).

```markdown
# Datenschutzerklärung

Stand: {{LEGAL_LAST_UPDATED}}

## 1. Verantwortlicher
Verantwortlicher im Sinne der DSGVO ist:
{{NAME}}, {{STRASSE, PLZ ORT, LAND}} — E-Mail: {{kontakt@getplantpal.com}}.

## 2. Überblick
PlantPal ist ein selbst-gehosteter Gieß-Erinnerungs-Dienst. Wir verarbeiten nur die
Daten, die für Betrieb, Login und Erinnerungs-E-Mails erforderlich sind. Wir verwenden
keine Tracking-, Analyse- oder Werbe-Tools und betreiben kein Profiling.

## 3. Verarbeitete Daten, Zwecke und Rechtsgrundlagen
- **Account & Login:** E-Mail-Adresse, Login-Zeitpunkte, Session-Daten. Zweck: Bereit-
  stellung des Nutzerkontos und Anmeldung per Magic-Link bzw. 6-stelligem Code.
  Rechtsgrundlage: Art. 6 Abs. 1 lit. b DSGVO (Vertrag/Nutzungsverhältnis).
- **Pflanzendaten & Bilder:** Von dir eingegebene Pflanzennamen, Intervalle, Notizen,
  Standort, Gieß-Historie und hochgeladene Fotos (auf 96×96 px verkleinert, EXIF-Daten
  inkl. evtl. GPS werden beim Upload entfernt). Zweck: Kernfunktion der App.
  Rechtsgrundlage: Art. 6 Abs. 1 lit. b DSGVO.
- **Erinnerungs-E-Mails:** Versand eines täglichen Digests durstiger Pflanzen, sofern
  aktiviert. Rechtsgrundlage: Art. 6 Abs. 1 lit. b DSGVO; in Settings jederzeit
  abschaltbar (Widerspruch nach Art. 21 DSGVO durch Deaktivieren).
- **Sicherheit & Missbrauchsabwehr:** kurzlebige Server-Logs, gehashte IP-Adressen und
  Zähler zur Ratenbegrenzung. Rechtsgrundlage: Art. 6 Abs. 1 lit. f DSGVO (berechtigtes
  Interesse an einem sicheren, missbrauchsfreien Betrieb).
- **Einladungen:** Wenn du andere einlädst, erzeugen wir einen Einladungs-Link; eine
  optional eingegebene „E-Mail-Hint" wird gespeichert. Rechtsgrundlage: Art. 6 Abs. 1
  lit. f DSGVO.

## 4. Empfänger / Auftragsverarbeiter
- **E-Mail-Versand:** {{MAIL_PROVIDER}} (Resend) verschickt in unserem Auftrag Magic-Link-,
  Code-, E-Mail-Änderungs- und Erinnerungs-Mails. Übermittelt werden Empfänger-Adresse,
  Mail-Inhalt (inkl. kurzlebigem Login-Token/-Code) und Sende-Metadaten. Es besteht ein
  Auftragsverarbeitungsvertrag (Art. 28 DSGVO). Login-Token sind einmalig nutzbar und
  laufen nach kurzer Zeit ab.
- **Hosting/Zustellung:** Cloudflare, Inc. stellt DNS, Registrar und einen verschlüsselten
  Tunnel/Reverse-Proxy bereit (TLS-Terminierung). Cloudflare verarbeitet dabei Verbindungs-
  und Inhaltsdaten in unserem Auftrag (Art. 28 DSGVO). Die App selbst läuft auf einem
  Server im privaten Umfeld des Verantwortlichen in Deutschland.

## 5. Drittlandübermittlung
Resend und Cloudflare können Daten in den USA verarbeiten. Grundlage der Übermittlung sind
das EU-US Data Privacy Framework (soweit zertifiziert) und/oder die Standardvertragsklauseln
der EU-Kommission gem. Art. 46 DSGVO.

## 6. Speicherdauer
- Account-, Pflanzen- und Gieß-Daten: bis zur Löschung deines Accounts.
- Login-Token/-Codes: bis Nutzung, längstens ~30 Minuten; ein täglicher Aufräum-Job
  entfernt abgelaufene Token.
- Sessions: bis Logout bzw. Ablauf (max. 180 Tage); abgelaufene/widerrufene Sessions
  werden täglich aufgeräumt.
- Einladungs-Links: bis Ablauf/Aufbrauch, danach Aufräumung.
- Versand-Protokolle der Reminder: kurzzeitig zur Idempotenz, danach Aufräumung.

## 7. Cookies & lokale Speicherung
Wir setzen ausschließlich technisch notwendige Cookies: `plantpal_session` (Login-Zustand)
und `plantpal_csrf` (Schutz vor Cross-Site-Request-Forgery). Beide sind für den von dir
angeforderten Dienst unbedingt erforderlich; daher ist nach § 25 Abs. 2 Nr. 2 TDDDG keine
Einwilligung nötig und es wird kein Cookie-Banner angezeigt. Optionale Oberflächen-
Einstellungen (Sprache, Hell-/Dunkel-Modus) speichern wir serverseitig in deinem Konto bzw.
— ohne Login — lokal in deinem Browser; auch dies dient allein der Funktion. Es findet kein
Tracking und kein Einsatz von Drittanbieter-Skripten statt.

## 8. Deine Rechte
Du hast das Recht auf Auskunft (Art. 15), Berichtigung (Art. 16), Löschung (Art. 17),
Einschränkung der Verarbeitung (Art. 18), Datenübertragbarkeit (Art. 20) sowie Widerspruch
(Art. 21). Du kannst eine Einwilligung jederzeit mit Wirkung für die Zukunft widerrufen.
- **Auskunft & Datenübertragbarkeit:** In den Einstellungen kannst du jederzeit über
  „Daten exportieren" ein vollständiges, maschinenlesbares Archiv (JSON + Bilder, ZIP)
  herunterladen.
- **Berichtigung:** Pflanzendaten sind direkt editierbar; deine E-Mail-Adresse änderst du
  über „E-Mail ändern" (Bestätigung per Mail an die neue Adresse).
- **Löschung:** Über „Account löschen" werden Konto, Pflanzen, Gieß-Historie, Bilder,
  Sessions und Token unwiderruflich und vollständig entfernt.

## 9. Beschwerderecht
Du hast das Recht, dich bei einer Datenschutz-Aufsichtsbehörde zu beschweren, insbesondere
in dem Mitgliedstaat deines Aufenthaltsorts oder des mutmaßlichen Verstoßes. Zuständig für
den Verantwortlichen ist die Aufsichtsbehörde am Sitz des Verantwortlichen.

## 10. Keine automatisierte Entscheidungsfindung
Es findet keine automatisierte Entscheidungsfindung einschließlich Profiling im Sinne des
Art. 22 DSGVO statt.

> Hinweis: Dieser Text ist eine technische Vorlage und keine Rechtsberatung. Bitte vor der
> Veröffentlichung final prüfen lassen und alle {{…}}-Felder ausfüllen.
```

### 6.5 Akzeptanzkriterien (v3 — Recht & DSGVO)

Jede Akzeptanz hat eine Test-ID; Backend-/Integration-Tests laufen mit pytest + httpx (ASGI), Frontend mit Vitest/Playwright. Konvention wie M1 §11.

| ID | Szenario | Test-Datei |
|---|---|---|
| **AK-L1** | **Legal-Seiten ohne Login erreichbar:** `GET /legal/imprint` und `GET /legal/privacy` liefern via SPA-Fallback `index.html` (200), ohne dass ein Session-Cookie gesetzt sein muss. | `tests/test_spa_legal.py::test_legal_routes_public` |
| **AK-L2** | **Footer-Links überall:** Auf Login-, Plantdex- und Settings-Seite ist je ein Link zu Impressum, Datenschutz und ein `mailto:` vorhanden und fokussierbar. | `frontend/src/__tests__/footer.test.tsx` |
| **AK-L3** | **Kein Cookie-Banner / nur notwendige Cookies:** Nach `POST /auth/request-login` + `GET /auth/verify` setzt die App genau `plantpal_session` + `plantpal_csrf` und **kein** Consent-/Tracking-Cookie; im DOM existiert kein Cookie-Banner-Element. | `tests/test_auth_service.py::test_only_technical_cookies` + `frontend/src/__tests__/no_cookie_banner.test.tsx` |
| **AK-L4** | **Datenschutz nennt Resend als AVV + Drittland:** Die gerenderte Privacy-Seite enthält die Strings „Auftragsverarbeitung", „{{MAIL_PROVIDER}}"-Auflösung (Default „Resend") und „Standardvertragsklauseln". | `frontend/src/__tests__/privacy_content.test.tsx` |
| **AK-L5** | **Export ZIP-Struktur:** `GET /api/account/export` liefert 200 + `application/zip`; das ZIP enthält `plantpal-export.json` und für jede Pflanze mit Bild ein `images/{id}.png`. | `tests/test_account_export.py::test_export_zip_structure` |
| **AK-L6** | **Export-Inhalt vollständig & isoliert:** Das JSON enthält Account-Felder + alle Pflanzen (inkl. soft-deleted) + Gieß-Historie des Users; es enthält **keine** Daten anderer User (User B's Pflanze taucht in User A's Export nicht auf) und **keinen** Klartext-Token. | `tests/test_account_export.py::test_export_user_scope_and_no_secrets` |
| **AK-L7** | **Export-Rate-Limit:** 4. Export-Request desselben Users binnen einer Stunde → 429 + `Retry-After`. | `tests/test_account_export.py::test_export_rate_limit` |
| **AK-L8** | **Export-Auth:** `GET /api/account/export` ohne gültige Session → 401. | `tests/test_account_export.py::test_export_requires_auth` |
| **AK-L9** | **Account-Löschen-UX (Confirm by typing email):** Der Delete-Button ist deaktiviert, bis im Dialog die exakte (case-insensitive) Account-E-Mail eingegeben wurde; danach `DELETE /api/account` → Konto, Pflanzen, Bilder, Sessions weg + sofortiger Logout (`/api/me` → 401). | `frontend/src/__tests__/delete_account_dialog.test.tsx` + `tests/test_account_delete.py::test_hard_delete` |
| **AK-L10** | **Placeholder-Guard:** Mit `APP_ENV=production` und unausgefülltem `LEGAL_OPERATOR_NAME` (enthält `{{`) wirft `validate_runtime()` `ValueError`; mit ausgefüllten Werten startet die App. | `tests/test_config.py::test_legal_placeholder_guard` |
| **AK-L11** | **„Stand"-Datum sichtbar:** Beide Legal-Seiten rendern „Stand: " + `VITE_LEGAL_LAST_UPDATED`. | `frontend/src/__tests__/legal_last_updated.test.tsx` |
| **AK-L12** | **i18n der Legal-Seiten:** Bei `locale=en` rendern die Seiten „Imprint" bzw. „Privacy Policy"; bei `locale=de` „Impressum" bzw. „Datenschutzerklärung". | `frontend/src/__tests__/legal_i18n.test.tsx` |

### 6.6 Out-of-Scope (Recht & DSGVO v3)

- Verzeichnis von Verarbeitungstätigkeiten (Art. 30) und der eigentliche AVV-Vertragsabschluss mit Resend/Cloudflare sind **organisatorische** Aufgaben des Betreibers, nicht Teil des Codes.
- Kein Consent-Management / TCF, da keine einwilligungspflichtige Verarbeitung.
- Kein automatischer E-Mail-Versand des Export-Archivs (nur Self-Service-Download); kein zeitversetztes „Recht-auf-Vergessen"-Grace-Window (Löschung ist sofort und hart, wie M1).
- Keine PDF-Generierung der Legal-Seiten (HTML/SPA genügt; Browser-Druck reicht).

---

*Dieser Baustein erweitert PlantPal v3 (Recht & DSGVO). Maßgebliche Primärquellen: `docs/PRD_M1.md` (§5 NFR-2/NFR-10, §4.7 F-SET-5), `src/plantpal/main.py` (`DELETE /api/account`, `_set_auth_cookies`, SPA-Mount), `src/plantpal/config.py` (`validate_runtime`), `migrations/001_initial.sql`, `src/plantpal/spa.py`, `README.md` (Datenschutz-Abschnitt). Kein-Anwalt-Hinweis gilt; finale Prüfung beim Betreiber.*


---

# Teil 8 — Konsolidierungs-Beschlüsse (nach Codex-Plan-Review, 2026-06-03)

Die parallel erzeugten Bausteine hatten Widersprüche; Codex (gpt-5.5, read-only) fand sie als Plan-Review (2 BLOCKER, 5 HIGH, 3 MEDIUM, 1 LOW). Folgende Beschlüsse sind **bei Widersprüchen verbindlich** und gelten für die Umsetzung:

| # | Konflikt | Beschluss |
|---|---|---|
| **K1** (BLOCKER) | `code` vs `code_hash`, fehlendes `attempt_count` | Spalte heißt überall **`code_hash`** (HMAC, konsistent mit `token_hash`). `email_change_requests` bekommt **`code_hash NOT NULL` + `attempt_count INTEGER NOT NULL DEFAULT 0`**. |
| **K2** (BLOCKER) | Invite-Quota-Semantik | Verbrauch = **`SUM(max_uses)` offener (nicht revoked, nicht expired) Invites**; **kein** `invite_quota`-Dekrement-Feld. `used_at` = „exhausted" (gesetzt wenn `used_count == max_uses`). `users.invite_quota` = Obergrenze (Default 3, Admin-CLI erhöhbar, Admins unbegrenzt). |
| **K3** (HIGH) | Read-Pool passt nicht zu Nebenwrites (last_seen/renewal/rate-limit in GETs) | **B.5 Read-Pool/Writer-Lock wird NICHT umgesetzt.** Over-Engineering für die Zielgröße (100–1000 gelegentliche Nutzer) + reale Nebenwrite-Risiken. Beibehalten: **M1-Single-Connection + WAL + busy_timeout=5000** (bereits serialisiert, ausreichend). AK-DB-2/3/4 entfallen; PRAGMA-Test (AK-DB-1) bleibt. |
| **K4** (HIGH) | Writer-Lock vs Mail-I/O | Entfällt durch K3 (Mail-Versand bleibt wie M1 nach der DB-Arbeit). |
| **K5** (HIGH) | Backup braucht sqlite3-CLI (nicht im Image) | Backup via **Python `sqlite3.Connection.backup()`** als CLI-Command `python -m plantpal.cli backup`. |
| **K6** (HIGH) | Housekeeping löscht Invites → Redemptions (Export-Konflikt) | Housekeeping löscht abgelaufene/aufgebrauchte `invite_tokens` (+ CASCADE `invite_redemptions`). Export enthält **nur aktuell existierende** Invites (gelöschte/abgelaufene sind DSGVO-konform nicht auskunftspflichtig). |
| **K7** (HIGH) | PWA-API-Caching widersprüchlich | **`/api` und `/auth` = NetworkOnly** (nie cachen). Nur App-Shell precachen. |
| **K8** (MEDIUM) | Tropfen-Status v3-Ziel vs out-of-scope | Tropfen-Status bleibt **Spec, Umsetzung deferred** (User „für später"). v3-Definition-of-Done schließt Tropfen-Status-UI aus. |
| **K9** (MEDIUM) | Migration-Idempotenz | Idempotenz **nur über `_migrations`-Tracker**. `CREATE … IF NOT EXISTS` + nackte `ALTER ADD COLUMN`; keine PRAGMA-Existenzprüfung. |
| **K10** (MEDIUM) | Export-Format doppelt | **Ein** Schema: B.7 (nested `plants[].waterings`, mit `sessions`). ZIP `plantpal-export-<user_id>-<YYYY-MM-DD>.zip` mit `export.json` + `images/{id}.png` + `README.txt`. |
| **K11** (LOW) | Migration-Dateiname | **`002_v3.sql`** (eine konsolidierte Migration, alle v3-Deltas). |

**Von Codex bestätigt (kein Handlungsbedarf):** `ALTER ADD COLUMN NOT NULL DEFAULT` funktioniert in SQLite für Bestandszeilen; der Runner verträgt die vollständige Migration (keine Trigger/BEGIN/`;` in Literalen); der 6-stellige Code ist mit Lockout=5 + Email/IP-Limits ausreichend sicher.
