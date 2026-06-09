import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "./api";
import { useI18n } from "./i18n";
import { Banner, ErrorBoundary } from "./components/Feedback";
import { TabBar } from "./components/TabBar";
import { AddPlantModal } from "./components/AddPlantModal";
import { AppShellContext, type SprossMirror } from "./appShell";
import { loadSprossStore } from "./sprossState";
import type { Stage } from "./status";
import { LoginPage } from "./pages/LoginPage";
import { LoginCodePage } from "./pages/LoginCodePage";
import { RegisterPage } from "./pages/RegisterPage";
import { PlantdexPage } from "./pages/PlantdexPage";
import { SettingsPage } from "./pages/SettingsPage";
import { StatsPage } from "./pages/StatsPage";
import { SprossPage } from "./pages/SprossPage";
import { ImpressumPage, DatenschutzPage } from "./pages/LegalPages";

function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: api.me, retry: false });
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const { data, isLoading, isError } = useMe();
  if (isLoading) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center pp-heading">
        {t("app.loading")}
      </div>
    );
  }
  if (isError || !data) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

/** Persistent layout for the four app routes: holds the AppShell context (live Spross mirror +
 *  openAdd), renders the page via <Outlet/> with bottom padding for the bar, the persistent TabBar,
 *  and the lifted Add-Plant sheet. A single Layout-Route (not a per-route wrapper) keeps the bar,
 *  context, hop-timer and an open Add-sheet MOUNTED across tab switches (no re-mount flicker). */
function AppShell() {
  const [adding, setAdding] = useState(false);
  // Seed the mirror from the persisted store so the central medallion is never empty on a cold
  // start that lands on /stats or /settings (mood stays the calm 'wohl' default until PlantdexPage
  // mounts and pushes the live collective mood).
  const [spross, setSpross] = useState<SprossMirror>(() => {
    const s = loadSprossStore();
    return {
      mood: "wohl",
      stage: (s?.stageMax ?? 2) as Stage,
      skin: s?.activeSkin ?? null,
      vacation: s?.vacation.on ?? false,
      reactNonce: 0,
      riseNonce: 0,
      bloomNonce: 0,
    };
  });
  const value = useMemo(() => ({ spross, setSpross, openAdd: () => setAdding(true) }), [spross]);
  return (
    <AppShellContext.Provider value={value}>
      <div className="pb-tab-safe">
        <Outlet />
      </div>
      <TabBar />
      {adding && <AddPlantModal onClose={() => setAdding(false)} />}
    </AppShellContext.Provider>
  );
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

/** A new service-worker bundle finished installing (event fired from main.tsx). We show a
 *  persistent banner with a manual reload rather than swapping bundles mid-session (A11Y-07). */
function useUpdateAvailable(): boolean {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const onUpdate = () => setReady(true);
    window.addEventListener("pp:update-available", onUpdate);
    return () => window.removeEventListener("pp:update-available", onUpdate);
  }, []);
  return ready;
}

export function App() {
  const { t } = useI18n();
  const online = useOnline();
  const updateReady = useUpdateAvailable();
  return (
    <>
      <a href="#main" className="pp-skip pp-btn">
        {t("a11y.skip")}
      </a>
      {/* Global-state banners stay pinned to the top while the page scrolls, so the offline/update
          notice doesn't scroll out of view on a long list (M: keep global state visible). */}
      {(!online || updateReady) && (
        <div className="sticky top-0 z-50">
          {!online && <Banner message={t("error.offline")} />}
          {updateReady && (
            <Banner
              tone="neutral"
              message={t("update.available")}
              action={{ label: t("update.reload"), onClick: () => window.location.reload() }}
            />
          )}
        </div>
      )}
      <RouteFocus />
      <ErrorBoundary>
        <main id="main" className="h-full">
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/login/code" element={<LoginCodePage />} />
            <Route path="/register" element={<RegisterPage />} />
            {/* One persistent Layout-Route gates auth once, then keeps the TabBar + AppShell context
                + hop-timer + open Add-sheet mounted across the four app tabs (no per-tab re-mount). */}
            <Route
              element={
                <RequireAuth>
                  <AppShell />
                </RequireAuth>
              }
            >
              <Route path="/" element={<PlantdexPage />} />
              <Route path="/stats" element={<StatsPage />} />
              <Route path="/spross" element={<SprossPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
            <Route path="/impressum" element={<ImpressumPage />} />
            <Route path="/datenschutz" element={<DatenschutzPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </ErrorBoundary>
    </>
  );
}
