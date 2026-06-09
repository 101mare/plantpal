# PlantPal → Apple iOS App Store (Deep-Research, Stand Juni 2026)

> Referenz für das App-Store-Ziel (siehe `CLAUDE.md`). Quellen unten; basiert auf offiziellen
> Apple-Docs, Capacitor/Tauri-Docs und mehreren unabhängigen Praxis-Quellen (2025/2026).

## Kurz-Fazit
Empfohlener Weg: **Capacitor (WKWebView + native Shell)** mit *bewusst* hinzugefügten nativen
Features. Die Vite+React-Codebasis bleibt zu ~85 % erhalten; Capacitor liefert den nativen Wrapper,
in den Push, native Navigation und Offline-Handling als Plugins kommen — genau die Features, die
einen Wrapper für Apple „nativ genug" machen.

Größte Risiken:
1. **Guideline 4.2 (Minimum Functionality)** — ein bloßer WebView-Wrapper ohne native Features wird
   sehr wahrscheinlich abgelehnt.
2. **Self-hosted-Backend** — Apple-Reviewer erreichen keinen privaten Pi/Cloudflare-Tunnel → es
   braucht ein öffentlich erreichbares Demo-Backend mit Demo-Account für die Review.
3. **Account-Löschung in-App** (Pflicht seit 2022) — muss echte Datenlöschung sein. *(Haben wir
   bereits: Settings → Account löschen mit Tippen-zum-Bestätigen + DELETE.)*
4. **iOS 26 „Liquid Glass"** (Juni 2025), ab **iOS 27 (Sept 2026) verpflichtend** — native UI erbt es
   automatisch, WebView nicht. Pixel-Art-Retro kann hier bewusst als Stil-Feature stehen.

## Distributionswege (Vergleich)
| Kriterium | Capacitor | PWABuilder iOS | Tauri 2 Mobile | DIY WKWebView | React Native/Expo |
|---|---|---|---|---|---|
| Reife 2025/26 | produktionsreif | rudimentär | stabil, Plugins dünn | viel Aufwand | Industrie-Standard |
| Code-Reuse | ~85 % | ~80 % | ~75 % | ~70 % | ~30-40 % |
| Native Features | Plugins (Push, Notif, Kamera, Biometrie, Haptik) | keine | wenige Mobile-Plugins | null | voll nativ |
| 4.2-Durchkommen | gut (mit nativer Tab-Bar+Push+Offline) | riskant | mittel | gut (mit Native-Layer) | bestmöglich |
| Mac/Xcode nötig? | ja (oder Codemagic/EAS) | ja | ja | ja | ja (oder EAS) |
| Empfehlung PlantPal | ✅ **PRIMÄR** | ❌ | ⚠️ | ⚠️ | ✅ langfristig |

→ **Capacitor** als realistischer Einstieg; bei Erfolg in 12-18 Mon. schrittweise Richtung React Native.

## Checkliste „Was wird gebraucht"
- **Apple Developer Program**: 99 USD/Jahr.
- **Mac + Xcode** empfohlen, aber nicht zwingend (Codemagic / Capawesome Cloud / EAS Build als
  Mac-lose Alternativen, ~2-10 USD/Build).
- **App-Icon** 1024×1024 PNG, *kein* Alpha, *keine* runden Ecken (kleine Größen testen — Pixel-Art
  ggf. vereinfachen, damit es bei 40px @2x lesbar bleibt).
- **Launch Screen** muss die erste App-Ansicht spiegeln (reines Logo-Splash wird abgelehnt).
- **Screenshots**: 6.9″ iPhone (1290×2796) Pflicht; skaliert auf andere Größen.
- **Privacy Policy** (URL in App Store Connect + in der App verlinkt) + **Privacy Nutrition Label**
  (E-Mail = Auth/Linked; Pflanzendaten = User Content/Linked; *kein* Tracking).
- **In-App Account-Löschung** (vorhanden). **Kein** „Sign in with Apple" nötig (eigener Magic-Link-Auth).
- **Demo-Backend + Demo-Account** für die Review (Invite-only ⇒ Reviewer braucht Zugang).

## Kritische Review-Hürden (Wrapper + self-hosted) & Entschärfung
- **4.2 Minimum Functionality (HOCH):** mind. 3-4 *sichtbar nutzbare* native Features einbauen —
  **native Tab-Bar** (kein HTML/CSS-Tab), **Push via APNs** (Gieß-Erinnerungen, stärkstes Argument),
  **Local Notifications**, **Offline-Fallback-Screen** (keine Browser-Fehlerseite), optional Face-ID-Login,
  **Haptik** beim Gießen, gebrandeter Splash.
- **Self-hosted (HOCH/Blocker):** gehostetes Demo-Backend (Railway/Render/Fly.io, ~5 USD/Mon.) mit
  vorgefüllten Demo-Daten; Demo-Login + Erklärung in den „App Review Notes". Muster: Bitwarden
  (Standard = gehostet, Server-URL für Self-Hoster konfigurierbar).
- **Account-Löschung (MITTEL):** erfüllt; echte Löschung, nicht nur Deaktivierung.
- **Invite-only (MITTEL):** Reviewer-Demo-Account oder Reviewer-Invite-Token in den Notes.

## Design-Direktiven fürs Frontend (iOS-Pflicht ab jetzt)
- **Navigation:** native-anmutende **Tab-Bar** (max 5) statt Web-Nav/Hamburger; **iOS-Swipe-Back nicht
  überschreiben**; eigene CSS-Modals durch System-/Sheet-Muster ersetzen wo möglich.
- **Kein Pull-to-Refresh-Konflikt:** `overscroll-behavior-y: none` (sonst triggert iOS den Seiten-Refresh).
- **Touch & Layout:** ≥ 44 pt Targets; Safe Areas überall (`env(safe-area-inset-*)`), Bottom-Nav über
  dem Home-Indicator; Dynamic-Island/Notch respektieren.
- **Dark Mode:** vollständig unterstützen *oder* explizit nur Light (kein halber Dark-Mode mit weißen Flächen).
- **Pixel-Art:** `image-rendering: pixelated` (nicht `crisp-edges`); Sprites in **3×** Basisauflösung
  exportieren für scharfe Retina-Darstellung; Stil selbst ist Apple-konform.
- **Anti-Patterns vermeiden:** `:hover`-only-UI → `:active`; `window.alert()` → native/Sheet; Browser-
  Scroll-/Navigationsannahmen.

## Quellen (Auswahl, Stand Juni 2026)
- Apple: [App Store Review Guidelines](https://developer.apple.com/app-store/review/guidelines/) ·
  [App Privacy Details](https://developer.apple.com/app-store/app-privacy-details/) ·
  [Account Deletion](https://developer.apple.com/support/offering-account-deletion-in-your-app/) ·
  [Program Inclusions](https://developer.apple.com/programs/whats-included/) ·
  [Screenshot Specs](https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications/) ·
  [Liquid Glass](https://www.apple.com/newsroom/2025/06/apple-introduces-a-delightful-and-elegant-new-software-design/)
- Tools: [Capacitor](https://capacitorjs.com/docs) · [PWABuilder iOS](https://github.com/pwa-builder/pwabuilder-ios-app-store) ·
  [Tauri 2 App Store](https://v2.tauri.app/distribute/app-store/) · [Codemagic (ohne Mac)](https://codemagic.io/build-ios-without-mac/) ·
  [Capawesome (ohne Mac)](https://capawesome.io/blog/how-to-build-and-deploy-ios-apps-without-a-mac/)
- Praxis: [MobiLoud PWA→App Store](https://www.mobiloud.com/blog/publishing-pwa-app-store) ·
  [MobiLoud WebView-Wrapper-Guidelines](https://www.mobiloud.com/blog/app-store-review-guidelines-webview-wrapper) ·
  [4.2-Rejection-Fix](https://iossubmissionguide.com/guideline-4-2-minimum-functionality/) ·
  [Liquid Glass ab iOS 27 Pflicht](https://appleinsider.com/articles/26/03/26/stop-holding-out-hope-liquid-glass-will-be-mandatory-in-ios-27)

## Konsequenz für die laufende Arbeit
Das Web-Frontend wird **jetzt** iOS-konform optimiert (Tab-Bar, Safe-Areas, overscroll, 44 pt,
Pixel-Art @3×, keine Web-Anti-Patterns) — so, dass die spätere Capacitor-Verpackung + native Features
(Push, Demo-Backend, App-Store-Assets) sauber andocken. Capacitor/Deployment ist ein eigener Strang.
