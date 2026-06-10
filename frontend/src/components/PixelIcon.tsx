/** Hand-pixeled 8×8 icons rendered as crisp SVG rects in currentColor.
 *
 * Replaces emoji glyphs in UI chrome: emojis render differently per platform/font and
 * clash with the Press Start 2P pixel aesthetic; these stay identical everywhere, tint
 * with the theme, and scale without smoothing (shape-rendering: crispEdges).
 * Decorative by default (aria-hidden) — pass `label` only when the icon stands alone.
 */

const GRIDS = {
  drop: [
    "...XX...",
    "...XX...",
    "..XXXX..",
    "..XXXX..",
    ".XXXXXX.",
    ".XXXXXX.",
    ".XXXXXX.",
    "..XXXX..",
  ],
  check: [
    "........",
    "......XX",
    ".....XXX",
    "....XXX.",
    "XX.XXX..",
    "XXXXX...",
    ".XXX....",
    "..X.....",
  ],
  trash: [
    "..XXXX..",
    "XXXXXXXX",
    ".XXXXXX.",
    ".XXXXXX.",
    ".XXXXXX.",
    ".XXXXXX.",
    ".XXXXXX.",
    "..XXXX..",
  ],
  camera: [
    "........",
    ".XX.....",
    "XXXXXXXX",
    "XXXXXXXX",
    "XXX..XXX",
    "XXX..XXX",
    "XXXXXXXX",
    "XXXXXXXX",
  ],
  lock: [
    "..XXXX..",
    ".XX..XX.",
    ".XX..XX.",
    "XXXXXXXX",
    "XXXXXXXX",
    "XXX..XXX",
    "XXXX.XXX",
    "XXXXXXXX",
  ],
  trophy: [
    "XXXXXXXX",
    ".XXXXXX.",
    ".XXXXXX.",
    "..XXXX..",
    "...XX...",
    "...XX...",
    "..XXXX..",
    ".XXXXXX.",
  ],
  bars: [
    "......XX",
    "......XX",
    "...XX.XX",
    "...XX.XX",
    "XX.XX.XX",
    "XX.XX.XX",
    "XX.XX.XX",
    "XX.XX.XX",
  ],
} as const;

export type PixelIconName = keyof typeof GRIDS;

export function PixelIcon({
  name,
  size = 12,
  className,
  label,
}: {
  name: PixelIconName;
  /** Rendered px box (w=h). Multiples of 8 stay perfectly crisp but any size works. */
  size?: number;
  className?: string;
  /** Accessible name — only when the icon is NOT accompanied by visible text. */
  label?: string;
}) {
  return (
    <svg
      viewBox="0 0 8 8"
      width={size}
      height={size}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={className}
      style={{ shapeRendering: "crispEdges" }}
    >
      {GRIDS[name].flatMap((row, y) =>
        [...row].map((cell, x) =>
          cell === "X" ? (
            <rect key={`${x}.${y}`} x={x} y={y} width={1} height={1} fill="currentColor" />
          ) : null,
        ),
      )}
    </svg>
  );
}
