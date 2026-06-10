# UX-Research → Produktionsreife (Phase 1 der Journey)

> Synthese aus 4 Deep-Research-Strängen (2026-06-10): Onboarding/First-Run,
> Glanceability/Text-Minimalismus, Konkurrenz-Teardown (Planta/Greg/Flora/Vera/Blossom/
> PictureThis/Happy Plant), iOS-Review-Praxis 2026. Vollständige Quellenlisten in den
> jeweiligen Abschnitten der Agent-Berichte; hier nur die PlantPal-konkreten,
> priorisierten Konsequenzen. Format: **Problem → Empfehlung → Stelle**.

## Leitplanken aus der Evidenz (für alle Phasen verbindlich)

1. **Kein Tutorial, keine Coach-Marks, kein Intro-Carousel — nie.** NN/g-Quantstudie:
   Tutorials verschlechtern wahrgenommene Leichtigkeit signifikant (SEQ 4.92 vs. 5.49,
   p=0.047) bei null Task-Gewinn; 76 % der Tooltips werden in <3 s weggewischt.
   Budget stattdessen in selbsterklärende UI.
2. **Textbudget:** Nutzer lesen 20–28 % der Wörter, 79 % scannen. First-Run-Flächen
   ≤12 Wörter, Status nie als Satz, Verben zuerst, de+en paarweise testen (Deutsch
   +20–35 % Länge = Stresstest).
3. **Glance-Hierarchie:** 57 % der Sehzeit above the fold. Ein Primärsignal pro Screen
   (Durstig-Zustand), glance-kritische Zahlen sind die GRÖSSTEN Textelemente,
   Farbe nie allein (WCAG 1.4.1 — immer Zahl/Icon dazu).
4. **Apple-Widget-Doktrin als Bauprinzip:** „Widget, nicht Website-Header" — richtige
   Menge Info, Single-Tap-Aktionen, keine Mini-App-Bänder. Dieselbe Architektur wird
   später das iOS-Widget.
5. **Marktlücke = unsere Identität:** Die „Vera-Lücke" (ruhig + ehrlich gratis + werbefrei)
   ist seit 2024 unbesetzt; jede Top-App hat dokumentierte Paywall-/Nagging-Wut.
   „Mirror, not judge" + Pokédex-Sammelfreude + Pixel-Charme sind die Differenzierer —
   niemals Druck-Mechaniken, Task-Inflation oder Pseudo-KI kopieren.

## A. Startseite (Plantdex) — Phase-2-Kernumbau

| # | Problem (Ist) | Empfehlung (Soll) | Stelle |
|---|---|---|---|
| A1 | Band schreit „DURSTIGE PFLANZEN!" — Ausruf statt Antwort; bei 0 durstig verschwindet es ersatzlos (Kernfrage bleibt unbeantwortet) | Zahl-zuerst-Band: 💧-Icon + **Count als größte Zahl des Screens** + 1 Wort („3 durstig"); bei 0: stille Grün-Zeile „✓ Alle versorgt" (keine Animation). Band-Akzent folgt schlimmster Stufe | `PlantdexPage.tsx` ThirstySection |
| A2 | Durstig-Zeilen: Name auf ~8 Zeichen gestutzt, Status dreizeilig wortreich („2 Tage überfällig") | Layout-Budget: Name bekommt Breite (1 Zeile, ellipsis spät), Status als Kurzform „2d über"/„heute" (fixes Vokabular, identische Slot-Position), Gieß-Button ≥44 pt rechts (Daumenzone) | ThirstySection-Zeilen |
| A3 | Gießen aus der Liste = 1 Tap ✓, aber Erfolg ist nur „Zeile weg" | Badge morpht in-place zu ✓, Zeile gleitet ruhig raus, `announce()` — Tubik-Pattern, bleibt still | ThirstySection + PlantCard |
| A4 | Suche + Sort-Dropdown sitzen zwischen Band und Sammlung, volle Breite, immer sichtbar | Unter das Band gehört die Sammlung; Suche/Sort sind Bibliotheks-Werkzeuge: kompakter, visuell leiser (eine Zeile), erst ab ~6 Pflanzen rendern | PlantdexPage |
| A5 | Karten zeigen Foto+Name+Raum; Status-Badge nur bei non-ok | Karte = Foto + Name + Status-Slot (fixe Position). Raum-Zeile nur zeigen, wenn nach Raum sortiert/gruppiert. „ok"-Dot bleibt dezent | `PlantCard.tsx` |
| A6 | Begrüßungs-Caption (nach >3 Tagen) ist gut dosiert | Beibehalten — Personalisierung über Inhalt, nie Anrede-Prosa. Keine neuen Header-Texte | — |

## B. Onboarding & First-Run — Phase 2

| # | Problem | Empfehlung | Stelle |
|---|---|---|---|
| B1 | Foto ist Pflichtfeld → „erste Pflanze in <30 s" unmöglich (Konkurrenz-No-Go: Plantas Setup-Marathon) | Foto **optional**: charmanter Pixel-Platzhalter (Topf-Silhouette) statt Zwang; „Foto später" ist ein Tap im Detail-Sheet | `AddPlantModal.tsx`, Backend erlaubt es schon? prüfen `routes/plants.py` |
| B2 | Add-Sheet: 6 Felder flach | Vorn: Name (autofokussiert) + Intervall (Default 7) + Foto-Slot. „Mehr Details" (Raum/Notizen/Wassermenge) eingeklappt — Progressive Disclosure, max. 2 Ebenen | AddPlantModal |
| B3 | Empty State öffnet Add-Sheet ✓, aber danach kein Ritual-Hinweis | Nach Pflanze #1: stille Inline-Zeile im Band-Slot „Morgen siehst du hier, wer Durst hat" (≤8 Wörter, verschwindet am Folgetag) — Empty-State-als-Onboarding statt Tutorial | PlantdexPage |
| B4 | Neue Pflanze gilt sofort als „heute fällig"? prüfen | Niemals Day-1-überfällig (Planta-Beschwerde #1): `last_watered_at = jetzt` beim Anlegen ODER neutraler Zustand bis zum ersten Gießen | `plant_service.py` prüfen |
| B5 | Login: Code-Weg als Fallback versteckt | Am Phone gleichwertig: nach „Link gesendet" den Code-Eingabe-Link prominent (+ „Mail-App öffnen"-Button im sent-Zustand); Apple-Review braucht den Code-Pfad ohnehin | `LoginPage.tsx` |
| B6 | Keine Beispiel-Pflanzen | So lassen — Fake-Einträge entwerten den Pokédex; Demo-Daten nur im Apple-Review-Account | — |

## C. Stats & Spross — Phase 2 (mirror, not judge schärfen)

| # | Problem | Empfehlung | Stelle |
|---|---|---|---|
| C1 | „Gieß-Streak (Tage): 0" = tägliches Schuld-Signal | Reframen auf ratchet/ruhig: „Bester Lauf: X Tage" (peak, fällt nie) oder Kachel ersetzen durch „Diese Woche gegossen: n" | `StatsPage.tsx` |
| C2 | Streak-Trophäen („7-Tage-…", „30-Tage-Streak") als gesperrte Ziele = Druck | → Vorschlagsliste V1 (Entscheidung Marius): druckfreie Sammel-Meilensteine („10 Pflanzen", „100× gegossen") oder erst nach Erreichen sichtbar | `sprossState.ts`, SprossPage |
| C3 | Wortreiche Erklärtexte (Urlaubs-Modus 3 Zeilen, „ANTIPPEN!") | Texte halbieren: Urlaubs-Hint 1 Zeile; „Antippen"-Nudge ist ok (selbstlöschend), aber leiser (kein !) | SprossPage, i18n |
| C4 | Stats-Seite unten leer | Kein Füll-Content erfinden — lieber 1 ruhige Zusatz-Kachel mit echtem Wert (z. B. „Ø Intervall: 8,6 T" — existiert im API) | StatsPage |

## D. Vollständigkeits-Audit — Phase 2 Checkliste

- D1 **Legal eingeloggt erreichbar**: Settings-Footer „Impressum · Datenschutz" (Apple
  5.1.1(i) + §5 DDG ≤2 Klicks). Zusätzlich Datenschutz: Abschnitt Aufbewahrung/Löschung
  prüfen/ergänzen.
- D2 Offline-Verhalten: ErrorState mit Retry existiert? Pro Page prüfen; gebrandeter
  Offline-Zustand (kein Browser-Fehlerbild) — zahlt auch auf iOS 4.2 ein.
- D3 Extremfälle je Page: 0/1/50 Pflanzen, 60-Zeichen-Namen, 365-Tage-Intervall,
  fehlende Bilder (Platzhalter!), lange Räume, en-Locale.
- D4 Jeder Flow endet kontrolliert: Login-Fehler inline, Invite abgelaufen,
  Export-Download, Account-Löschung (Bestätigen → Logout → Login-Seite).
- D5 A11y-Durchlauf: Fokus-Reihenfolge, aria-Labels neue Elemente, Kontraste der neuen
  Kurz-Status (4.5:1), Dynamic-Type-Verhalten (rem-basiert).

## E. iOS-Paket — Phase-5-Arbeitsliste (aus Review-Praxis-Research)

**[CODE] vor Einreichung (Phase 5 baut, soweit Linux-machbar):**
1. Capacitor mit **gebündelten** Assets (kein `server.url` auf Prod) → Auth über
   `capacitor://`-Origin klären (größter Posten; Cookie vs. Token).
2. **Review-Account-Mechanik**: Config-Flag `REVIEW_ACCOUNT_EMAIL` + fester 6-stelliger
   Code (nie ablaufend, Rate-Limit-Ausnahme), baut auf `verify_login_code` auf;
   Demo-Pflanzen-Seed für diesen Account.
3. Local Notifications + Priming (kontextuell nach erster Pflanze, Inline-Karte statt
   Modal); Haptics beim Gießen; gebrandeter Offline-Screen; Splash.
4. `ITSAppUsesNonExemptEncryption=NO`; `NSCameraUsageDescription`/`NSPhotoLibraryUsage-
   Description` de+en; `TARGETED_DEVICE_FAMILY=1` (iPhone-only → nur 6,9"-Screenshots).
5. Privacy-Manifest via aktuellem Capacitor; Build-Basis Xcode 26 / iOS-26-SDK
   (Pflicht seit 28.04.2026).

**Ohne Code (Checkliste/Marius):** Privacy-Labels (Email + Photos + UserID, alle
„linked", kein Tracking), Support-Seite auf getplantpal.com, Review-Notes (invite-only-
Erklärung, Login-Schritte, fester Code, Reserve-Account wegen Lösch-Test-Lockout),
Altersfreigabe 4+ (neuer Fragebogen), **DSA-Trader-Entscheidung** (Hobby → Non-Trader
plausibel; Verifikation dauert → früh erledigen), Option „Unlisted Distribution" für
invite-only bewusst entscheiden, Review-Fenster: Deploy-Freeze + Uptime-Alarm,
Sign-in-with-Apple NICHT nötig (eigenes Auth-System, 4.8-Ausnahme).

## F. Anti-Pattern-Verbotsliste (konsolidiert)

1. Tutorial/Carousel/Coach-Marks jeder Art.
2. Begrüßungs-Prosa-Header / Anrede-Personalisierung.
3. Status als Satz oder an wechselnder Position; Farbe ohne redundanten Kanal.
4. Day-1-„überfällig", Streak-Countdowns, rote Schuld-Färbung säumiger Pflanzen.
5. Task-/Notification-Inflation (eine Tages-Zusammenfassung, nie pro Pflanze).
6. Paywall-/Trial-Patterns, Rabatt-Carousels (haben wir nicht — nie einführen).
7. Pseudo-Pflanzen-ID/-Diagnose ohne Substanz.
8. Sample-Daten im echten Konto.
9. Web-Signale im App-Build (externe Safari-Links, Browser-Lade-UI, `server.url`-Remote).

## Definition der Phase-2-Reihenfolge (Umsetzung)

1. A1–A3 Band-Umbau + Kurz-Status-Vokabular (i18n de+en).
2. B1–B2 Add-Sheet (Foto optional + Progressive Disclosure) inkl. Backend-Check B4.
3. D1 Legal-Links, B5 Login-Code-Prominenz.
4. C1, C3, C4 Stats/Spross-Beruhigung (C2 → Vorschlagsliste).
5. A4–A5 Suche/Sort/Karten-Feinschliff, V2 Hintergrund-Kuration.
6. D2–D5 Vollständigkeit + A11y; Playwright-Vorher/Nachher-Nachweis.
