import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { ApiError } from "./api";
import { App } from "./App";
import { LiveRegion } from "./components/Feedback";
import { I18nProvider, detectLocale } from "./i18n";
import { ThemeProvider, detectBackground, detectTheme } from "./theme";
import "./index.css";

// Apply persisted theme + language before first paint (no flash).
document.documentElement.setAttribute("data-theme", detectTheme());
// Pre-paint the iOS/Android status-bar colour from the persisted theme too, so a light-mode user
// no longer gets a dark-statusbar flash on cold start (theme.tsx keeps it in sync on later toggles).
document
  .querySelector('meta[name="theme-color"]')
  ?.setAttribute("content", detectTheme() === "light" ? "#f3efe2" : "#0d2018");
document.documentElement.setAttribute("data-bg", detectBackground());
document.documentElement.lang = detectLocale();

// Register the service worker; surface an explicit "update available" banner with a manual
// reload instead of silently swapping bundles mid-session (A11Y-07).
if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js")
      .then((reg) => {
        reg.addEventListener("updatefound", () => {
          const sw = reg.installing;
          sw?.addEventListener("statechange", () => {
            if (sw.state === "installed" && navigator.serviceWorker.controller) {
              // Hand off to React (App renders a persistent banner) instead of a floating toast.
              window.dispatchEvent(new CustomEvent("pp:update-available"));
            }
          });
        });
      })
      .catch(() => {});
  });
}

// On an expired session (401) bounce to the login screen, instead of letting every query and
// mutation surface its own error. Background-refetch failures stay silent (stale data stays
// visible); initial-load failures are shown by each view's ErrorState; everything else is
// handled inline at the trigger — so there are no app-wide error toasts anymore.
function handle401(error: unknown) {
  if (
    error instanceof ApiError &&
    error.status === 401 &&
    !window.location.pathname.startsWith("/login")
  ) {
    window.location.assign("/login");
  }
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: handle401 }),
  mutationCache: new MutationCache({ onError: handle401 }),
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <I18nProvider>
          <BrowserRouter>
            <App />
            <LiveRegion />
          </BrowserRouter>
        </I18nProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </StrictMode>,
);
