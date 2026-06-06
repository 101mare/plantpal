import { Component, useEffect, useRef, useState, type ReactNode } from "react";
import { errorText, useI18n } from "../i18n";

/**
 * Contextual error feedback, replacing scattered `toast.error` (research: toasts are wrong
 * for errors — they vanish, miss screen readers, sit far from the trigger). Errors now show
 * inline at the trigger, as a view error-state with retry, or as a persistent banner.
 */

/** Inline error directly at the form/button that failed. Persists until resolved. */
export function InlineError({ error, className = "" }: { error: unknown; className?: string }) {
  const { t } = useI18n();
  if (error == null) return null;
  return (
    <p role="alert" className={`text-[11px] leading-snug text-pp-danger ${className}`}>
      {errorText(error, t)}
    </p>
  );
}

/**
 * Persistent top banner for global states (offline, system, app-update). Not auto-dismissing —
 * it stays as long as the state holds, the opposite of an ephemeral toast.
 *  - tone="danger"  red, role=alert    (offline / something broke)
 *  - tone="neutral" green, role=status (a non-error prompt like "update available")
 * An optional `action` renders an inline button (e.g. "Reload") right in the banner.
 */
export function Banner({
  message,
  onDismiss,
  action,
  tone = "danger",
}: {
  message: string;
  onDismiss?: () => void;
  action?: { label: string; onClick: () => void };
  tone?: "danger" | "neutral";
}) {
  const { t } = useI18n();
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      aria-live={tone === "danger" ? "assertive" : "polite"}
      className={`flex items-center justify-center gap-3 px-4 py-1.5 text-center text-[11px] font-bold text-white ${
        tone === "danger" ? "bg-pp-danger" : "bg-pp-border"
      }`}
      style={{ paddingTop: "max(0.375rem, env(safe-area-inset-top))" }}
    >
      <span>{message}</span>
      {action && (
        <button
          type="button"
          onClick={action.onClick}
          className="px-3 py-2 underline underline-offset-2"
        >
          {action.label}
        </button>
      )}
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label={t("error.dismiss")}
          className="px-3 py-2"
        >
          ✕
        </button>
      )}
    </div>
  );
}

const ANNOUNCE_EVENT = "pp:announce";

/**
 * Fire a screen-reader announcement *without* showing any visible popup. Successful actions are
 * now silent for sighted users — the UI change itself (card turns green, modal closes, new card
 * appears) is the confirmation — but screen-reader users still need to hear that it worked. Call
 * this with an already-translated string; the single <LiveRegion> at the app root speaks it.
 * (Research: NN/G / Apple HIG — prefer nonintrusive status; Sara Soueidan — mirror silent UI
 * changes into an aria-live region or they're invisible to assistive tech.)
 */
export function announce(message: string) {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(ANNOUNCE_EVENT, { detail: message }));
  }
}

/** Single visually-hidden polite live region with a small FIFO queue. Several quick
 *  announcements (e.g. watering two plants in a row) used to clobber each other through one
 *  shared 50ms timer — now each is given its own airtime so none is lost (N38). Mount once. */
export function LiveRegion() {
  const [message, setMessage] = useState("");
  const queue = useRef<string[]>([]);
  const draining = useRef(false);
  useEffect(() => {
    let clearTimer: ReturnType<typeof setTimeout>;
    let nextTimer: ReturnType<typeof setTimeout>;
    const drain = () => {
      const next = queue.current.shift();
      if (next === undefined) {
        draining.current = false;
        return;
      }
      draining.current = true;
      // Clear first, then set on the next tick, so identical consecutive text is still spoken
      // (assistive tech ignores an unchanged live-region value).
      setMessage("");
      clearTimer = setTimeout(() => {
        setMessage(next);
        nextTimer = setTimeout(drain, 1100); // each message gets ~1.1s before the next one
      }, 60);
    };
    const onAnnounce = (e: Event) => {
      queue.current.push((e as CustomEvent<string>).detail);
      if (!draining.current) drain();
    };
    window.addEventListener(ANNOUNCE_EVENT, onAnnounce);
    return () => {
      window.removeEventListener(ANNOUNCE_EVENT, onAnnounce);
      clearTimeout(clearTimer);
      clearTimeout(nextTimer);
    };
  }, []);
  return (
    <div role="status" aria-live="polite" className="sr-only">
      {message}
    </div>
  );
}

/** Replaces a whole view when its data couldn't load. Offers a retry. */
export function ErrorState({
  error,
  onRetry,
  message,
}: {
  error?: unknown;
  onRetry?: () => void;
  message?: string;
}) {
  const { t } = useI18n();
  return (
    <div role="alert" className="pp-frame p-6 text-center text-sm">
      <p className="mb-3">
        {message ?? (error !== undefined ? errorText(error, t) : t("error.generic"))}
      </p>
      {onRetry && (
        <button type="button" className="pp-btn" onClick={onRetry}>
          {t("error.retry")}
        </button>
      )}
    </div>
  );
}

function FallbackError() {
  const { t } = useI18n();
  return (
    <div className="flex h-full items-center justify-center p-4">
      <div className="pp-frame p-8 text-center text-sm">
        <div className="mb-3 text-3xl">🪴</div>
        <p className="mb-4">{t("error.server")}</p>
        <button type="button" className="pp-btn" onClick={() => window.location.reload()}>
          {t("error.retry")}
        </button>
      </div>
    </div>
  );
}

/** Catches unexpected render crashes so a single broken view can't blank the whole app.
 *  Small hand-rolled boundary — no extra dependency. */
export class ErrorBoundary extends Component<
  { children: ReactNode; fallback?: ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) return this.props.fallback ?? <FallbackError />;
    return this.props.children;
  }
}
