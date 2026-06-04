import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { Toaster, toast } from "sonner";
import { App } from "./App";
import { I18nProvider, detectLocale } from "./i18n";
import { ThemeProvider, detectTheme, useTheme } from "./theme";
import "./index.css";

// Apply persisted theme + language before first paint (no flash).
document.documentElement.setAttribute("data-theme", detectTheme());
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
              const de = detectLocale() === "de";
              toast(de ? "Update verfügbar" : "Update available", {
                duration: Infinity,
                action: {
                  label: de ? "Neu laden" : "Reload",
                  onClick: () => window.location.reload(),
                },
              });
            }
          });
        });
      })
      .catch(() => {});
  });
}

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});

function ThemedToaster() {
  const { theme } = useTheme();
  return <Toaster theme={theme} position="top-center" richColors />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <I18nProvider>
          <BrowserRouter>
            <App />
            <ThemedToaster />
          </BrowserRouter>
        </I18nProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </StrictMode>,
);
