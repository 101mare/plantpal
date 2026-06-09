# PlantPal — Projekt-Instruktionen

## Strategische Design-Direktive (höchste Priorität)
- **Primärfokus: iPhone-/Handy-Design.** Jede UI-/UX-Entscheidung wird ZUERST fürs Smartphone
  (iPhone) getroffen; Desktop/Tablet sind sekundär. Nicht „auch mobil", sondern „iPhone zuerst".
- **Ziel: Veröffentlichung im Apple iOS App Store.** Design UND Architektur arbeiten darauf hin.
  Fortlaufend beachten:
  - Apple Human Interface Guidelines (HIG): native-anmutende Muster, klare Hierarchie, keine
    „Website-im-Wrapper"-Anmutung. iOS-Navigation (Tab-Bar/Toolbar) gegenüber Web-Mustern bevorzugen.
  - Safe Areas (Notch / Dynamic Island / Home-Indicator), Touch-Targets ≥ 44 pt, Dynamic Type,
    Dark Mode, prefers-reduced-motion.
  - Web-/Browser-typische Muster vermeiden, die auf iOS fremd wirken (Pull-to-refresh-Konflikte,
    Hover-only-UI, Browser-Zurück-Annahmen).
  - App-Store-Assets im Blick behalten (App-Icon 1024 px + Set, Launch Screen, Screenshots je
    Gerätegröße, Privacy-Labels).
- **Offene Architektur-Frage:** PlantPal ist aktuell eine PWA mit self-hosted FastAPI-Backend.
  Der iOS-App-Store-Weg (Wrapper vs. nativ, gehostetes vs. self-hosted Backend, Apple-Review
  4.2 „Minimum Functionality") wird recherchiert → Ergebnis + Entscheidung in
  `docs/IOS_APP_STORE.md` (wird aus der Deep-Research gefüllt).

## Eiserne UI-Regeln (gelten weiter)
- KEINE Popups/Toasts/Modals außer den bestehenden Backdrop-Sheets. Erfolg ist still (+ aria-live
  `announce()`), Fehler erscheinen inline, Löschen ist eine Undo-Kachel, globale Zustände als Banner.
- „Mirror, not judge": kein Nagging / Schuld / Streak-Countdown / Verknappung / Leaderboards.
- Spross-Maskottchen ist dekorativ (`aria-hidden`) und stiehlt nie den Fokus.
- warmgold Pixel-Art-Look (Tokens in `frontend/src/index.css`). i18n ZWEISPRACHIG de + en
  (`frontend/src/i18n.tsx`) — jeder neue Key in beiden Blöcken.

## Tech & Verifikation
- Frontend: Vite + React + TS + Tailwind v4 (`frontend/`). Backend: FastAPI + SQLite, self-hosted
  (`src/plantpal/`).
- Vor jedem Commit grün halten:
  - Frontend: `cd frontend && npx tsc --noEmit && npx eslint src/ && npx vitest run && npx vite build`
  - Backend: `.venv/bin/python -m pytest`
- Commit/Push nur auf Anweisung. Projekt-Historie & Entscheidungen: Auto-Memory `MEMORY.md`.
