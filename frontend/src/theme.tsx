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

export const BACKGROUNDS: Background[] = [
  "vines",
  "vines-tiefsee",
  "vines-tanne",
  "vines-moos",
  "vines-smaragd",
  "vines-espresso",
  "vines-burgund",
  "none",
];

export function detectBackground(): Background {
  const v = localStorage.getItem("pp_bg") ?? "";
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
