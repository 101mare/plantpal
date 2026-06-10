# Asset-Prompts (ChatGPT Image) — App Store & App

> Workflow wie gehabt: Du generierst mit ChatGPT Image, postest die Bilder in den Chat,
> die Einbau-Pipeline (`scripts/build_sprites.py`-Muster) übernimmt Freistellen/Skalieren.
> **Ausnahme App-Icon:** KEIN Magenta-Hintergrund — iOS-Icons müssen vollflächig und ohne
> Transparenz sein (Alpha führt zu Upload-Fehler ITMS-90717).

---

## 1. App-Icon 1024×1024 (Pflicht für die Einreichung)

**Prompt:**

> Square app icon, 1024x1024, retro pixel art. A cheerful tiny sprout mascot („Spross")
> with a round light-green head, two leaf sprigs on top and rosy cheeks, sitting in a
> terracotta clay pot, rendered in chunky 8-bit pixel-art style with crisp pixel edges
> (no anti-aliasing, no outlines bleeding). Centered, filling about 70% of the canvas.
> Background: solid deep forest green (#0d2018) with a very subtle darker pixel-art vine
> pattern in the corners. Warm gold (#e0b53d) pixel rim light on the pot. Flat colors,
> high contrast, joyful, charming. NO text, NO transparency, full-bleed square,
> no rounded corners (iOS rounds automatically).

Ableitung des Icon-Sets (alle Größen) übernimmt Xcode aus der 1024er („Single Size").
**Check nach Generierung:** Motiv erkennbar bei 60 px? (Daumenregel: zukneifen.)

## 2. Launch Screen / Splash (Capacitor)

Kein Bild nötig als MVP: dunkelgrüner Vollton (#0d2018) ist konfiguriert und HIG-konform
(Launch ≈ erste App-Ansicht, kein Branding-Moment). Optional fürs Polishing:

**Prompt (optional, zentriertes Splash-Motiv):**

> Pixel-art sprite of the same tiny sprout mascot in a terracotta pot, 512x512, chunky
> 8-bit style, crisp pixel edges, centered on a SOLID MAGENTA (#FF00FF) background for
> chroma-key cutout. The mascot looks calm and welcoming. No text, no shadow.

→ wird freigestellt und in `ios/App/App/Assets.xcassets/Splash.imageset` gelegt
(zentriert auf #0d2018; Anleitung in der Submission-Checkliste).

## 3. App-Store-Screenshots (6,9", 1290×2796 — die einzig nötige Größe)

**Keine KI-Bilder** — Apple 2.3.3 verlangt echte App-Ansichten. Plan (5 Stück, auf dem
Mac-Simulator „iPhone 16 Pro Max" aufnehmen, de-Locale):

| # | Inhalt | Vorbereitung |
|---|---|---|
| 1 | Plantdex mit Band „3 durstig" + Karten | Demo-Daten wie Review-Account |
| 2 | Gieß-Moment: Zeile mit ✓-Morph | direkt nach Tap aufnehmen |
| 3 | Spross-Seite (Maskottchen + Vitalität + Trophäen) | Stage ≥3 Account |
| 4 | Statistik (ruhige Kacheln) | gefüllte Historie |
| 5 | Pflanze + (Schnell-Anlage, „optional Foto") | leeres Sheet |

Optional dekorativer Rahmen/Caption später — fürs erste Review reichen klare,
ungerahmte Screenshots.

## 4. Künftige In-App-Icons (nur bei Bedarf)

Das PixelIcon-SVG-Set (drop/check/trash/camera/lock/trophy/bars) deckt die UI ab —
**keine Generierung nötig.** Falls je ein neues Icon gebraucht wird: 8×8-Raster im
gleichen SVG-Stil ergänzen statt Bilder generieren (konsistent + themeable).
