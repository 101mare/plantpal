import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useI18n } from "../i18n";
import { useAppShell } from "../appShell";
import { Spross } from "./Spross";

/**
 * Persistent bottom tab-bar — the app's sole primary navigation (Instagram-style: no back buttons,
 * sections switch only via the tabs; detail views stay backdrop sheets). A <nav> landmark with
 * Links + aria-current="page" — NOT role=tablist/tab (that ARIA pattern is for in-page tabpanels,
 * expects aria-controls + arrow-key roving, and would announce "tab" without a panel).
 *
 * The central tab renders the REAL Spross sprite (mood-mirrored, larger + raised on a pedestal). The
 * add (+) tab opens the persistent Add-Plant sheet via the AppShell context (NOT a window-event — the
 * old PlantdexPage listener is unmounted on /stats|/spross|/settings).
 */
export function TabBar() {
  const { t } = useI18n();
  const { pathname } = useLocation();
  const { spross, openAdd } = useAppShell();
  const [kbd, setKbd] = useState(false);

  // Hide the bar while the on-screen keyboard is open (Plantdex search / Settings fields) so it
  // doesn't float mid-screen above the keyboard. Feature-detected — a no-op without visualViewport.
  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;
    const onResize = () => setKbd(window.innerHeight - vv.height > 120);
    vv.addEventListener("resize", onResize);
    return () => vv.removeEventListener("resize", onResize);
  }, []);

  return (
    <nav className={`pp-tabbar ${kbd ? "pp-tabbar--kbd" : ""}`} aria-label={t("nav.primary")}>
      <Link
        to="/"
        aria-label={t("nav.plantdex")}
        title={t("nav.plantdex")}
        aria-current={pathname === "/" ? "page" : undefined}
        className={`pp-tab ${pathname === "/" ? "pp-tab-active" : ""}`}
      >
        <img src="/sprites/tab-plantdex.png" alt="" aria-hidden="true" className="pp-tab-ico" />
      </Link>
      <Link
        to="/stats"
        aria-label={t("nav.stats")}
        title={t("nav.stats")}
        aria-current={pathname === "/stats" ? "page" : undefined}
        className={`pp-tab ${pathname === "/stats" ? "pp-tab-active" : ""}`}
      >
        <img src="/sprites/tab-stats.png" alt="" aria-hidden="true" className="pp-tab-ico" />
      </Link>
      {/* Central, raised tab: the real mood-mirrored Spross sprite (identity), not a flat icon. */}
      <Link
        to="/spross"
        aria-label={t("nav.spross")}
        title={t("nav.spross")}
        aria-current={pathname === "/spross" ? "page" : undefined}
        className={`pp-tab-center ${pathname === "/spross" ? "pp-tab-center-active" : ""}`}
      >
        <span className="pp-tab-pedestal">
          <Spross
            mood={spross.mood}
            stage={spross.stage}
            skin={spross.vacation ? undefined : spross.skin}
            rest={spross.vacation}
            reactNonce={spross.reactNonce}
            riseNonce={spross.riseNonce}
            bloomNonce={spross.bloomNonce}
            className="h-10 w-10"
          />
        </span>
      </Link>
      <Link
        to="/settings"
        aria-label={t("nav.settings")}
        title={t("nav.settings")}
        aria-current={pathname === "/settings" ? "page" : undefined}
        className={`pp-tab ${pathname === "/settings" ? "pp-tab-active" : ""}`}
      >
        <img src="/sprites/tab-settings.png" alt="" aria-hidden="true" className="pp-tab-ico" />
      </Link>
      <button
        type="button"
        className="pp-tab pp-tab-add"
        aria-label={t("nav.add")}
        title={t("nav.add")}
        onClick={openAdd}
      >
        <span aria-hidden="true" className="pp-tab-add-glyph">
          <img src="/sprites/tab-add.png" alt="" className="pp-tab-add-icon" />
        </span>
      </button>
    </nav>
  );
}
