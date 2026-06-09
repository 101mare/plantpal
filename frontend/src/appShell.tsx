import { createContext, useContext, type Dispatch, type SetStateAction } from "react";
import type { SprossMood, Stage } from "./status";

/** Live mood-mirror snapshot the persistent TabBar reads to render the central Spross sprite.
 *  Pushed by PlantdexPage (full live mood/stage/skin/vacation + reaction nonces) and SettingsPage
 *  (vacation toggle). Seeded from the persisted store in AppShell so the medallion is never empty,
 *  even on a cold start landing directly on /stats or /settings. */
export interface SprossMirror {
  mood: SprossMood;
  stage: Stage;
  skin: string | null;
  vacation: boolean;
  reactNonce: number;
  riseNonce: number;
  bloomNonce: number;
}

export interface AppShellCtx {
  spross: SprossMirror;
  setSpross: Dispatch<SetStateAction<SprossMirror>>;
  /** Opens the persistent Add-Plant sheet (lifted into AppShell so the ➕ tab works on every route). */
  openAdd: () => void;
}

/** Leaf module (no Page-/App-imports) so App.tsx, TabBar, PlantdexPage and SettingsPage can all
 *  import the context without a circular dependency. */
export const AppShellContext = createContext<AppShellCtx | null>(null);

export function useAppShell(): AppShellCtx {
  const c = useContext(AppShellContext);
  if (!c) throw new Error("useAppShell must be used within AppShell");
  return c;
}
