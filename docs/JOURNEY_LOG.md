# Journey-Log: PlantPal → Produktionsreife

> Lebendes Log der autonomen Reise (`docs/GOAL_PRODUCTION_READY.md`).
> Branch: `production-ready` (ab `edcc3d6`, main unberührt). Gestartet: 2026-06-10.
> Direktive von Marius unterwegs: **keine Unterbrechungen** — Stop-Punkte werden geloggt
> und am Ende gebündelt delegiert. **Design hervorragend, kein KI-Slop** — die warmgold
> Pixel-Identität wird geschärft, nie auf generische Patterns verwässert.

## Status

| Phase | Stand |
|---|---|
| 0 — Setup & Bestandsaufnahme | ✅ abgeschlossen 2026-06-10 |
| 1 — UX-Deep-Research | ✅ abgeschlossen 2026-06-10 (`docs/UX_RESEARCH_PRODUCTION.md`) |
| 2 — UX-Umsetzung | ✅ Kern abgeschlossen 2026-06-10 (Codex-Review läuft; D2–D5-Restsweep im Phase-6-Verify) |
| 3 — Backend-/DB-Härtung | ✅ abgeschlossen 2026-06-10 (Audit: produktionsreif) |
| 4 — Pi-Hosting-Paket | offen |
| 5 — iOS-Paket | offen |
| 6 — Abschluss | offen |

## Baseline (Phase 0, 2026-06-10)

- Backend: **360 pytest passed, 92 % Coverage** (TOTAL 2021 Stmts / 169 Miss).
- Frontend: 30 vitest, tsc/eslint/build grün (Stand `edcc3d6`).
- DB-Pragmas bereits gesetzt: WAL, busy_timeout=5000, foreign_keys=ON, synchronous=NORMAL.
- Deploy-Gerüst vorhanden: Dockerfile, Compose (Tunnel-only ingress, Litestream-Profil,
  backup.sh), Health-Route.
- Demo-Umgebung für die Reise: uvicorn :8400, DB `/tmp/pp-journey/data/plantpal.db`,
  Demo-User `demo@plantpal.local`, 8 Pflanzen (3 durstig), 85 Waterings über 60 Tage.
  Screenshot-Walkthrough: `/tmp/pp-journey/shots/` (21 Shots, dark+light, alle Routen),
  Skript `/tmp/pp-journey/shoot.py` (Playwright, im venv installiert).

## Entscheidungs-Log

| # | Entscheidung | Begründung |
|---|---|---|
| D1 | `Referrer-Policy: no-referrer` → **`same-origin`** (global) | **P0-Bug:** Unter no-referrer serialisieren Browser den Origin-Header von Same-Origin-POSTs zu `null`/weglassen (Fetch-Spec) → `require_same_origin_submit` lehnte **jeden echten Browser-Login ab** (Magic-Link-Interstitial UND Code-Login), seit dem Interstitial-Umbau (Bug-Hunt 06-05). httpx-Tests setzen Origin explizit und blieben grün. `same-origin` leakt weiterhin nichts cross-site (auch keine `?token=`-URLs). `Origin: null` bleibt abgelehnt (Sandbox-Angreifer). Per Playwright im echten Chromium verifiziert: Login funktioniert wieder. |
| D2 | Playwright-Python ins venv installiert (nutzt vorhandenes Chromium-Binary) | Echte Browser-Verifikation (Login-Flow, Screenshots, Theme-Wechsel) für die ganze Reise; deckte sofort D1 auf. Dev-Dependency, kein Produktions-Impact. |

## Findings-Inventar Phase 0 (→ Phase 2/3-Arbeitsliste)

**P0 (sofort gefixt):**
- F1 ✅ Browser-Login kaputt (Referrer-Policy) — gefixt, Regressionstest ergänzt (D1).

**P1 (Phase 2 — UX/Konformität):**
- F2 Foto ist **Pflichtfeld** beim Pflanze-Anlegen → blockiert „erste Pflanze in <30 s"
  (Konkurrenz-Lehre #2/#3); optional machen + charmanter Pixel-Platzhalter.
- F3 **Impressum/Datenschutz eingeloggt unerreichbar** (nur auf Login-Seite via
  LangThemeBar) → verletzt Apple 5.1.1(i) („easily accessible in-app") + §5 DDG
  (≤2 Klicks); Settings-Footer-Links ergänzen.
- F4 Startseiten-Band „DURSTIGE PFLANZEN!" = lauter Ausruf statt Glance-Antwort →
  Zahl-zuerst-Band („3 durstig" / „✓ Alle versorgt"-Zustand fehlt komplett) gemäß
  Research-Bauplan.
- F5 Durstig-Zeilen: Namen extrem gestutzt („BASILIK…"), Status wortreich
  („2 Tage überfällig") → Layout-Budget neu verteilen, Kurzform („2d über").
- F6 Stats zeigt **„Gieß-Streak (Tage): 0"** → Schuld-Signal, verletzt „mirror, not
  judge"; reframen (z. B. Bestwert/ruhige Formulierung) — Umbenennung ist freigegebene
  UI-Verdichtung, keine Feature-Löschung.
- F7 Login-Seite: Code-Eingabe-Weg muss am Phone gleichwertig prominent sein
  (Magic-Link-Kontextwechsel = größter Drop-off; Apple-Review braucht Code-Pfad).
- F8 Texte wortreich: Urlaubs-Modus-Erklärung, „ANTIPPEN!", Vitalitäts-Zeilen →
  Textbudget ≤12 Wörter pro Fläche (NN/g: 20–28 % werden gelesen).
- F9 Add-Sheet: 6 Felder flach → Name (+ optional Foto) + Intervall vorn, Rest
  hinter „Mehr Details" (Progressive Disclosure).

**Vorschlagsliste Feature-Streichungen/-Änderungen (Entscheidung Marius am Ende):**
- V1 Trophäen „7-Tage-Streak"/„30-Tage-Streak": als gesperrte Ziele erzeugen sie
  Streak-Druck (Konflikt mit Eisenregel). Vorschlag: durch druckfreie Sammel-Meilensteine
  ersetzen (z. B. „10 Pflanzen", „100 Gießvorgänge") oder nur nach Erreichen anzeigen.
- V2 Hintergrund-Galerie: 7 Vines-Farbvarianten → kuratiert auf ~3 (freigegeben,
  Umsetzung nach UX-Research-Abwägung in Phase 2).

## Gesammelte User-TODOs (Delegation am Ende, Details §7 im Goal)

1. Domain `getplantpal.com`: Nameserver beim Registrar auf `mariah.ns.cloudflare.com` +
   `porter.ns.cloudflare.com` umstellen → Cloudflare „Active" abwarten.
2. Apple Developer Program (99 €/Jahr) — erst für TestFlight/Submission nötig.
3. Asset-Prompts aus `docs/ASSET_PROMPTS.md` (entsteht in Phase 5) mit ChatGPT Image
   generieren.
4. Pi-Deploy nach `docs/PI_RUNBOOK.md` (entsteht in Phase 4).

## Phase 2 — gelieferte Pakete (alle Gates grün, je Commit verifiziert)

| Commit | Paket |
|---|---|
| `df59e18` | Zahl-zuerst-Band + PixelIcon-Set (Emoji-frei) + Kurz-Status-Vokabular + ✓-Exit-Morph + Karten-Verdichtung + Suche ab 6 Pflanzen |
| `f36eccd` | Foto optional (Backend+Frontend, +2 pytest) + Progressive Disclosure im Add-Sheet → erste Pflanze in <30 s |
| `7388f7c` | Legal-Footer in Settings (Apple 5.1.1(i)/§5 DDG), i18n-Legal-Labels, Theme-Toggle-Emojis raus |
| `~`      | Stats beruhigt: Bestwert statt Streak-0, Ø-Intervall-Kachel, Trophy/Lock/Bars-PixelIcons, Spross-Texte halbiert |
| `a348a03` | Hintergrund-Galerie 7→3 kuratiert (V2), Legacy-Sanitize |
| `~`      | Tag-1-Ritual-Zeile („Morgen siehst du hier, wer Durst hat.") — selbstentfernend |

Verifiziert via Playwright (echtes Chromium, 390×844@2x, de+en): Band-Zustände
(n>0 / Morph / Alle versorgt / Tag-1), Quick-Add ohne Foto end-to-end, Stats/Spross.
Neue Funde unterwegs: Impressum enthält Platzhalter `[Dein Name]` → **User-TODO #5**.

## Gesammelte User-TODOs — Ergänzung

5. **Impressum ausfüllen** (`frontend/src/pages/LegalPages.tsx`): echter Name/Adresse/
   E-Mail statt Platzhalter — §5-DDG-Pflicht VOR jedem öffentlichen Hosting/Submission.

## Phase 3 — Backend-/DB-Audit (2026-06-10): Urteil „produktionsreif"

**Lasttest** (50 User × 100 Pflanzen × 2 J ≈ 510 776 Waterings, 63 MB, x86; Messung am
Extremnutzer mit 100 Pflanzen):

| Endpoint | p50 | p95 |
|---|---|---|
| GET /api/plants (100 Stück) | 3,9 ms | 9,6 ms |
| GET /api/plants?group=room | 5,8 ms | 10,6 ms |
| GET /api/stats | 24,1 ms | **33,0 ms** (schwerster) |
| GET /api/me (Session-Check) | 3,7 ms | 4,6 ms |
| POST water | 7,6 ms | 8,9 ms |
| GET waterings-Historie | 11,6 ms | 14,5 ms |

Pi-Hochrechnung (×3–5): schlechtester Fall ~100–165 ms für die Stats-Seite eines
100-Pflanzen-Users → **keine Optimierung nötig**; bewusst KEIN vorauseilendes Umbauen von
`compute_stats` (lädt volle User-Historie — bei Zielskala unkritisch, Semantik bleibt).
Nebenbefund: Rate-Limiter (30/m Mutationen) bremste den Benchmark korrekt aus ✓.

**Indizes:** bereits vollständig (user/plant-FKs, partielle Indizes für aktive Pflanzen,
Sessions via `session_hash UNIQUE`, waterings beidseitig mit `watered_at DESC`). EXPLAIN
zeigt Index-Pfade, keine Full-Scans auf heißen Queries.

**Backup-Restore-Probe** (Code-Pfad von scripts/backup.sh): Snapshot der 63-MB-DB unter
laufendem Server in 0,28 s, `integrity_check: ok`, alle Zeilenzahlen identisch, Restore
bootet durch die Migrationen. Litestream bleibt als optionales Off-site-Profil.

**Security-Pass:** Tokens HMAC-gepeppert (sha256), Session-Cookie HttpOnly+Secure(prod)+
SameSite=Lax, CSRF double-submit, keine sensiblen Daten in Logs, keine print()-Reste,
Upload-Pipeline limitiert (Größe/Pixel/Content-Type). Header seit D1 korrekt.

## Nächste Schritte

- Codex-Findings (läuft im Hintergrund) einarbeiten.
- Phase 4: ARM64-Build, Compose-Ressourcen-Limits, .env.example, PI_RUNBOOK.md.
