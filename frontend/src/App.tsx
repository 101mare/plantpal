import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { api } from "./api";
import { useI18n } from "./i18n";
import { Banner, ErrorBoundary } from "./components/Feedback";
import { LoginPage } from "./pages/LoginPage";
import { LoginCodePage } from "./pages/LoginCodePage";
import { RegisterPage } from "./pages/RegisterPage";
import { PlantdexPage } from "./pages/PlantdexPage";
import { SettingsPage } from "./pages/SettingsPage";
import { StatsPage } from "./pages/StatsPage";
import { ImpressumPage, DatenschutzPage } from "./pages/LegalPages";

function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: api.me, retry: false });
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const { data, isLoading, isError } = useMe();
  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center pp-heading">{t("app.loading")}</div>
    );
  }
  if (isError || !data) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

/** On every client-side route change reset scroll and move focus to the page heading,
 *  so keyboard/screen-reader users don't stay stranded on the old link (A11Y-12). */
function RouteFocus() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
    document.querySelector<HTMLElement>("h1")?.focus?.({ preventScroll: true });
  }, [pathname]);
  return null;
}

function useOnline(): boolean {
  const [online, setOnline] = useState(() => typeof navigator === "undefined" || navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  return online;
}

export function App() {
  const { t } = useI18n();
  const online = useOnline();
  return (
    <>
      <a href="#main" className="pp-skip pp-btn">
        {t("a11y.skip")}
      </a>
      {!online && <Banner message={t("error.offline")} />}
      <RouteFocus />
      <ErrorBoundary>
        <main id="main" className="h-full">
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/login/code" element={<LoginCodePage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route
              path="/"
              element={
                <RequireAuth>
                  <PlantdexPage />
                </RequireAuth>
              }
            />
            <Route
              path="/settings"
              element={
                <RequireAuth>
                  <SettingsPage />
                </RequireAuth>
              }
            />
            <Route
              path="/stats"
              element={
                <RequireAuth>
                  <StatsPage />
                </RequireAuth>
              }
            />
            <Route path="/impressum" element={<ImpressumPage />} />
            <Route path="/datenschutz" element={<DatenschutzPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </ErrorBoundary>
    </>
  );
}
