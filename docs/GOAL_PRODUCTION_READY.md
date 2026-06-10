# GOAL: PlantPal → Produktionsreife (Journey-Auftrag)

> **Start-Kommando für eine frische Session:**
> „Lies `docs/GOAL_PRODUCTION_READY.md` und arbeite die Reise ab."
>
> Stand des Auftrags: 2026-06-10, gegrillt & verifiziert mit Marius.
> Basis-Branch bei Abfassung: `ux-a11y-security-audit` (26 Commits vor `main`).

---

## 1. Mission

Bring PlantPal von „sehr guter Prototyp" auf **produktionsreif für den öffentlichen Maßstab**:
Ein fremder Erstnutzer aus dem iOS App Store muss die App ohne Erklärung verstehen und gern
täglich benutzen. Dazu gehören vier Stränge, in dieser Reihenfolge:

1. **Umwerfende UX-Recherche** (Deep Research) und deren konsequente Umsetzung — Vollständigkeit
   aller Flows, radikal wenig Text auf der Startseite, angenehme, schnelle UI.
2. **Backend-/DB-Produktionshärtung** — ist die Datenbank effizient genug? (Audit + Fixes)
3. **Raspberry-Pi-Hosting-Paket** — alles vorbereiten + Runbook, damit Marius deployen kann.
4. **iOS-App-Store-Konformität** — konform gecodet + komplett vorbereitet bis zur Xcode-Schwelle.

Du hast **weitgehende Freiheit**: Alles darf angepasst und geändert werden, solange das grobe
Ziel eingehalten wird (Grenzen: §3).

## 2. Pflichtlektüre vor dem ersten Edit

- `CLAUDE.md` — iPhone-first-Direktive, eiserne UI-Regeln, Gates (gilt unverändert!)
- `docs/IOS_APP_STORE.md` + `docs/IOS_NEXT_STEPS.md` — iOS-Strategie (Capacitor-Weg)
- `docs/MOBILE_UX_AUDIT_2026-06-09.md` — bereits umgesetzte Mobile-UX-Basis
- `docs/BACKEND_ARCHITECTURE.md` — Backend-Konventionen
- Auto-Memory `MEMORY.md` — Projekt-Historie & User-Präferenzen

## 3. Verbindlicher Rahmen (vom User festgelegt, 2026-06-10)

### Git & Rollback
- **Neuer Branch `production-ready`**, abgezweigt vom HEAD von `ux-a11y-security-audit`.
  `main` und `ux-a11y-security-audit` bleiben unberührt = Rollback-Punkte.
- **Commit frei** pro abgeschlossenem Arbeitspaket (feingranular, Gates grün).
- **Push zu `origin` frei** nach jedem Meilenstein (Backup). **Merge nach `main`: nur Marius.**

### Qualitätsmaßstab
- **Öffentlicher Maßstab**: anonymer Erstnutzer, App-Store-Review, vollständige Legal-Strecke,
  Demo-/Review-Zugang für Apple. Invite-only bleibt als Zugangsmodell erlaubt.

### Autonomie & Stop-Punkte
- Standard: **autonom entscheiden + dokumentieren** (Entscheidungs-Log, §5 Phase 0).
- **Anhalten und Marius fragen (AskUserQuestion) NUR bei:**
  1. Geld/Accounts (Apple Developer, Cloudflare-Tarife, Domains, externe Dienste),
  2. Löschen echter, sichtbarer Features → stattdessen begründete **Vorschlagsliste** führen,
  3. irreversiblen Datenmodell-Brüchen (Migrationen, die Bestandsdaten verlieren könnten).
- **Vorab freigegeben (kein Stopp nötig):**
  - **UI-Verdichtung frei**: Sektionen zusammenlegen, Texte radikal kürzen, umgruppieren —
    solange keine Funktion verloren geht.
  - **Tote Pfade sofort entfernen**: nachweislich ungenutzter Code, verwaiste i18n-Keys,
    unerreichbare Routen, überflüssige Dependencies (Nachweis im Log).
  - **Hintergrund-Galerie kürzen**: die 7 Vines-Varianten dürfen auf eine kuratierte Auswahl
    reduziert werden, wenn die UX-Recherche dafür spricht.

### Eiserne Regeln (unverändert aus CLAUDE.md)
- Keine Popups/Toasts/Modals außer bestehenden Backdrop-Sheets; Erfolg still + `announce()`;
  Fehler inline; Löschen als Undo-Kachel; globale Zustände als Banner.
- „Mirror, not judge": kein Nagging/Schuld/Streak-Countdown/Verknappung/Leaderboards.
- Spross dekorativ (`aria-hidden`), stiehlt nie den Fokus.
- warmgold Pixel-Art-Look; i18n **zweisprachig de+en** — jeder neue Key in beiden Blöcken.
- iPhone-first; iOS-HIG; Safe-Areas; Touch ≥ 44 pt; Dark Mode; reduced-motion.

### Gates (vor JEDEM Commit grün)
- Frontend: `cd frontend && npx tsc --noEmit && npx eslint src/ && npx vitest run && npx vite build`
- Backend: `.venv/bin/python -m pytest`
- Neue Logik bekommt Tests (pytest/vitest) — Produktionsreife heißt auch Testabdeckung.

### Asset-Workflow (Bilder/Logos/Icons)
- Fable generiert **keine** Bilder selbst. Stattdessen: präzise **ChatGPT-Image-Prompts**
  schreiben (magenta Hintergrund `#FF00FF`, Pixel-Art-Stilvorgaben wie bisher) und in
  `docs/ASSET_PROMPTS.md` sammeln; Marius generiert die Bilder und legt sie in den Chat/Ordner.
- **Nie auf Assets blockieren**: Platzhalter einbauen, Einbau-Pipeline
  (`scripts/build_sprites.py`-Muster: remove_bg → alpha_bbox → fit) vorbereiten, weiterarbeiten.

### Kontext-Kontinuität (lange Reise)
- `docs/JOURNEY_LOG.md` als lebendes Log führen: erledigt / entschieden (mit Begründung) /
  Vorschlagsliste Feature-Streichungen / nächste Schritte. Nach jeder Phase aktualisieren,
  sodass eine frische Session nahtlos übernehmen könnte.

### Verifikation (User-Präferenz aus Memory)
- **Nach jeder Phase**: Codex-Review (`codex`-CLI) über das Phasen-Diff laufen lassen,
  bestätigte Findings sofort fixen.
- **Am Ende der Reise**: Session-Verify (≤ 20 Agents) über die gesamte Reise.
- Falls Marius zwischendurch Audit-Ergebnisse liefert (`/code-review ultra`/Codex):
  einarbeiten, bestätigte Findings fixen.

---

## 4. Was bereits existiert (nicht neu erfinden!)

- **Mobile-UX-Basis**: iOS-Tab-Bar (Pixel-Icons, zentraler Spross), Instagram-Navigation ohne
  Back-Buttons, Safe-Areas, 44-pt-Targets, Keyboard-aware Tab-Bar, A11y-Pass (Session 06/2026).
- **DB-Grundhärtung**: WAL, `busy_timeout=5000`, `foreign_keys=ON`, `synchronous=NORMAL`,
  nummerierte Migrationen, per-Request-Connection.
- **Deploy-Gerüst**: `Dockerfile`, `docker-compose.yml` (kein Host-Port — Cloudflare Tunnel
  als Ingress, `cloudflared`-Service), Litestream-Profil (`--profile backup`),
  `scripts/backup.sh` (Cron-Snapshot + rsync), Health-Route mit WAL-/Scheduler-Status.
- **Auth & Account**: Magic-Link-Login, 90-Tage-Session, Invite-System, E-Mail-Änderung,
  **Account-Löschung in-App** (App-Store-Pflicht ✓), Daten-Export.
- **iOS-Doku**: Capacitor-Empfehlung, 4.2-Featureliste (Push/Haptics/…), Review-Risiken.

## 5. Phasenplan

### Phase 0 — Setup & Bestandsaufnahme
- Branch `production-ready` von `ux-a11y-security-audit` abzweigen; `docs/JOURNEY_LOG.md` anlegen.
- Ist-Analyse: alle Pages/Flows einmal durchgehen (auch per Headless-Screenshot), offene
  Sackgassen/Inkonsistenzen notieren. Test-Status + Coverage festhalten.

### Phase 1 — UX-Deep-Research („umwerfend")
- Deep Research (Web) zu: Mobile-first-UX 2026, Daily-Ritual-/Habit-Apps, Onboarding-Patterns
  (Erstnutzer ohne Erklärung), Text-Minimalismus/Glanceability, iOS-HIG-Feinheiten,
  Pflanzen-App-Konkurrenzanalyse (Planta, Greg, Flora — was nervt, was funktioniert).
- Ergebnis: `docs/UX_RESEARCH_PRODUCTION.md` — priorisierte, PlantPal-konkrete Findings
  (nicht generisch!), je Finding: Problem → Empfehlung → betroffene Stelle.

### Phase 2 — UX-Umsetzung
- **Startseite radikal entschlacken**: so wenig Text wie möglich, glanceable (Zahlen/Icons
  statt Sätze); Begrüßungs-/Statusband prüfen und eindampfen.
- **Erstnutzer-Onboarding**: vom leeren Zustand zur ersten Pflanze ohne Erklärtext-Wände;
  Empty-States aller Pages.
- **Vollständigkeits-Audit**: jeden Flow zu Ende denken (Fehlerfälle, Offline, lange Listen,
  lange Namen, 0/1/viele Pflanzen); keine UI-Sackgassen.
- i18n de+en für alles Neue; A11y-Pass; Performance-Gefühl (Skeletons statt Spinner, optimistic
  updates wo sinnvoll).

### Phase 3 — Backend-/DB-Produktionshärtung
- **DB-Effizienz-Audit**: fehlende Indizes (FK-Spalten, häufige WHEREs), `EXPLAIN QUERY PLAN`
  der Hauptqueries, N+1-Suche, Pagination-Verhalten.
- **Lasttest realistisch**: ~50 User × je ~100 Pflanzen × 2 Jahre Gieß-Historie generieren;
  p95-Latenzen der Kern-Endpoints messen (vorher/nachher dokumentieren).
- **Backup-Probe**: backup.sh + Litestream-Restore einmal end-to-end durchspielen (lokal),
  Schritte ins Runbook.
- Security-Pass: Rate-Limits, Security-Header, Session-/Token-Hygiene, Upload-Härtung;
  Logs produktionstauglich (keine sensiblen Daten).

### Phase 4 — Raspberry-Pi-Hosting-Paket
- **ARM64-Build verifizieren**: `docker buildx` Multi-Arch (linux/arm64) baut sauber durch;
  Image-Größe im Blick.
- **Rücksicht: der Pi hostet schon andere Dienste** — keine Host-Port-Kollisionen (Compose
  nutzt bereits nur `expose` + Tunnel ✓), RAM-/CPU-Limits im Compose setzen, eigenes
  Compose-Projekt-Naming.
- `docs/PI_RUNBOOK.md` Schritt-für-Schritt: Voraussetzungen → `.env` ausfüllen
  (`.env.example` vervollständigen!) → Deploy → Update-Prozedur → Backup/Restore →
  Monitoring (Health-Check) → Rollback. Geschrieben für „Marius am Sonntagabend", nicht
  für DevOps-Profis.
- Cloudflare-Tunnel-Anleitung konkret für `getplantpal.com` (Tunnel anlegen, Token in `.env`,
  Route auf `http://plantpal:8000`).

### Phase 5 — iOS-Paket (konform + komplett vorbereitet)
- **Review-Konformität**: Guideline-4.2-Mehrwert dokumentieren, Demo-/Review-Account-Mechanik
  für Apple (Review-Login ohne Magic-Link-Hürde!), Privacy-Labels-Entwurf,
  Datenschutz/Impressum erreichbar, Account-Löschung ✓.
- **Capacitor-Gerüst** im Repo (auf Linux machbar: init, config, ios-Platform-Scaffold;
  `pod install`/Xcode-Build bleiben außen vor).
- **Asset-Prompts** (`docs/ASSET_PROMPTS.md`): App-Icon 1024 px (+ Set-Ableitung per Skript),
  Splash/Launch, Screenshot-Plan je Gerätegröße — als ChatGPT-Image-Prompts für Marius.
- `docs/IOS_SUBMISSION_CHECKLIST.md` inkl. **„Erste Mac-Session"-Anleitung** (Mac vorhanden,
  Apple-Account fehlt noch): Xcode öffnen, Simulator-Lauf, was wann der 99-€-Account braucht.

### Phase 6 — Abschluss
- Finaler Session-Verify (≤ 20 Agents) über die gesamte Reise; Findings fixen.
- Lighthouse-/Performance-Pass (PWA, Best Practices, A11y ≥ 90).
- `docs/JOURNEY_REPORT.md`: Was wurde geändert & warum, Vorschlagsliste Feature-Streichungen,
  offene User-TODOs (siehe §7), Empfehlung für den Merge nach `main`.

## 6. Definition of Done

- [ ] Erstnutzer kommt ohne Erklärung von App-Store-Install bis zur ersten gegossenen Pflanze.
- [ ] Startseite: minimaler Text, glanceable, kein Erklär-Overload.
- [ ] Alle Flows vollständig (0/1/viele, Fehler, Offline, Extremwerte) — keine Sackgassen.
- [ ] DB-Audit dokumentiert: Indizes gesetzt, p95 der Kern-Endpoints unter Last gemessen & ok.
- [ ] Backup → Restore einmal real durchgespielt und im Runbook beschrieben.
- [ ] ARM64-Image baut; `PI_RUNBOOK.md` von „frischem Terminal" bis „App läuft unter Domain".
- [ ] iOS: Capacitor-Gerüst + Submission-Checkliste + Asset-Prompts vollständig.
- [ ] Alle Gates grün; neue Logik getestet; Codex-Review je Phase gelaufen; Session-Verify am Ende.
- [ ] `JOURNEY_LOG.md` + `JOURNEY_REPORT.md` vollständig; Branch gepusht; main unberührt.

## 7. TODOs für Marius (außerhalb der Reise — die Reise blockiert NIE darauf)

### 7.1 Domain `getplantpal.com` aktivieren (≈ 10 Minuten)
Die Domain ist registriert und im Cloudflare-Account angelegt, nutzt aber noch nicht
Cloudflares Nameserver (daher die Cloudflare-Mail):

1. Beim **Registrar** einloggen (wo die Domain gekauft wurde; falls unklar:
   [ICANN Lookup](https://lookup.icann.org) → `getplantpal.com` → „Registrar").
2. Dort die DNS-/Nameserver-Einstellungen öffnen und die vorhandenen Nameserver durch
   **genau diese zwei** ersetzen (keine weiteren daneben stehen lassen):
   - `mariah.ns.cloudflare.com`
   - `porter.ns.cloudflare.com`
3. Speichern. Propagation dauert Minuten bis max. ~24 h.
4. Im [Cloudflare-Dashboard](https://dash.cloudflare.com) prüfen: `getplantpal.com` →
   Status muss von „Pending" auf **„Active"** springen (Cloudflare mailt auch).
5. Erst NACH „Active": Zero-Trust → Tunnels → Tunnel anlegen, Public Hostname
   `getplantpal.com` → `http://plantpal:8000` routen, Token als
   `CLOUDFLARE_TUNNEL_TOKEN` in die `.env` auf dem Pi (Details: `PI_RUNBOOK.md`).

### 7.2 Später (wenn die Reise die Pakete geliefert hat)
- Apple Developer Program (99 €/Jahr) abschließen — erst nötig für Push/TestFlight/Submission.
- Asset-Prompts aus `docs/ASSET_PROMPTS.md` mit ChatGPT Image generieren und zurückgeben.
- Pi-Deploy nach `docs/PI_RUNBOOK.md` durchführen.
- Erste Mac-Session nach `docs/IOS_SUBMISSION_CHECKLIST.md`.
