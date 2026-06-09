#!/usr/bin/env python3
"""Baut Spross-Mascot-Sprite-Sheets aus einzelnen (KI-generierten) PNGs.

Loest zwei Probleme automatisch, die Gemini/ChatGPT-Exporte mitbringen:
  1. Hintergrund entfernen  - die Modelle malen oft ein helles Schachbrett statt
     echter Transparenz. Wird global (hell + entsaettigt) entfernt; eingeschlossene
     helle Flaechen (Augen-Weiss) werden per Fenster-Mehrheit wiederhergestellt.
  2. Normalisieren + montieren - alle Frames auf gleiche, quadratische Zellengroesse
     bringen, an der Topf-Grundlinie unten ausrichten, horizontal aneinanderreihen.

Abhaengigkeiten: Pillow + numpy (System-Python). Kein scipy noetig.

CLI
---
  python scripts/build_sprites.py all
      Baut aus den aktuellen Downloads das Stage-2-Mood-Sheet, gereinigte Basis-PNGs
      je Stufe und die Evolutions-Uebersicht.

  python scripts/build_sprites.py stage <N> <wohl> <bluehend> <durstig> <welkend> <neugierig>
      Baut frontend/public/sprites/spross-stage<N>.png aus 5 PNGs (Pfade in genau
      dieser Reihenfolge). So baust du eine einzelne Stufe gezielt.

  python scripts/build_sprites.py folder [<dir>]   (default: ~/Downloads)
      Baut ALLE Stufen-Sheets auf einmal. Benennt deine Mood-Bilder nach dem Schema
      stage<N>-<mood>.png  (mood = bluehend|durstig|welkend|neugierig), z. B.
      stage3-welkend.png. ``wohl`` = brand/mascot/clean/stage<N>-base.png (automatisch).
      Fuer jede Stufe mit allen 4 Moods wird ein Sheet gebaut; fehlende werden gemeldet.

  python scripts/build_sprites.py anim <name> <cols> <rows> <img>
      Schneidet ein cols x rows Raster (ChatGPT-Grid/Streifen, Magenta-BG) zeilen-major in ein
      Sheet frontend/public/sprites/spross-anim-<name>.png (cols*rows Zellen a 256px, fuer steps()).
      Bsp: Freudewackeln 2x2 -> `anim freude 2 2 bild.png`; Aufrichter -> `anim aufrichter 3 1 …`;
      Bloom 2x3 -> `anim bloom 3 2 …`.

  python scripts/build_sprites.py clean <in.png> <out.png>
      Entfernt nur den Hintergrund einer einzelnen Datei (freigestellt -> RGBA).

Frame-Reihenfolge im Sheet: 0 wohl | 1 bluehend | 2 durstig | 3 welkend | 4 neugierig
"""
from __future__ import annotations
import glob
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPRITES_DIR = os.path.join(ROOT, "frontend", "public", "sprites")
MASCOT_HIRES = os.path.join(ROOT, "brand", "mascot", "plantpal-mascot-a.png")  # 2048px, scharfe Augen
MOOD_ORDER = ["wohl", "bluehend", "durstig", "welkend", "neugierig"]
# v2 skins: hue-shift (deg) applied ONLY to the green character+leaves; pot/cheeks/eyes/gold stay.
# Tuned so each NAME matches its resulting colour (base leaf-green ~90°): tau=teal, mondlicht=blue,
# amethyst=violet, beere=magenta/berry, koralle=coral — an even spread around the wheel, off green.
SKIN_RECOLOR = {"tau": 95, "mondlicht": 150, "amethyst": 185, "beere": 215, "koralle": -80}


# --- Kern: Hintergrund-Entfernung ------------------------------------------

def _opaque_fraction(opaque: np.ndarray, r: int) -> np.ndarray:
    """Anteil opaker Pixel in einem (2r+1)^2-Fenster, via Integralbild (scipy-frei)."""
    h, w = opaque.shape
    ii = np.zeros((h + 1, w + 1), dtype=np.int32)
    ii[1:, 1:] = np.cumsum(np.cumsum(opaque.astype(np.int32), 0), 1)
    ys = np.arange(h)
    xs = np.arange(w)
    y0, y1 = np.clip(ys - r, 0, h), np.clip(ys + r + 1, 0, h)
    x0, x1 = np.clip(xs - r, 0, w), np.clip(xs + r + 1, 0, w)
    Y0, X0 = np.meshgrid(y0, x0, indexing="ij")
    Y1, X1 = np.meshgrid(y1, x1, indexing="ij")
    total = ii[Y1, X1] - ii[Y0, X1] - ii[Y1, X0] + ii[Y0, X0]
    area = (Y1 - Y0) * (X1 - X0)
    return total / np.maximum(area, 1)


def _defringe(rgb: np.ndarray, alpha: np.ndarray, passes: int = 4,
              mx_thresh: int = 205, sat_thresh: int = 35) -> None:
    """Schaelt den hellen Matte-Halo ab: Randpixel (opak, an Transparenz grenzend), die
    hell UND entsaettigt sind, werden transparent gesetzt. Stoppt von selbst an der
    dunklen Outline (mx zu niedrig) und an gesaettigten Blatt-/Topffarben (sat zu hoch).
    Modifiziert ``alpha`` in-place."""
    mx = rgb.max(2)
    sat = mx - rgb.min(2)
    bright_desat = (mx > mx_thresh) & (sat < sat_thresh)
    for _ in range(passes):
        opaque = alpha > 8
        trans = ~opaque
        edge = np.zeros_like(opaque)
        edge[1:, :]  |= opaque[1:, :]  & trans[:-1, :]
        edge[:-1, :] |= opaque[:-1, :] & trans[1:, :]
        edge[:, 1:]  |= opaque[:, 1:]  & trans[:, :-1]
        edge[:, :-1] |= opaque[:, :-1] & trans[:, 1:]
        kill = edge & bright_desat
        if not kill.any():
            break
        alpha[kill] = 0


def _defringe_colored(rgb: np.ndarray, alpha: np.ndarray, bg: np.ndarray,
                      thresh: float = 55.0, passes: int = 5) -> None:
    """Wie _defringe, aber fuer farbige Hintergruende: schaelt Randpixel ab, deren Farbe
    nahe an der BG-Farbe liegt (euklidischer RGB-Abstand < thresh). Modifiziert ``alpha``."""
    dist = np.sqrt(((rgb - bg) ** 2).sum(2))
    close = dist < thresh
    for _ in range(passes):
        opaque = alpha > 8
        trans = ~opaque
        edge = np.zeros_like(opaque)
        edge[1:, :]  |= opaque[1:, :]  & trans[:-1, :]
        edge[:-1, :] |= opaque[:-1, :] & trans[1:, :]
        edge[:, 1:]  |= opaque[:, 1:]  & trans[:, :-1]
        edge[:, :-1] |= opaque[:, :-1] & trans[:, 1:]
        kill = edge & close
        if not kill.any():
            break
        alpha[kill] = 0


def remove_bg(im: Image.Image) -> Image.Image:
    """Entfernt den Hintergrund -> RGBA. Erkennt die BG-Farbe selbst am Bildrand:

      * MAGENTA/Pink (empfohlen): systematischer Chroma-Key ueber M = min(R,B) - G.
        M > 0 heisst "beide, R und B, liegen ueber G" = Magenta-Signatur. KEIN Pflanzen-Pixel
        ist magenta (Gruen/Gold/Braun/Lachs-Wange/Weiss/rote Beere haben alle M<=2), daher wird
        global jeder Magenta-Pixel geschnitten -- auch eingeschlossene Taschen (zwischen Fluegeln,
        um schwebende Blaetter). Bewusst OHNE restore (das hatte Magenta-Taschen zurueckgeholt).
      * heller/weisser Hintergrund (oft als Schachbrett gemalt) -> hell+entsaettigt raus,
        Augen-Highlights via Integralbild zurueck, Matte-Halo + weicher Rest-Glow abgeschaelt.
      * sonstiger farbiger Hintergrund -> Pixel nahe der BG-Farbe (RGB-Abstand) raus.

    Bereits sauber freigestellte RGBA-Bilder werden unveraendert zurueckgegeben.
    """
    if im.mode == "RGBA" and im.getchannel("A").getextrema()[0] < 255:
        return im
    im = im.convert("RGB")
    arr = np.asarray(im, dtype=np.uint8)
    rgb = arr.astype(int)
    R, G, B = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    border = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]], 0)
    bg = np.median(border, 0)

    if bg[0] > 140 and bg[2] > 140 and bg[1] < 110:  # --- Magenta-Chroma-Key (Vlahos) ---
        # M = min(R,B) - G  ist die Magenta-Signatur (>0 => R UND B liegen ueber G).
        M = np.minimum(R, B) - G
        # 1) Weiche Matte (anti-aliased): M<=t0 voll deckend, M>=t1 voll transparent, Rampe dazwischen.
        t0, t1 = 2.0, 12.0
        alpha = (np.clip((t1 - M) / (t1 - t0), 0.0, 1.0) * 255).astype(np.uint8)
        # 2) Despill: Magenta-Stich aus den BEHALTENEN Pixeln klemmen (R,B -> G), nur wo M>0.
        # Trifft ausschliesslich magenta-getoente Pixel; Gold/Wange/rote Beere (M<=0) bleiben unberuehrt.
        spill = M > 0
        out = arr.copy()
        out[:, :, 0] = np.where(spill, np.minimum(R, G), R)
        out[:, :, 2] = np.where(spill, np.minimum(B, G), B)
        return Image.fromarray(np.dstack([out[:, :, :3], alpha]), "RGBA")

    if bg.min() > 200:  # heller Hintergrund
        mn, mx = rgb.min(2), rgb.max(2)
        bglike = (mn > 228) & ((mx - mn) < 22)
    else:  # sonstiger farbiger Hintergrund
        bglike = np.sqrt(((rgb - bg) ** 2).sum(2)) < 40
    alpha = np.where(bglike, 0, 255).astype(np.uint8)
    r = max(8, im.size[0] // 45)
    restore = (alpha == 0) & (_opaque_fraction(alpha > 0, r) > 0.55)
    alpha[restore] = 255
    if bg.min() > 200:
        _defringe(rgb, alpha)
        mn2 = rgb.min(2); sat2 = rgb.max(2) - mn2
        near_edge = _opaque_fraction(alpha > 0, 6) < 0.92
        faded = (alpha > 0) & near_edge & (sat2 < 30) & (mn2 > 200)
        whiteness = np.clip((mn2 - 200) / 55.0, 0.0, 1.0)
        soft = (255 * (1.0 - whiteness)).astype(np.uint8)
        alpha[faded] = np.minimum(alpha[faded], soft[faded])
    else:
        _defringe_colored(rgb, alpha, bg)
    return Image.fromarray(np.dstack([arr, alpha]), "RGBA")


# --- Helfer ----------------------------------------------------------------

def alpha_bbox(im: Image.Image) -> Image.Image:
    a = np.asarray(im.getchannel("A"))
    ys, xs = np.where(a > 8)
    if len(xs) == 0:
        return im
    return im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))


def _bleed_rgb(im: Image.Image, passes: int = 6) -> Image.Image:
    """Schiebt die Farbe der opaken Pixel um ``passes`` Pixel in die transparente Zone hinein
    (Alpha bleibt 0). Dadurch tragen beim Verkleinern keine Magenta-RGB-Reste mehr bei -- der
    Rand-Blend mischt nur noch Charakterfarben, also kein rosa/magenta Saum am Sprite."""
    a = np.asarray(im.convert("RGBA")).astype(np.float32).copy()
    rgb = a[:, :, :3]
    solid = a[:, :, 3] > 16
    for _ in range(passes):
        accum = np.zeros_like(rgb)
        cnt = np.zeros(solid.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ss = np.roll(solid, (dy, dx), (0, 1))
            sr = np.roll(rgb, (dy, dx), (0, 1))
            m = ss & ~solid
            accum[m] += sr[m]
            cnt[m] += 1
        fill = cnt > 0
        rgb[fill] = accum[fill] / cnt[fill][..., None]
        solid = solid | fill
    a[:, :, :3] = rgb
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def _resize_rgba(im: Image.Image, w: int, h: int) -> Image.Image:
    """Farb-Bleed (Decontaminate) + LANCZOS -> sauberer Alpha-Rand ohne Magenta-Saum."""
    return _bleed_rgb(im.convert("RGBA")).resize((w, h), Image.LANCZOS)


def scale_to_h(im: Image.Image, h: int) -> Image.Image:
    return _resize_rgba(im, max(1, round(im.width * h / im.height)), h)


def fit(im: Image.Image, cell: int, frac: float = 1.0) -> Image.Image:
    """Skaliert ``im`` so, dass es komplett in ein cell*frac-Quadrat passt (kein Ueberlauf)."""
    s = min(cell * frac / im.width, cell * frac / im.height)
    return _resize_rgba(im, max(1, round(im.width * s)), max(1, round(im.height * s)))


def paste_bottom_center(canvas: Image.Image, im: Image.Image, cx: int, baseline_y: int) -> None:
    canvas.alpha_composite(im, (cx - im.width // 2, baseline_y - im.height))


def load_clean(path: str) -> Image.Image:
    return remove_bg(Image.open(path))


# --- Sheets ----------------------------------------------------------------

def build_stage_sheet(out_path: str, frames: dict[str, str], cell: int = 256) -> None:
    """{wohl, bluehend, durstig, welkend, neugierig} -> ein quadratisches 5-Frame-Sheet.

    Jeder Frame wird per Alpha-Bbox freigestellt, in die Zelle eingepasst (kein Ueberlauf)
    und an der Grundlinie unten zentriert. Robust auch bei unterschiedlich grossen
    Quellbildern (Gemini variiert die Canvas-Groesse pro Generierung). ``wohl`` wird minimal
    kleiner skaliert, da es keine schwebenden Extras (Sparkles/Tropfen) hat.
    """
    scaled = {}
    for k in MOOD_ORDER:
        if k not in frames:
            continue
        im = alpha_bbox(load_clean(frames[k]))
        scaled[k] = fit(im, cell, 0.92 if k == "wohl" else 1.0)
    sheet = Image.new("RGBA", (cell * 5, cell), (0, 0, 0, 0))
    for i, k in enumerate(MOOD_ORDER):
        if k in scaled:
            paste_bottom_center(sheet, scaled[k], i * cell + cell // 2, cell)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    sheet.save(out_path)
    print(f"SHEET {out_path}: {sheet.size}")


def build_anim_sheet(out_path: str, src_path: str, cols: int, rows: int = 1, cell: int = 256) -> None:
    """Schneidet ein cols x rows Raster (ChatGPT-Grid oder -Streifen, Magenta-BG) in ein sauberes
    horizontales Animations-Sheet (cols*rows Zellen a cell px, ZEILEN-major) fuer CSS ``steps()``.
    Jeder Frame wird freigestellt, eingepasst und an der Grundlinie unten zentriert."""
    src = remove_bg(Image.open(src_path))
    w, h = src.size
    cw, ch = w // cols, h // rows
    frames = []
    for r in range(rows):
        for c in range(cols):
            frames.append(fit(alpha_bbox(src.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch))), cell))
    n = len(frames)
    sheet = Image.new("RGBA", (cell * n, cell), (0, 0, 0, 0))
    for i, fr in enumerate(frames):
        paste_bottom_center(sheet, fr, i * cell + cell // 2, cell)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    sheet.save(out_path)
    print(f"ANIM {out_path}: {sheet.size} ({n} Frames a {cell}px)")


def build_clean_bases(out_dir: str, src: dict[int, str], size: int = 256) -> None:
    """Gereinigte, transparente Einzel-PNGs je Stufe (Basis-Pose)."""
    os.makedirs(out_dir, exist_ok=True)
    for stage, path in src.items():
        im = alpha_bbox(load_clean(path))
        im = scale_to_h(im, size)
        p = os.path.join(out_dir, f"stage{stage}-base.png")
        im.save(p)
        print(f"BASE {p}: {im.size}")


def build_evolution(out_path: str, stages: list[tuple[str, float, str]], cell: int = 300) -> None:
    """Evolutions-Uebersicht: Wachstum durch vorgegebene Groessenkurve, Grundlinie unten."""
    imgs = [(scale_to_h(alpha_bbox(load_clean(p)), int(cell * f)), label) for p, f, label in stages]
    cw = max(i.width for i, _ in imgs) + 24
    sheet = Image.new("RGBA", (cw * len(imgs), cell + 26), (0, 0, 0, 0))
    d = ImageDraw.Draw(sheet)
    for i, (im, label) in enumerate(imgs):
        paste_bottom_center(sheet, im, i * cw + cw // 2, cell)
        d.text((i * cw + 8, cell + 6), label, fill=(224, 181, 61, 255))
    sheet.save(out_path)
    print(f"EVOLUTION {out_path}: {sheet.size}")


# --- aktuelle Quellen (Downloads) ------------------------------------------

def _downloads():
    dl = os.path.expanduser("~/Downloads")

    def find(pat):
        hits = sorted(glob.glob(os.path.join(dl, pat)))
        if not hits:
            raise FileNotFoundError(f"Keine Datei fuer Muster: {pat}")
        return hits[0]

    mascot = os.path.join(ROOT, "brand", "mascot", "mascot-cutout.webp")
    return {
        "mascot": mascot,
        "moods": {
            "wohl": mascot,
            "bluehend": find("MOOD: BL*"),
            "durstig": find("MOOD: DURSTIG*"),
            "welkend": find("MOOD: WELKEND*"),
            "neugierig": find("MOOD: NEUGIERIG*"),
        },
        "stages": {1: find("STUFE 1*"), 3: find("STUFE 3*"), 4: find("STUFE 4*"),
                   5: find("STUFE 5*"), 6: find("STUFE 6*")},
    }


def recolor_green(im: Image.Image, delta_h: float, sat_boost: float = 1.15) -> Image.Image:
    """Hue-shift ONLY the green-dominant pixels (character body + leaves) by ``delta_h`` degrees, in
    HSV so the terracotta pot, salmon cheeks, eyes and gold crown stay untouched. The pot is the
    constant anchor across skins; only the creature recolors."""
    rgba = np.asarray(im.convert("RGBA"))
    rgb = rgba[:, :, :3].astype(int)
    R, G, B = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    green = (G > R + 6) & (G > B + 6) & (rgb.max(2) > 70)  # clearly green, not the near-black outline
    hsv = np.asarray(im.convert("RGB").convert("HSV")).astype(np.int32)
    dh = int(round(delta_h / 360 * 255))
    hsv[:, :, 0] = np.where(green, (hsv[:, :, 0] + dh) % 256, hsv[:, :, 0])
    hsv[:, :, 1] = np.where(green, np.clip(hsv[:, :, 1] * sat_boost, 0, 255), hsv[:, :, 1])
    out = np.asarray(Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB"))
    # Write back ONLY the green pixels: the RGB->HSV->RGB round-trip is lossy (±1-3/channel quantisation),
    # so copying `out` wholesale would drift the pot/gold/cheeks/eyes too. Masking keeps every non-green
    # pixel byte-identical to the base sheet — the pot really is the constant anchor across all skins.
    res = rgba.copy()
    res[green, :3] = out[green]
    return Image.fromarray(res, "RGBA")


def build_skins() -> None:
    """Bake per-character recolor skins from the built mood sheets (pot stays terracotta). Output:
    frontend/public/sprites/spross-stage{N}-{skin}.png — the frontend swaps the URL per active skin."""
    made = 0
    for n in (1, 2, 3, 4, 5, 6):
        src = os.path.join(SPRITES_DIR, f"spross-stage{n}.png")
        if not os.path.exists(src):
            continue
        base = Image.open(src).convert("RGBA")
        for skin, dh in SKIN_RECOLOR.items():
            recolor_green(base, dh).save(os.path.join(SPRITES_DIR, f"spross-stage{n}-{skin}.png"))
            made += 1
    print(f"SKINS: {made} recolor-sheets -> {SPRITES_DIR}")


_MOOD_KEYS = {"blühend": "bluehend", "bluehend": "bluehend", "durstig": "durstig",
              "welkend": "welkend", "neugierig": "neugierig"}


def _classify(path: str):
    """(stage, kind, is_latest) aus einem (auch unsauberen) Dateinamen, sonst None.

    kind in {wohl, bluehend, durstig, welkend, neugierig}; 'base'/'new_base' -> wohl.
    Erkennt z. B. 'stage5MOOD: WELKEND ... LATESTUSETHIS.png' korrekt; bei Duplikaten
    (mit/ohne LATESTUSETHIS) gewinnt die LATEST-Variante.
    """
    low = os.path.basename(path).lower()
    m = re.search(r"stage\s*([1-6])", low)
    if not m:
        return None
    stage = int(m.group(1))
    if "base" in low:
        kind = "wohl"
    else:
        kind = next((v for k, v in _MOOD_KEYS.items() if k in low), None)
        if kind is None:
            return None
    return stage, kind, ("latestusethis" in low)


def main(argv: list[str]) -> None:
    cmd = argv[0] if argv else "all"
    if cmd == "all":
        d = _downloads()
        build_stage_sheet(os.path.join(SPRITES_DIR, "spross-stage2.png"), d["moods"])
        bases = {2: d["mascot"], **d["stages"]}
        build_clean_bases(os.path.join(ROOT, "brand", "mascot", "clean"), bases)
        evo = [
            (d["stages"][1], 0.50, "1 Keimling"),
            (d["mascot"],    0.62, "2 Sprossling"),
            (d["stages"][3], 0.74, "3 Blattgeist"),
            (d["stages"][4], 0.82, "4 Rankenweiser"),
            (d["stages"][5], 0.90, "5 Bluetenwaechter"),
            (d["stages"][6], 1.00, "6 Urgeist"),
        ]
        build_evolution(os.path.join(ROOT, "brand", "mascot", "spross-evolution.png"), evo)
    elif cmd == "stage":
        n, paths = argv[1], argv[2:]
        if len(paths) != 5:
            sys.exit("stage braucht: <N> wohl bluehend durstig welkend neugierig")
        frames = dict(zip(MOOD_ORDER, paths))
        build_stage_sheet(os.path.join(SPRITES_DIR, f"spross-stage{n}.png"), frames)
    elif cmd == "folder":
        src_dir = argv[1] if len(argv) > 1 else os.path.expanduser("~/Downloads")
        clean_dir = os.path.join(ROOT, "brand", "mascot", "clean")
        os.makedirs(clean_dir, exist_ok=True)
        exts = (".png", ".webp", ".jpg", ".jpeg")
        chosen = {}  # (stage, kind) -> (is_latest, path)
        for f in glob.glob(os.path.join(src_dir, "*")):
            if not f.lower().endswith(exts):
                continue
            c = _classify(f)
            if not c:
                continue
            stage, kind, latest = c
            key = (stage, kind)
            if key not in chosen or (latest and not chosen[key][0]):
                chosen[key] = (latest, f)
        mood_keys = ["bluehend", "durstig", "welkend", "neugierig"]
        built, missing = [], []
        for n in (1, 2, 3, 4, 5, 6):
            w = chosen.get((n, "wohl"))
            base_path = os.path.join(clean_dir, f"stage{n}-base.png")
            if w:  # neue Basis vorhanden -> clean-Basis aktualisieren, als wohl nutzen
                fit(alpha_bbox(load_clean(w[1])), 256).save(base_path)
                wohl_src = w[1]
            elif n == 2 and os.path.exists(MASCOT_HIRES):  # Stufe 2 = Mascot, hochaufgel. Original (scharfe Augen)
                fit(alpha_bbox(load_clean(MASCOT_HIRES)), 256).save(base_path)
                wohl_src = MASCOT_HIRES
            elif os.path.exists(base_path):
                wohl_src = base_path
            else:
                missing.append((n, ["wohl/Basis"]))
                continue
            present = {m: chosen[(n, m)][1] for m in mood_keys if (n, m) in chosen}
            if len(present) == 4:
                build_stage_sheet(os.path.join(SPRITES_DIR, f"spross-stage{n}.png"),
                                  {"wohl": wohl_src, **present})
                built.append(n)
            else:
                missing.append((n, [m for m in mood_keys if m not in present]))
        # Evolutions-Uebersicht aus den (aktualisierten) Basen neu bauen
        growth = [(1, 0.50, "1 Keimling"), (2, 0.62, "2 Sprossling"), (3, 0.74, "3 Blattgeist"),
                  (4, 0.82, "4 Rankenweiser"), (5, 0.91, "5 Bluetenwaechter"), (6, 1.00, "6 Urgeist")]
        evo = [(os.path.join(clean_dir, f"stage{n}-base.png"), fr, lb) for n, fr, lb in growth
               if os.path.exists(os.path.join(clean_dir, f"stage{n}-base.png"))]
        if evo:
            build_evolution(os.path.join(ROOT, "brand", "mascot", "spross-evolution.png"), evo)
        build_skins()  # regenerate the per-character recolor skins from the fresh mood sheets
        print("Gebaut:", built or "-")
        for n, miss in missing:
            print(f"Stufe {n}: es fehlen {miss}")
    elif cmd == "skins":
        build_skins()
    elif cmd == "anim":
        # anim <name> <cols> <rows> <img>  -> frontend/public/sprites/spross-anim-<name>.png
        name, cols, rows, src = argv[1], int(argv[2]), int(argv[3]), argv[4]
        build_anim_sheet(os.path.join(SPRITES_DIR, f"spross-anim-{name}.png"), src, cols, rows)
    elif cmd == "clean":
        remove_bg(Image.open(argv[1])).save(argv[2])
        print(f"CLEAN {argv[2]}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
