# Plan — Spross v2: restliche Flächen (P1/P2)

Status: **PLAN** (Review ausstehend → danach Implementierung). Quelle der Specs: der v2-Ultracode-
Design-Workflow (Synthese + Critic). Verifikation-Konvention: **/plan-review (ohne Codex)** vor der
Umsetzung; Codex erst wieder nach der Implementierung pro Milestone.

## Ziel & Scope

Die im v2-Design schon spezifizierten, aber noch nicht gebauten Flächen umsetzen — „der Rest von v2".
**100 % Frontend/CSS, kein neues Backend.** Begründung: Stage/Peak sind seit v2 server-durabel
(`users.vitality_stage_max` / `spross_peak_vitality`); Skins/Meilensteine/Pets/Urlaub leben im
bestehenden `localStorage["pp:spross"]`, dessen Felder v2 bereits angelegt hat. Cross-Device-Sync
dieser Zusatzfelder = **v3, bewusst draußen**.

## Schon vorhandene Basis (nicht neu bauen)

- `frontend/src/sprossState.ts` → `SprossStore` hat bereits ungenutzt: `milestones`, `skins`,
  `activeSkin`, `petCount`, `vacation`. Load/Save/Ratchet existieren.
- `frontend/src/components/Spross.tsx` → Wrapper (Bloom) + inneres Sprite; `onPet` ⇒ `<button>`;
  `reactNonce`/`bloomNonce` (animationName-getrennt).
- `frontend/src/status.ts` → `vitalityScore`, `stageFromVitality`, `STAGE_THRESHOLDS`, `Stage`.
- `PlantdexPage.tsx` → Mood-Band, `['stats']`-Query, Ratchet-Effekt, Server-Sync.
- `App.tsx` → `RouteFocus` (fokussiert erstes `<h1>`), `RequireAuth`; Routen `/stats`, `/settings`.

## Features

### P1.1 — `/spross` Companion-Home (neue Route)
- **Neu** `pages/SprossPage.tsx`, kopiert die StatsPage-Shell (`max-w-md`, `pp-frame`,
  `<h1 tabIndex={-1}>` ⇒ RouteFocus landet sauber).
- `<Route path="/spross">` in `App.tsx`, in `RequireAuth`, neben `/stats`.
- Liest `useQuery(['stats'])` + `loadSprossStore()`.
- Inhalt: großer **dekorativer** `<Spross stage={stageMax} mood={…} skin={activeSkin} size≈140 />`;
  **Text** „Stufe N von 6 · «Name»"; transparente Vitalitäts-Formel mit den **eigenen Zahlen**;
  nächste Schwelle als **statischer** Text („Stufe N+1 ab X Vitalität" — nie „noch Y %/Tage");
  monotoner **Wachstums-Balken** (Breite aus `peakVitality` innerhalb der aktuellen Bande, sinkt nie).
- i18n: 6 Stufennamen (de+en) + Formel-Copy.
- **HARTE REGEL:** nur **ratcheted/peak**-Werte rendern, NIE `live` (post-Lapsus `consistency 40 %`,
  `streak 0` läse sich als „du wurdest schlechter").

### P1.2 — Das Band wird zur Tür
- Plantdex-Mood-Band in `<Link to="/spross">` wrappen; **sichtbarer accessible name = der
  Stufen-Label-Text** (inneres Spross bleibt `aria-hidden`; Joy-Wiggle bleibt). Plus sekundärer
  Header-Nav-`<Link>` „Spross" (neben Stats/Settings/Add).
- 320 px: Greeting-Caption und persistentes Stufen-Label **nicht gleichzeitig** zeigen.

### P1.3 — Trophäen-/Meilenstein-Schrank (Sektion auf `/spross`)
- `sprossState.ts`: `MILESTONES`-Defs + **reine** `detectMilestones(stats, store, plants)`; neu
  erreichte werden mit `berlinToday()` datiert in `store.milestones` geschrieben — **append-only**,
  nie entfernt.
- Gates **nur aus vorhandenen Daten**: `stufe_3/5/6`, `konsistenz_80`, `streak_7/30`,
  `alle_versorgt` (thirsty==0 bei ≥3 Pflanzen), `wiederkehr` (>3-Tage-Gruß), `pflege_100` (Pets).
  KEINE Mengen-Meilensteine („50 Gießungen") — Lifetime-Count braucht v3-Backend.
- Render: CSS-Grid; freigeschaltet = Pixel-Kachel + Datum; gesperrt = graue „?"-Silhouette.
  **KEINE** Fortschrittsbalken, **KEIN** „X/N erledigt".
- Detektion läuft im selben Effekt wie der Ratchet (beide Queries geladen, mount-ref `storeExisted`).

### P1.4 — Skins (CSS-`filter`, 0 neue Assets)
- `Spross.tsx`: `skin?: string` ⇒ `data-skin` aufs **innere Sprite** (NICHT Wrapper/Button → tönt
  weder Bloom-Halo noch Fokus-Ring).
- `index.css`: `.spross[data-skin="…"] { filter: … }` — 3–5 permanente, verdiente, nie-ablaufende
  Skins: `tau-schimmer` `brightness(1.08) saturate(1.25)` @ `stufe_3`|`konsistenz_80`;
  `mondlicht` `hue-rotate(180deg) saturate(0.85) brightness(1.05)` @ `streak_30`;
  `goldblatt` `sepia(0.45) saturate(1.5)` @ `stufe_5`; `pflegegruen` @ `pflege_100`.
  (hue-rotate immer mit saturate gepaart; kein blur; auf allen 6 Sheets + light theme eyeballen.)
- Picker auf `/spross`: 44 px Radio-Gruppe, nur freigeschaltete wählbar, `activeSkin` im Store
  (allow-list-validiert wie `theme`). Vollständig reversibel.
- Plantdex-Band + /spross-Hero rendern `skin={store.activeSkin}`.

### P1.5 — Aufrichten-Animation (Erholung)
- `index.css`: `@keyframes spross-rise` (translateY + leichte Scale, ruht bei 0 % **und** 100 % ⇒
  reduced-motion-safe) + `.spross-rise`.
- `Spross.tsx`: `riseNonce?` analog `reactNonce` (eigener State, `onAnimationEnd` nach `animationName`).
- Plantdex: `riseNonce` bumpen, wenn `thirsty.length` von >0 auf 0 fällt. Liest sich als
  **Erleichterung** — kein Straftimer, so schnell wie der Verfall.

### P2.1 — Tap-to-pet (nur `/spross`-Hero)
- /spross-Hero übergibt `onPet` ⇒ `<button aria-label="Spross">`; Tap ⇒ Wiggle (`reactNonce`) +
  `store.petCount++`. Kein Sound, kein Toast, **nicht** in aria-live, **nie** autofocus. Bei 100 Pets
  ⇒ `pflegegruen`-Skin + `pflege_100`-Trophäe. **Pets geben NIE Vitalität** (sonst Grind-Loop).

### P2.2 — Urlaubs-Modus (Settings-Toggle)
- `SettingsPage.tsx`: Checkbox (bestehende Settings-Row-Optik) ⇒ `store.vacation = {on, since}`.
- Wirkung (ehrlich begrenzt, **kein** Decay-Pause — es gibt keinen Decay; **kein** Tage-Limit):
  (a) Plantdex klemmt Distress-Moods (durstig/welkend → wohl); (b) Welcome-back-Gruß + Aufrichten
  ausgesetzt; (c) ruhiger desaturierter „dormant"-Look (`.spross-rest` static filter); (d) sichtbarer
  **Text** „Urlaubsmodus aktiv" auf /spross (Zustand nicht nur über Farbe).

## Cross-Cutting Guardrails (jede PR muss bestehen)
- Identität (stageMax/skins/milestones/peak) nur max/append; **nie eine sinkende Zahl zeigen**
  (Balken peak-getrieben; kein „% bis nächste", kein Streak-Countdown).
- Unlocks: permanent · deterministisch · nicht-zufällig · nicht-kaufbar · nicht-ablaufend.
- Pull-not-push: 0 Popups/Toasts/Badges; Progression-Events rufen **nie** `announce()`.
- reduced-motion: alle Keyframes ruhen bei 0/100 %; jede dauerhafte Aura ist `static box-shadow`.
- Mascot dekorativ-by-default; stiehlt nie Fokus; alle neuen Controls ≥44 px; Skin-`filter` strikt
  aufs innere Sprite (nie Body-Text/Fokus-Ring/Bloom).

## Tests
- `sprossState.test.ts`: `detectMilestones` (neu-erkannt + append-only + keine Mengen-Meilensteine),
  Skin-allow-list-Validierung, Vacation-Mood-Clamp (rein).
- Komponenten/`status`: rise-nonce one-shot; /spross zeigt Stufenname + **statische** Schwelle.
- Manuell: 320 px (Band-Link-Overflow; Greeting vs. Label nicht gleichzeitig), reduced-motion
  (rise/skins frieren auf normales Sprite), Skin-Filter tönt Fokus-Ring nicht, RouteFocus auf /spross.

## Sequenz (jeweils tsc + vitest + build + eslint/prettier grün)
1. P1.1 `/spross`-Route + Stufenname + statische Formel/Schwelle + Wachstums-Balken
2. P1.2 Band-als-Tür + Header-Link
3. P1.3 Meilensteine (defs + detect + Grid)
4. P1.4 Skins (prop + CSS + Picker)
5. P1.5 Aufrichten
6. P2.1 Tap-to-pet
7. P2.2 Urlaubs-Modus

## Offene Fragen (für den Review / den User)
- Skin-Set/Namen/Gates final? hue-rotate auf der warmgold-Pixel-Identität ästhetisch ok (auf allen
  6 Sheets in dark **und** light)?
- Englische Äquivalente der 6 Stufennamen (Keimling…Urgeist) für i18n?
- Band-als-Link: 4. Header-Link akzeptiert (320 px-Wrap der Nav)?
- `alle_versorgt`-Schwelle bei ≥3 Pflanzen ok?
- Urlaubs-Modus in v2 bauen oder nach v3 schieben (Monotonie macht den Decay-Pause-Teil ohnehin obsolet)?

---

## Plan-Review (ohne Codex) — Findings & Resolutionen

Drei Review-Agenten (Vollständigkeit · Architektur-Fit · Risiko), stark konvergent. Resolutionen
sind verbindlich für die Implementierung:

**R1 (BLOCKER) — /spross-Formel nie mit LIVE-Zahlen.** `consistency_pct`/`streak` sind live und fallen
nach einem Lapsus → gefühlter Rückschritt + sinkende Zahl. **Fix:** /spross zeigt nur
(a) **Peak-Vitalität** (ratcheted, monoton: „Deine Vitalität: 74 (Bestwert)"), (b) **statische**
Schwelle („Nächste Stufe ab 83"), (c) die Formel **in Worten** („Vitalität = Pflege-Qualität ×
Verweildauer"). KEINE live consistency/streak-Zahlen. (Pflanzen-Alter/Tenure ist monoton und darf
gezeigt werden.)

**R2 (HIGH) — Band-als-Link.** Ein `<Link>` um nur `aria-hidden`-Inhalt hat **keinen** accessible
name (WCAG 2.4.4/4.1.2) und Fehltipps über den Gieß-Buttons navigieren weg. **Fix:** ein **sichtbarer
Stufen-Label-Text** („Stufe N · «Name»") ist der Link-Inhalt + dessen accessible name; inneres Sprite
bleibt `aria-hidden`; Tap-Target = das Label (nicht das Sprite neben den Buttons), genug Abstand.

**R3 (HIGH) — Meilenstein-Daten auf neuem Gerät.** Bei Server-Restore (`storeExisted=false`) würde
`detectMilestones` `stufe_3/5` mit `berlinToday()` stempeln (falsches „erstmals erreicht"). **Fix:**
Datierung an `storeExisted` koppeln (Mount-Ref, wie der Bloom-Gate in `sprossState.ts`); server-
implizite Meilensteine ohne Datum seeden, nie auf heute stempeln.

**R4 (Vollständigkeit/Arch) — /spross braucht `['plants']` + Detektions-Ort.** Formel/Tenure/
`alle_versorgt` brauchen `plants`. **Fix:** der Meilenstein-**Write** + Skin-Unlock laufen im
**bestehenden PlantdexPage-Ratchet-Effekt** (hat `plants`+`stats`+`storeExisted`+`greeting`), genau
EIN Store-Objekt, EINMAL gespeichert (kein Clobbering). `/spross` **liest** nur `store.milestones`/
`skins` und lädt zusätzlich `['plants']` für die Anzeige. (Plantdex ist die Einstiegsseite → Reads
sind aktuell.)

**R5 (Arch) — rise NICHT aufs innere Sprite.** Der Wiggle animiert dort schon `transform`. **Fix:**
Aufrichten und Joy-Wiggle sind **pro Gieß-Event gegenseitig exklusiv** (leert das Gießen die
Durstig-Liste → `riseNonce`; sonst → `waterNonce`), beide am inneren Sprite, also keine Kollision.
`@keyframes spross-rise` ruht bei 0 % **und** 100 % (reduced-motion-safe).

**R6 (Arch/Vollständigkeit) — Skin-Validierung + Render-Quelle.** **Fix:** `SKINS`-Registry-Konstante
in `sprossState.ts`; `loadSprossStore` droppt unbekanntes/nicht-freigeschaltetes `activeSkin`
(allow-list wie `detectBackground`/`BACKGROUNDS` in `theme.tsx`). Skin-`filter` aufs **innere**
Sprite (tönt weder Bloom-Halo noch Fokus-Ring — bestätigt). /spross-Hero rendert
`stage = max(store.stageMax, stats.vitality_stage_max)`.

**R7 (Vollständigkeit) — Wachstumsbalken-Mathe.** **Fix:** Füllung = `clamp((peak − bandStart) /
(bandEnd − bandStart), 0, 1)`; bei Stufe 6 (keine nächste Schwelle) **voller** Balken + „max. Stufe",
kein „nächste ab". Unterlauf vermeiden, wenn `stageMax` (server/tenure-gefloort) > Peak-Bande →
clamp 0.

**R8 (Vollständigkeit) — Leerzustand /spross.** 0 Pflanzen / `null`-Store → Keimling-Hero + ruhiger
Hinweis (kein Crash), analog StatsPage-Empty-Branch.

**R9 (Risiko/MEDIUM) — Urlaubs-Modus `.spross-rest` vs `data-skin`.** **Fix:** im Urlaub gewinnt der
ruhige `desaturate`-Look (Skin-Filter ausgesetzt, Zustand zusätzlich als Text).

**Offen für den User (echte Produkt-Entscheidungen):** EN-Stufennamen; Skin-Set/Ästhetik
(hue-rotate auf warmgold?); Band-als-Link vs. nur Header-Link; Urlaubs-Modus in v2 oder v3.
