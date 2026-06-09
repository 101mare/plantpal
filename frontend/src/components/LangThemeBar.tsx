import { Link } from "react-router-dom";
import { useI18n } from "../i18n";
import { useTheme } from "../theme";

/** Compact language + theme switcher and legal links for unauthenticated pages. */
export function LangThemeBar() {
  const { t, locale, setLocale } = useI18n();
  const { theme, toggle } = useTheme();
  return (
    <div className="mt-4 flex flex-col items-center gap-2 text-[10px]">
      <div className="flex items-center gap-4">
        <button
          type="button"
          className="pp-tap px-3 underline"
          onClick={() => setLocale(locale === "de" ? "en" : "de")}
          aria-label={locale === "de" ? "Switch to English" : "Auf Deutsch umschalten"}
        >
          {locale === "de" ? "EN" : "DE"}
        </button>
        <button
          type="button"
          className="pp-tap px-3 underline"
          onClick={toggle}
          aria-label={theme === "dark" ? t("settings.theme.light") : t("settings.theme.dark")}
        >
          {theme === "dark" ? "☀️ Light" : "🌙 Dark"}
        </button>
      </div>
      <div className="flex gap-4 opacity-60">
        <Link to="/impressum" className="pp-tap px-2">
          Impressum
        </Link>
        <Link to="/datenschutz" className="pp-tap px-2">
          Datenschutz
        </Link>
      </div>
    </div>
  );
}
