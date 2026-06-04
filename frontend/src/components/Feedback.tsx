import { Component, type ReactNode } from "react";
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

/** Persistent top banner for global states (offline, system). Not auto-dismissing. */
export function Banner({ message, onDismiss }: { message: string; onDismiss?: () => void }) {
  const { t } = useI18n();
  return (
    <div
      role="alert"
      aria-live="polite"
      className="flex items-center justify-center gap-3 bg-pp-danger px-4 py-1.5 text-center text-[11px] font-bold text-white"
      style={{ paddingTop: "max(0.375rem, env(safe-area-inset-top))" }}
    >
      <span>{message}</span>
      {onDismiss && (
        <button type="button" onClick={onDismiss} aria-label={t("error.dismiss")} className="px-1">
          ✕
        </button>
      )}
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
