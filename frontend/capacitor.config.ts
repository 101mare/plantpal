import type { CapacitorConfig } from "@capacitor/cli";

/**
 * PlantPal iOS shell (Guideline 2.5.2: SELF-CONTAINED — the Vite build is bundled, never
 * loaded from a remote server.url; only API calls leave the app, to BASE_URL/getplantpal.com).
 * Build for iOS:  npm run build && npx cap sync ios   (API base: VITE_API_BASE, see api.ts)
 */
const config: CapacitorConfig = {
  appId: "com.getplantpal.app",
  appName: "PlantPal",
  webDir: "dist",
  ios: {
    contentInset: "never", // the app handles safe areas itself (env(safe-area-inset-*))
    backgroundColor: "#0d2018",
  },
};

export default config;
