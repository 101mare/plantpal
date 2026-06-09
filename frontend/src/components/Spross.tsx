import { useEffect, useRef, useState, type CSSProperties } from "react";
import type { SprossMood } from "../status";

/** Every sheet is 1280x256 = 5 frames of 256px, order: wohl|bluehend|durstig|welkend|neugierig.
 *  We derive the background math from FRAME_COUNT so a future mis-sized sheet fails loudly instead
 *  of silently mis-cropping — never hardcode -256px. */
const FRAME_COUNT = 5;
const FRAME: Record<SprossMood, number> = {
  wohl: 0,
  bluehend: 1,
  durstig: 2,
  welkend: 3,
  neugierig: 4,
};

interface SprossProps {
  mood: SprossMood;
  /** px box (w=h). If omitted, the caller MUST size via `className` (e.g. responsive h-16 sm:h-24). */
  size?: number;
  /** 1..6 evolution stage (which sheet). The band/hero pass the ratcheted stageMax. */
  stage?: 1 | 2 | 3 | 4 | 5 | 6;
  /** Unlocked cosmetic skin id → swaps to the PRE-BAKED recoloured sheet (spross-stage{N}-{id}.png). */
  skin?: string | null;
  /** Vacation "dormant" look: a static desaturate on the inner sprite; overrides any skin. */
  rest?: boolean;
  /** Bump to replay the one-shot joy-wiggle (after watering). Undefined = no motion. */
  reactNonce?: number;
  /** Bump to play the one-shot "straighten up" recovery (when the last thirsty plant is watered).
   *  Mutually exclusive with reactNonce per water-event, so they never collide on the inner sprite. */
  riseNonce?: number;
  /** Bump to play the one-shot level-up "bloom" glow (on the WRAPPER, so it never collides with the
   *  inner-sprite animations and is never tinted by a skin filter). Undefined = no bloom. */
  bloomNonce?: number;
  /** If set, Spross becomes a real <button> (>=44px) that replays the wiggle. Else decorative. */
  onPet?: () => void;
  className?: string;
}

/**
 * Dumb, presentational CSS-sprite mascot — decorative by DEFAULT (aria-hidden): every state it
 * mirrors is already in the screen-reader tree (thirsty count + heading, plant labels, stats
 * numbers, the /spross stage text), so labelling it would double-announce — the nag the design
 * forbids. Mood + stage = an INSTANT background swap (never a transition). The joy-wiggle, the
 * recovery "rise", and the level-up bloom are CSS @keyframes (in index.css) authored to rest at
 * identity, so prefers-reduced-motion freezes them to a normal sprite while mood/stage still switch.
 */
export function Spross({
  mood,
  size,
  stage = 2,
  skin,
  rest,
  reactNonce,
  riseNonce,
  bloomNonce,
  onPet,
  className,
}: SprossProps) {
  const [reacting, setReacting] = useState(false);
  const [rising, setRising] = useState(false);
  const [blooming, setBlooming] = useState(false);
  const seenReact = useRef(reactNonce);
  const seenRise = useRef(riseNonce);
  const seenBloom = useRef(bloomNonce);
  useEffect(() => {
    if (reactNonce !== undefined && reactNonce !== seenReact.current) {
      seenReact.current = reactNonce;
      setReacting(true);
    }
  }, [reactNonce]);
  useEffect(() => {
    if (riseNonce !== undefined && riseNonce !== seenRise.current) {
      seenRise.current = riseNonce;
      setRising(true);
    }
  }, [riseNonce]);
  useEffect(() => {
    if (bloomNonce !== undefined && bloomNonce !== seenBloom.current) {
      seenBloom.current = bloomNonce;
      setBlooming(true);
    }
  }, [bloomNonce]);

  const box: CSSProperties = {
    ...(size !== undefined ? { width: size, height: size } : {}),
    position: "relative",
    display: "inline-block",
  };
  // A skin = a pre-baked recoloured sheet; vacation (`rest`) always shows the BASE sheet (the static
  // .spross-rest desaturate then reads as dormant) so a skin never bleeds through the rest look.
  const skinSuffix = skin && !rest ? `-${skin}` : "";
  const sprite: CSSProperties = {
    width: "100%",
    height: "100%",
    backgroundImage: `url(/sprites/spross-stage${stage}${skinSuffix}.png)`,
    backgroundSize: `${FRAME_COUNT * 100}% 100%`,
    backgroundPositionX: `${(FRAME[mood] / (FRAME_COUNT - 1)) * 100}%`,
    backgroundRepeat: "no-repeat",
  };
  const wrapCls = ["spross-wrap", blooming ? "spross-bloom" : "", className]
    .filter(Boolean)
    .join(" ");
  // animationend bubbles; clear strictly by name so the wrapper-bloom and inner animations don't cross-clear.
  const onWrapEnd = (e: { animationName: string }) => {
    if (e.animationName === "spross-bloom") setBlooming(false);
  };
  const innerCls = [
    "pixelated",
    "spross",
    reacting ? "spross-react" : "",
    rising ? "spross-rise" : "",
    rest ? "spross-rest" : "",
  ]
    .filter(Boolean)
    .join(" ");
  const inner = (
    <span
      aria-hidden="true"
      className={innerCls}
      style={sprite}
      onAnimationEnd={(e) => {
        if (e.animationName === "spross-wiggle") setReacting(false);
        else if (e.animationName === "spross-rise") setRising(false);
      }}
    />
  );

  if (onPet) {
    return (
      <button
        type="button"
        aria-label="Spross"
        onClick={onPet}
        onAnimationEnd={onWrapEnd}
        className={wrapCls}
        style={{
          ...box,
          minWidth: 44,
          minHeight: 44,
          border: 0,
          padding: 0,
          background: "none",
          cursor: "pointer",
        }}
      >
        {inner}
      </button>
    );
  }
  return (
    <span
      aria-hidden="true"
      className={wrapCls}
      style={{ ...box, pointerEvents: "none", userSelect: "none" }}
      onAnimationEnd={onWrapEnd}
    >
      {inner}
    </span>
  );
}
