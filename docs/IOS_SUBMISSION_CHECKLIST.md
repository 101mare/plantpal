# iOS-Submission-Checkliste (PlantPal → App Store)

> Stand 2026-06-10 (Journey Phase 5). Was auf Linux ging, ist FERTIG ✅; der Rest ist die
> **Erste-Mac-Session** (§2) + App Store Connect (§3). Grundlagen: `IOS_APP_STORE.md`
> (Deep-Research), `UX_RESEARCH_PRODUCTION.md` §E (Review-Praxis 2026).

## 1. Bereits erledigt ✅ (im Repo, Branch production-ready)

- **Capacitor-7-Gerüst**: `frontend/ios/` (appId `com.getplantpal.app`, Name „PlantPal"),
  `capacitor.config.ts` mit **gebündeltem** webDir (kein `server.url` → 2.5.2 self-contained).
- **Info.plist**: `NSCameraUsageDescription` + `NSPhotoLibraryUsageDescription` (en default,
  de via `de.lproj/InfoPlist.strings`), `ITSAppUsesNonExemptEncryption=false`
  (Export-Compliance-Frage entfällt), **Portrait-only**.
- **iPhone-only**: `TARGETED_DEVICE_FAMILY = 1` → nur 6,9"-Screenshots nötig, keine
  iPad-Layout-Review-Falle.
- **API-Base-Schalter**: `VITE_API_BASE` in `frontend/src/api.ts` — Web-Build unverändert
  (same-origin), iOS-Build zeigt auf `https://getplantpal.com`.
- **Review-Account-Mechanik** (Guideline 2.1, Magic-Link-Problem): Backend akzeptiert für
  konfigurierte E-Mail(s) — Komma-Liste, Haupt- + Reserve-Account — einen festen
  6-stelligen Code (`REVIEW_ACCOUNT_EMAIL` + `REVIEW_LOGIN_CODE`), optional
  selbst-deaktivierend via `REVIEW_CODE_EXPIRES_AT`. Format wird beim Boot validiert
  (fail-fast statt stillem 422 im Review-Fenster). Wiederholbar, generische Fehler.
- **Native-Shell-Auth KOMPLETT gelöst (Bearer)**: `/auth/verify-code` mit `client:"app"`
  liefert den Session-Token im Body; die Shell sendet `Authorization: Bearer` (CSRF-immun,
  keine Cookie-/SameSite-Probleme), `ALLOWED_APP_ORIGINS=capacitor://localhost` schaltet
  Origin-Allowlist + CORS frei. End-to-end mit PROD-Settings getestet
  (tests/test_app_shell_auth.py) — der frühere „Cookie-Check im Simulator" entfällt.
- **Bild-URLs Shell-fest**: `assetUrl()` präfixt `plant.image_url` in allen drei
  <img>-Stellen mit `VITE_API_BASE` (Web-Build byte-identisch).
- **In-App-Pflichten**: Account-Löschung in Settings ✅, Datenschutz/Impressum in-App
  erreichbar ✅ (Settings-Footer), Code-Login prominent ✅.

## 2. Erste-Mac-Session (Schritt für Schritt, ~1–2 h)

> Voraussetzung: Mac mit **Xcode 26** (Pflicht-SDK seit 28.04.2026) + Homebrew.
> Apple-Developer-Account ist erst ab §2.6 (Signing) nötig — bauen + Simulator gehen ohne.

```bash
# 0) Werkzeuge
xcode-select --install               # falls frisch
brew install cocoapods node@22

# 1) Repo + Abhängigkeiten
git clone git@github.com:101mare/plantpal.git && cd plantpal/frontend
npm ci
# Capacitor 8 erfordert Node 22 (auf dem Linux-Rechner lief 7 mit Node 20):
npm i -E @capacitor/core@latest @capacitor/ios@latest && npm i -DE @capacitor/cli@latest

# 2) iOS-Build des Frontends (API zeigt auf den Pi/Cloudflare)
VITE_API_BASE=https://getplantpal.com npm run build
npx cap sync ios                     # kopiert dist + pod install (jetzt mit CocoaPods)

# 3) Öffnen + erster Lauf
npx cap open ios                     # Xcode: Simulator "iPhone 16 Pro Max" → ▶
```

**Im ersten Simulator-Lauf testen (Reihenfolge!):**
1. App lädt das **gebündelte** Frontend (kein weißer Flash → `backgroundColor` greift).
2. Login-Seite → **„Code eingeben"** → Review-Code-Flow gegen getplantpal.com.
   Die Shell authentifiziert via **Bearer-Token** (implementiert + prod-getestet):
   Voraussetzung serverseitig nur `ALLOWED_APP_ORIGINS=capacitor://localhost` in der
   Pi-`.env`. Kein Cookie-/SameSite-Gamble mehr.
   ⚠️ **Bekannte v1-Einschränkung Pflanzenfotos in der Shell:** `<img>`-Requests tragen
   keinen Authorization-Header → geschützte Fotos fallen still auf den Platzhalter
   zurück. Im Simulator prüfen; falls Fotos für v1 gewünscht: kleines `<AuthedImage>`,
   das das Bild per `request()` lädt und als blob:-URL setzt (Skizze im Verify-Report),
   ODER signierte Kurzzeit-Tokens in der Bild-URL. Bewusste Mac-Session-Entscheidung.
3. Pflanze anlegen (Kamera-Prompt → deutscher Purpose-String?), gießen, Spross, Stats.
4. Safe Areas auf Notch-Gerät; Dark/Light; reduced motion (Einstellungen → Bedienungshilfen).

**4) Native Mehrwerte für 4.2 einbauen (Reihenfolge nach Wirkung):**

```bash
npm i @capacitor/local-notifications @capacitor/haptics @capacitor/splash-screen
npx cap sync ios
```
- **Local Notifications** (stärkstes Argument, kein Server nötig): täglicher stiller
  Reminder „X Pflanzen sind durstig" — Scheduling beim App-Start aus den lokalen Daten;
  Priming NACH dem ersten Gießen als Inline-Karte (kein Modal! Eisenregel), Opt-out in
  Settings. Erst System-Prompt, wenn der Nutzer die Inline-Karte bejaht.
- **Haptics**: 1 Zeile beim Gieß-Erfolg (`Haptics.impact({style: Light})`) im
  `water.onSuccess` — nur `if (Capacitor.isNativePlatform())`.
- **Splash**: dunkelgrün + zentriertes Spross-Asset (aus `ASSET_PROMPTS.md` §2).
- Offline-Zustand: vorhandener ErrorState mit Retry ist gebrandet ✅ — im Flugmodus prüfen.

**5) App-Icon**: 1024er aus `ASSET_PROMPTS.md` §1 → Xcode Assets „AppIcon" (Single Size).

**6) Signing & TestFlight** (ab hier Apple-Account, 99 €/Jahr):
Xcode → Target App → Signing: Team wählen, Bundle-ID `com.getplantpal.app` registrieren →
Product → Archive → Distribute → TestFlight. Auf dem EIGENEN iPhone den kompletten Flow
testen (inkl. Account-Löschung + Re-Invite!).

## 3. App Store Connect (Formulare, ~1 h + DSA-Vorlauf!)

| Feld | Wert |
|---|---|
| **Privacy Labels** | Contact Info → Email (linked, App Functionality); User Content → Photos (linked, App Functionality); Identifiers → User ID (linked, App Functionality). **Kein** Tracking, keine Diagnostics. Ergebnis: „Data Linked to You". |
| **Altersfreigabe** | Neuer Fragebogen (2025) ehrlich ausfüllen → erwartbar **4+**; Wellness/Medizin = Nein. |
| **DSA-Trader-Status** | **Früh entscheiden** (Verifikation dauert Tage!): Hobby ohne Einnahmen → Non-Trader plausibel (keine öffentliche Adresse im Store; Impressum in der App bleibt davon unberührt). Bei Zweifel kurze Rechtsberatung. |
| **Support-URL** | `https://getplantpal.com/impressum` reicht NICHT als Support-Seite — kleine Kontakt/FAQ-Seite anlegen (kann eine statische Route der SPA sein). |
| **Privacy-Policy-URL** | `https://getplantpal.com/datenschutz` ✅ (in-App-Link existiert). |
| **Kategorie** | Lifestyle (primär), Utilities (sekundär). |
| **Beschreibung** | Kernversprechen aus dem Konkurrenz-Research: *ruhig, ehrlich kostenlos, kein Abo, keine Werbung, kein Schuld-Nagging — in 30 Sekunden wissen, wer Wasser braucht; Pokédex-Sammelfreude mit Spross.* |

**Review Notes (Vorlage):**

> PlantPal is a calm, subscription-free plant-watering tracker. Accounts are
> invitation-based (family & friends); sign-in is passwordless via email code.
> **Review account:** email `review@getplantpal.com` — on the sign-in screen choose
> "Enter code" and use the permanent code `<REVIEW_LOGIN_CODE aus .env>`. The account is
> pre-filled with demo plants. If you test account deletion, a second review account is
> available: `review2@getplantpal.com`, same code. Self-hosted backend at
> https://getplantpal.com (IPv6 via Cloudflare). Account deletion: Settings → red zone.
> Privacy policy & legal notice: Settings footer.

**Vor dem Submit:**
- [ ] Review-Accounts anlegen + befüllen — als **normale User, NICHT admin** (ein
      erratener Code darf nie Admin-Rechte geben): `create-invite` → mit
      `review@getplantpal.com` und `review2@getplantpal.com` registrieren, je 5–6
      Pflanzen mit Fotos, 2 durstig, etwas Historie.
- [ ] `.env` auf dem Pi: `REVIEW_ACCOUNT_EMAIL=review@…,review2@…` +
      `REVIEW_LOGIN_CODE` (6 Ziffern) + `REVIEW_CODE_EXPIRES_AT` (~4 Wochen) setzen,
      deployen.
- [ ] **Nach dem Review:** alle drei `REVIEW_*`-Werte leeren, deployen, Review-Accounts
      löschen — der feste Code darf das Review-Fenster nicht überleben.
- [ ] **Deploy-Freeze + Uptime-Alarm** fürs Review-Fenster (90 % der Reviews < 24 h).
- [ ] Impressum-Platzhalter ersetzt (User-TODO #5!) — sonst sichere Ablehnung/Abmahnrisiko.
- [ ] Screenshots nach Plan (`ASSET_PROMPTS.md` §3).

## 4. Bewusst NICHT in v1

- APNs-Server-Push (Local Notifications decken den Gieß-Reminder; Push später als Update).
- Sign in with Apple (4.8-Ausnahme: eigenes Auth-System — kein Zwang).
- OTA-/Live-Updates (2.5.2-Risiko; Updates klassisch über Store-Releases).
- iPad-Support (Family 1; später bewusste Entscheidung).
