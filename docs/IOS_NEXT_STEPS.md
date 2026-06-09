# PlantPal → iOS App Store: nächster Schritt (Roadmap)

> Stand: das **Web-Frontend** ist iOS-konform (native-anmutende Tab-Bar, Safe-Areas, overscroll,
> 44 pt, Pixel-Art, Instagram-Navigation). Dieser Strang ist die **native Verpackung + Einreichung**.
> Grundlage: `docs/IOS_APP_STORE.md` (Deep-Research). Empfohlener Weg: **Capacitor**.

## Phase 0 — Voraussetzungen (einmalig)
- [ ] **Apple Developer Program** (Individual, 99 USD/Jahr) anlegen.
- [ ] Build-Umgebung: **Mac + Xcode** *oder* Mac-los über **Codemagic / EAS / Capawesome Cloud**.
- [ ] Entscheidung „gehostetes Default-Backend vs. self-host" treffen (siehe Phase 3) — blockiert sonst die Review.

## Phase 1 — Capacitor in das bestehende Vite-Projekt integrieren
- [ ] `npm i @capacitor/core @capacitor/cli @capacitor/ios`
- [ ] `npx cap init PlantPal app.plantpal.www --web-dir=frontend/dist`
- [ ] `npm run build` (Vite) → `npx cap add ios` → `npx cap sync`
- [ ] iOS-Projekt in Xcode öffnen (`npx cap open ios`), erster Simulator-Lauf.
- [ ] Server-Config: für die App das **gehostete** Backend als `server.url`/API-Base (nicht der private Pi).
- Hinweis: Service-Worker/PWA-Caching im WKWebView prüfen (Capacitor liefert das Web-Bundle lokal aus —
  der SW ist dann teils redundant; Asset-Caching ggf. Capacitor überlassen).

## Phase 2 — Native Features (Pflicht für Guideline 4.2 „Minimum Functionality")
Mind. **3–4 sichtbar nutzbare** native Features, sonst Ablehnung als „nur ein Web-Wrapper":
- [ ] **Push-Notifications** via `@capacitor/push-notifications` (APNs) — Gieß-Erinnerungen als echter
      nativer Push (stärkstes 4.2-Argument; PWA-Push ist auf iOS eingeschränkt). Braucht APNs-Key + Backend-Versand.
- [ ] **Local Notifications** `@capacitor/local-notifications` — Offline-Reminder „Pflanze X heute gießen".
- [ ] **Haptics** `@capacitor/haptics` — kurzer Impuls beim Gießen/Level-up (kleiner Aufwand, großer „nativ"-Eindruck).
- [ ] **Offline-Fallback-Screen** (kein Browser-Fehler) — eigener Retry-Screen bei fehlender Verbindung.
- [ ] *(optional)* **Face-ID-Login** `@capacitor/biometrics` — zeigt OS-Integration.
- [ ] **Gebrandeter Splash** `@capacitor/splash-screen` — spiegelt die erste App-Ansicht (kein Logo-auf-Weiß).
- Die bereits gebaute Tab-Bar zählt als native-anmutende Navigation; ggf. später echte `UITabBar` erwägen.

## Phase 3 — Backend-Strategie (KRITISCH für die Review)
Apple-Reviewer erreichen keinen privaten Pi/Cloudflare-Tunnel.
- [ ] **Gehostetes Demo/Default-Backend** deployen (Railway/Render/Fly.io/VPS, ~5 USD/Mon.) mit vorgefüllten Demo-Daten.
- [ ] **Server-URL-Option** in den Einstellungen (Bitwarden-Modell): Default = gehostet, frei konfigurierbar für Self-Hoster.
- [ ] **Demo-Account** anlegen (Invite-only!) und in App Store Connect → „App Review Information" eintragen
      (Login + Hinweis „Backend ist live unter …; Self-Hosting ist optional").

## Phase 4 — Assets & Compliance
- [ ] **App-Icon** 1024×1024 (kein Alpha/keine runden Ecken) — Pixel-Art bei 40 px testen, ggf. vereinfachte Kleinversion.
- [ ] **Launch Screen** = erste App-Ansicht (kein reines Logo-Splash).
- [ ] **Screenshots** 6.9″ iPhone (1290×2796) Pflicht.
- [ ] **Privacy Policy** (URL in App Store Connect + in der App verlinkt) + **Privacy Nutrition Label**
      (E-Mail = Auth/Linked; Pflanzendaten = User Content/Linked; **kein** Tracking).
- [x] **In-App-Account-Löschung** — bereits vorhanden (Settings → Account löschen, echte Löschung).
- [x] **Kein „Sign in with Apple" nötig** (eigener Magic-Link-Auth).

## Phase 5 — Build, Signing, TestFlight, Einreichung
- [ ] Signing/Provisioning (automatisch via Xcode oder Fastlane/Codemagic).
- [ ] Release-Build → **TestFlight** (interner Test auf echtem iPhone — besonders Push, Safe-Areas, Haptik, Pixel-Art @3×).
- [ ] App Store Connect: Metadaten, Screenshots, Privacy Label, **Review Notes** (Demo-Account!).
- [ ] Einreichen → Review. Bei 4.2-Ablehnung: native Features nachschärfen (Phase 2).

## Offene Entscheidungen (für später, vom Nutzer)
1. **Backend-Modell:** rein gehostet, hybrid (Default gehostet + Self-Host-Option), oder self-host-first mit Review-Demo?
2. **Push-Infrastruktur:** APNs-Versand im FastAPI-Backend (zusätzlicher Dienst/Key-Management).
3. **Liquid Glass (ab iOS 27 Pflicht):** Pixel-Art-Retro bewusst als Stil halten vs. native Chrome anpassen.
4. **Langfrist:** bei Erfolg schrittweise Richtung React Native für ein voll-natives Erlebnis (Widgets, Share Extensions).

## Empfohlene Reihenfolge
**Phase 3-Entscheidung zuerst** (Backend blockiert die Review) → Capacitor-Grundgerüst (Phase 1) →
Local Notifications + Haptik als schnelle 4.2-Gewinne → Demo-Backend + Assets → TestFlight → Push → Einreichung.
