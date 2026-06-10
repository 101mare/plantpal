# Journey-Report: PlantPal → Produktionsreife

> Abschlussbericht der autonomen Reise vom 2026-06-10 (Branch `production-ready`,
> 26 Commits ab `edcc3d6`, gepusht). Auftrag: `docs/GOAL_PRODUCTION_READY.md`.
> Prozess-Log: `docs/JOURNEY_LOG.md`. **main blieb unberührt** (Rollback jederzeit).

## Ergebnis in einem Satz

PlantPal ist jetzt auf dem Stand „öffentlicher Erstnutzer": research-gestützte
Glance-Startseite, Pflanze #1 in unter 30 Sekunden, ein behobener P0-Login-Bug,
DB-Audit mit Urteil „skaliert locker", fertiges Pi-Deploy-Paket und ein iOS-Paket,
das bis zur Xcode-Schwelle wirklich funktioniert (Bearer-Auth statt Cookie-Gamble) —
alles getestet (379 pytest / 30 vitest, alle Gates grün, je Meilenstein verifiziert).

## Die wichtigsten Funde (hätten produktiv wehgetan)

1. **P0: Login war in echten Browsern komplett kaputt.** `Referrer-Policy: no-referrer`
   ließ Browser den Origin-Header von Same-Origin-POSTs zu `null` serialisieren →
   Magic-Link UND Code-Login wurden serverseitig abgelehnt. Tests blieben grün, weil
   httpx den Origin explizit setzt. Gefunden im ersten echten Playwright-Walkthrough,
   gefixt (`same-origin`), mit Regressionstest gepinnt. (`4111751`)
2. **iOS-Shell wäre nicht einloggbar gewesen** (Session-Verify, 4 unabhängige Blocker:
   kein CORS, SameSite=Lax, CSRF-Cookie cross-origin unlesbar, strikter Origin-Check).
   Gelöst durch einen Bearer-Token-Pfad + `ALLOWED_APP_ORIGINS` + CORS — end-to-end mit
   Produktions-Settings getestet, BEVOR je ein Mac angefasst wird. (`c4c7ffd`)
3. **Impressum/Datenschutz waren eingeloggt unerreichbar** (Apple-5.1.1(i)-/§5-DDG-
   Verstoß) → Settings-Footer. (`7388f7c`)
4. **Dokumentierte Backup-Cron-Zeile wäre nie gelaufen** (Permission-Falle /var/log +
   auskommentierte Zeile) → gefixt, bevor sie je jemand installiert hat.

## Was sich für Nutzer ändert (Phase 2, research-gestützt)

- **Startseite als Glance-Widget:** Gold-Tropfen + große Zahl („3 durstig") statt
  „DURSTIGE PFLANZEN!"; explizites „✓ Alle versorgt"; Tag-1-Zeile „Morgen siehst du
  hier, wer Durst hat."; Gieß-Erfolg = stilles ✓-Ausgleiten der Zeile.
- **Pflanze #1 in <30 s:** Foto optional (Pixel-Platzhalter), Name+Intervall vorn,
  Rest hinter „Mehr Details" — die Anti-These zum Planta-Setup-Marathon.
- **Emoji-frei:** handgepixeltes 8×8-SVG-Icon-Set (tropfen/check/papierkorb/kamera/
  schloss/pokal/balken) — plattform-identisch, theme-tintbar, Press-Start-2P-konsistent.
- **Mirror, not judge geschärft:** „Streak: 0"-Kachel ersetzt durch Bestwert-Vitalität
  (fällt nie), Texte halbiert, Hintergrund-Galerie auf 3 kuratiert.
- **A11y:** Lighthouse 100; Gieß-Fokus-Reparatur (WCAG 2.4.3), Label-in-Name-Fix,
  Status nie nur als Farbe.

## Zahlen

| Metrik | Vorher | Nachher |
|---|---|---|
| pytest / Coverage | 360 / 92 % | **379** / ~92 % |
| Lighthouse (Login) | – | Perf **80** · A11y **100** · BP **100** |
| p95 unter Last (510k Waterings, 100-Pflanzen-User) | – | plants 9,6 ms · stats 33 ms · water 8,9 ms |
| Bundle (gzip) | 88 KB, unkomprimiert ausgeliefert | 88 KB, **gzip + 1J-Cache-TTL** |
| Backup-Restore | ungeprobt | geprobt (63 MB, integrity ok, Boot ok) |

## Verifikation (mehrschichtig)

1. Gates je Commit (tsc/eslint/prettier/vitest/build + pytest).
2. Playwright im echten Chromium je UI-Paket (390×844@2x, de+en, dark+light).
3. **Codex-Review** über das Phasen-Diff: kein P0, 3 bestätigte Findings → gefixt.
4. **Session-Verify-Workflow** (18 Agents, 6 Dimensionen × adversariale Prüfung):
   9 bestätigte Findings, 0 falsch-positiv → ALLE gefixt (inkl. Mutations-Test-Nachweis,
   dass die neue Raw-Multipart-Regression echte Lücken schließt).
5. Finaler Web-Smoke nach dem Auth-Umbau: Login + Gießen + Morph ✓.

## Vorschlagsliste (deine Entscheidung, nichts wurde gelöscht)

- **V1 Streak-Trophäen** („7-Tage-/30-Tage-Streak" als gesperrte Ziele = Streak-Druck):
  ersetzen durch Sammel-Meilensteine („10 Pflanzen", „100× gegossen") oder erst nach
  Erreichen anzeigen. Aufwand: klein (sprossState.ts + i18n).
- **Shell-Fotos v1** (bekannte Einschränkung): `<img>` sendet keinen Bearer → Fotos
  zeigen in der iOS-Shell den Platzhalter. Optionen in der Checkliste (AuthedImage via
  blob-fetch ODER signierte Bild-URLs) — Entscheidung sinnvoll in der Mac-Session.
- **Stats-Endpoint** lädt die volle Watering-Historie (33 ms p95 beim Extremnutzer,
  ~150 ms Pi): bewusst NICHT optimiert. Erst relevant ab ~5× heutiger Zielskala.

## Deine TODOs (gebündelt, in sinnvoller Reihenfolge)

1. **Impressum ausfüllen** (`frontend/src/pages/LegalPages.tsx`): `[Dein Name]`-Platzhalter
   durch echte Angaben ersetzen — §5-DDG-Pflicht VOR jedem öffentlichen Hosting. (5 Min)
2. **Domain aktivieren:** Nameserver beim Registrar auf `mariah.ns.cloudflare.com` +
   `porter.ns.cloudflare.com` umstellen → Cloudflare-Status „Active". (10 Min + Wartezeit)
3. **Resend einrichten** (Konto + Domain verifizieren + API-Key) — fürs Magic-Link-Mailing.
4. **Pi-Deploy** nach `docs/PI_RUNBOOK.md` (Compose, Tunnel, Backups-Cron). (~1 h)
5. **Review des Branches + Merge:** `production-ready` ansehen (26 Commits, jeder
   self-contained) → wenn zufrieden: nach `main` mergen.
6. **Assets generieren** nach `docs/ASSET_PROMPTS.md` (App-Icon 1024 ist Pflicht,
   Splash optional) und mir in den Chat posten.
7. **Apple Developer Program** (99 €/Jahr) — erst nötig für TestFlight/Submission.
8. **Erste Mac-Session** nach `docs/IOS_SUBMISSION_CHECKLIST.md` §2 (~1–2 h am Mac).
9. App Store Connect nach Checkliste §3 (Privacy-Labels, DSA-Trader **früh** klären,
   Support-Seite, Review-Accounts non-admin + `REVIEW_*` in `.env`, danach wieder leeren).

## Empfehlung zum Merge

Der Branch ist in sich konsistent, jede Phase einzeln verifiziert, main unberührt.
Empfohlen: kurzes eigenes Durchklicken am Handy (Dev-Server oder Pi), dann Merge —
ein `/code-review ultra` über den Branch davor schadet nie, ist aber nach Codex +
18-Agent-Verify Kür, nicht Pflicht.
