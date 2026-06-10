import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Background, Theme } from "./types";

export function detectTheme(): Theme {
  return localStorage.getItem("pp_theme") === "light" ? "light" : "dark";
}

// Curated set (V2): forest default + one bright + one warm. The old tiefsee/tanne/moos/
// burgund variants were near-duplicates of the default; fewer, more distinct choices.
export const BACKGROUNDS: Background[] = ["vines", "vines-smaragd", "vines-espresso", "none"];

export function detectBackground(): Background {
  const v = localStorage.getItem("pp_bg") ?? "";
  // Legacy values from the 7-variant era fall back to the forest default (not "none" —
  // those users HAD a vines wallpaper and should keep one).
  return (BACKGROUNDS as string[]).includes(v) ? (v as Background) : "vines";
}

interface ThemeCtx {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggle: () => void;
  background: Background;
  setBackground: (b: Background) => void;
}

const Ctx = createContext<ThemeCtx | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(detectTheme);
  const [background, setBgState] = useState<Background>(detectBackground);
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    // Keep the Android toolbar / standalone status-bar colour in sync with the active theme so a
    // light-theme user no longer gets a mismatched dark toolbar (M: dynamic theme-color).
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", theme === "light" ? "#f3efe2" : "#0d2018");
  }, [theme]);
  useEffect(() => {
    document.documentElement.setAttribute("data-bg", background);
  }, [background]);
  const setTheme = useCallback((t: Theme) => {
    localStorage.setItem("pp_theme", t);
    setThemeState(t);
  }, []);
  const toggle = useCallback(() => {
    setThemeState((prev) => {
      const next: Theme = prev === "dark" ? "light" : "dark";
      localStorage.setItem("pp_theme", next);
      return next;
    });
  }, []);
  const setBackground = useCallback((b: Background) => {
    localStorage.setItem("pp_bg", b);
    setBgState(b);
  }, []);
  const value = useMemo(
    () => ({ theme, setTheme, toggle, background, setBackground }),
    [theme, setTheme, toggle, background, setBackground],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useTheme(): ThemeCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
