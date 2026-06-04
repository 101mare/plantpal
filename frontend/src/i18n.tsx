import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import type { Locale } from "./types";
import { ApiError } from "./api";

// Dependency-free i18n (no i18next): a small dict + t() with {var} interpolation.
const resources: Record<Locale, Record<string, string>> = {
  de: {
    "app.loading": "Lädt…",
    "nav.plantdex": "Mein Plantdex",
    "nav.stats": "Statistik",
    "nav.settings": "Einstellungen",
    "nav.add": "Pflanze +",
    "nav.back": "Zurück",
    "thirsty.title": "Durstige Pflanzen!",
    "thirsty.allWatered": "🌿 Alles gewässert!",
    "plant.water": "Gießen",
    "plant.edit": "Bearbeiten",
    "plant.delete": "Löschen",
    "plant.save": "Speichern",
    "plant.cancel": "Abbrechen",
    "plant.deleted": "Pflanze gelöscht",
    "plant.undo": "Rückgängig",
    "plant.restored": "Wiederhergestellt",
    "plant.name": "Name",
    "plant.interval": "Intervall (Tage)",
    "plant.notes": "Notizen",
    "plant.amount": "Wassermenge (ml)",
    "plant.room": "Standort/Raum",
    "plant.photo": "Foto",
    "plant.replacePhoto": "Foto ersetzen",
    "plant.lastWatered": "Zuletzt gegossen",
    "plant.status": "Status",
    "plant.overdue": "{n} Tage überfällig",
    "plant.ok": "✅ ok",
    "plant.everyDays": "Alle {n} Tage",
    "list.search": "Suchen…",
    "list.sort.thirsty": "Durst zuerst",
    "list.sort.name": "Name",
    "list.sort.recent": "Zuletzt gegossen",
    "list.filter.thirsty": "Nur durstige",
    "empty.title": "Noch keine Pflanzen",
    "empty.hint": "Tippe auf Pflanze + um deine erste Pflanze einzutragen.",
    "empty.cta": "Erste Pflanze anlegen",
    "login.title": "Bei PlantPal anmelden",
    "login.email": "Email-Adresse",
    "login.sendLink": "Login-Link senden",
    "login.checkInbox": "Schau in dein Postfach – Link und Code sind unterwegs.",
    "login.haveCode": "Ich habe einen Code erhalten",
    "login.codeTitle": "Code eingeben",
    "login.code": "6-stelliger Code",
    "login.verify": "Anmelden",
    "stats.totalPlants": "Pflanzen",
    "stats.thirsty": "Durstig",
    "stats.streak": "Gieß-Streak (Tage)",
    "stats.consistency": "Gieß-Konsistenz",
    "stats.longestOverdue": "Am längsten überfällig",
    "stats.none": "—",
    "settings.title": "Einstellungen",
    "settings.account": "Angemeldet als",
    "settings.emailReminders": "Email-Erinnerungen erhalten",
    "settings.reminderHour": "Erinnerungs-Uhrzeit (Berlin)",
    "settings.language": "Sprache",
    "settings.theme": "Design",
    "settings.theme.dark": "Dunkel",
    "settings.theme.light": "Hell",
    "settings.invites": "Einladungen",
    "settings.inviteQuota": "Verbleibendes Kontingent: {n}",
    "settings.createInvite": "Einladungs-Link erstellen",
    "settings.inviteUses": "Nutzungen",
    "settings.revoke": "Widerrufen",
    "settings.copy": "Kopieren",
    "settings.copied": "Kopiert!",
    "settings.changeEmail": "Email-Adresse ändern",
    "settings.newEmail": "Neue Email-Adresse",
    "settings.sendVerify": "Bestätigung senden",
    "settings.emailChangeSent": "Bestätigungs-Mail an die neue Adresse gesendet.",
    "settings.export": "Meine Daten exportieren",
    "settings.logout": "Abmelden",
    "settings.deleteAccount": "Account vollständig löschen",
    "settings.deleteConfirm": "Account und alle Daten unwiderruflich löschen?",
    "plant.added": "Pflanze hinzugefügt 🌱",
    "plant.photoRequired": "Bitte ein Foto auswählen.",
    "plant.watered": "Gegossen 💧",
    "plant.photoReplaced": "Foto ersetzt",
    "plant.saved": "Gespeichert",
    "status.ok": "Aktuell",
    "status.soon": "Bald fällig",
    "date.today": "heute",
    "date.yesterday": "gestern",
    "date.daysAgo": "vor {n} Tagen",
    "list.noResults": "Keine Treffer.",
    "list.resetFilters": "Filter zurücksetzen",
    "stats.empty.title": "Noch keine Statistik",
    "stats.empty.hint": "Lege Pflanzen an und gieße sie, um hier deinen Fortschritt zu sehen.",
    "settings.saved": "Gespeichert",
    "login.wrongEmail": "Andere Email-Adresse verwenden",
    "a11y.skip": "Zum Inhalt springen",
    "register.title": "Account erstellen",
    "register.noToken":
      "Ungültiger oder fehlender Einladungs-Link. Bitte fordere eine neue Einladung an.",
    "register.done": "Account erstellt! Wir haben dir einen Login-Link geschickt.",
    "register.toLogin": "Zum Login",
    "register.email": "Email-Adresse",
    "register.submit": "Account erstellen",
    "register.submitting": "Erstelle…",
    "register.failed": "Registrierung fehlgeschlagen.",
    "error.code.rate_limited": "Zu viele Versuche. Bitte etwas später erneut probieren.",
    "error.code.unauthenticated": "Nicht angemeldet. Bitte melde dich erneut an.",
    "error.code.forbidden": "Dazu hast du keine Berechtigung.",
    "error.code.csrf_failed": "Sicherheitsprüfung fehlgeschlagen. Bitte lade die Seite neu.",
    "error.code.validation_error": "Bitte überprüfe deine Eingaben.",
    "error.code.not_found": "Nicht gefunden.",
    "error.code.invite_quota_exceeded": "Dein Einladungs-Kontingent ist aufgebraucht.",
    "error.generic": "Etwas ist schiefgelaufen.",
    "error.retry": "Erneut versuchen",
  },
  en: {
    "app.loading": "Loading…",
    "nav.plantdex": "My Plantdex",
    "nav.stats": "Stats",
    "nav.settings": "Settings",
    "nav.add": "Add Plant",
    "nav.back": "Back",
    "thirsty.title": "Thirsty Plants!",
    "thirsty.allWatered": "🌿 All watered!",
    "plant.water": "Water",
    "plant.edit": "Edit",
    "plant.delete": "Delete",
    "plant.save": "Save",
    "plant.cancel": "Cancel",
    "plant.deleted": "Plant deleted",
    "plant.undo": "Undo",
    "plant.restored": "Restored",
    "plant.name": "Name",
    "plant.interval": "Interval (days)",
    "plant.notes": "Notes",
    "plant.amount": "Water amount (ml)",
    "plant.room": "Location/Room",
    "plant.photo": "Photo",
    "plant.replacePhoto": "Replace photo",
    "plant.lastWatered": "Last watered",
    "plant.status": "Status",
    "plant.overdue": "{n} days overdue",
    "plant.ok": "✅ ok",
    "plant.everyDays": "Every {n} days",
    "list.search": "Search…",
    "list.sort.thirsty": "Thirsty first",
    "list.sort.name": "Name",
    "list.sort.recent": "Recently watered",
    "list.filter.thirsty": "Thirsty only",
    "empty.title": "No plants yet",
    "empty.hint": 'Tap "Add Plant" to register your first plant.',
    "empty.cta": "Add your first plant",
    "login.title": "Sign in to PlantPal",
    "login.email": "Email address",
    "login.sendLink": "Send sign-in link",
    "login.checkInbox": "Check your inbox – link and code are on the way.",
    "login.haveCode": "I received a code",
    "login.codeTitle": "Enter code",
    "login.code": "6-digit code",
    "login.verify": "Sign in",
    "stats.totalPlants": "Plants",
    "stats.thirsty": "Thirsty",
    "stats.streak": "Watering streak (days)",
    "stats.consistency": "Watering consistency",
    "stats.longestOverdue": "Longest overdue",
    "stats.none": "—",
    "settings.title": "Settings",
    "settings.account": "Signed in as",
    "settings.emailReminders": "Receive email reminders",
    "settings.reminderHour": "Reminder time (Berlin)",
    "settings.language": "Language",
    "settings.theme": "Theme",
    "settings.theme.dark": "Dark",
    "settings.theme.light": "Light",
    "settings.invites": "Invites",
    "settings.inviteQuota": "Remaining quota: {n}",
    "settings.createInvite": "Create invite link",
    "settings.inviteUses": "uses",
    "settings.revoke": "Revoke",
    "settings.copy": "Copy",
    "settings.copied": "Copied!",
    "settings.changeEmail": "Change email address",
    "settings.newEmail": "New email address",
    "settings.sendVerify": "Send confirmation",
    "settings.emailChangeSent": "Confirmation email sent to the new address.",
    "settings.export": "Export my data",
    "settings.logout": "Log out",
    "settings.deleteAccount": "Delete account permanently",
    "settings.deleteConfirm": "Permanently delete the account and all data?",
    "plant.added": "Plant added 🌱",
    "plant.photoRequired": "Please select a photo.",
    "plant.watered": "Watered 💧",
    "plant.photoReplaced": "Photo replaced",
    "plant.saved": "Saved",
    "status.ok": "Healthy",
    "status.soon": "Due soon",
    "date.today": "today",
    "date.yesterday": "yesterday",
    "date.daysAgo": "{n} days ago",
    "list.noResults": "No matches.",
    "list.resetFilters": "Reset filters",
    "stats.empty.title": "No stats yet",
    "stats.empty.hint": "Add plants and water them to see your progress here.",
    "settings.saved": "Saved",
    "login.wrongEmail": "Use a different email address",
    "a11y.skip": "Skip to content",
    "register.title": "Create account",
    "register.noToken": "Invalid or missing invite link. Please request a new invite.",
    "register.done": "Account created! We've sent you a sign-in link.",
    "register.toLogin": "Go to sign-in",
    "register.email": "Email address",
    "register.submit": "Create account",
    "register.submitting": "Creating…",
    "register.failed": "Registration failed.",
    "error.code.rate_limited": "Too many attempts. Please try again later.",
    "error.code.unauthenticated": "Not signed in. Please sign in again.",
    "error.code.forbidden": "You don't have permission to do that.",
    "error.code.csrf_failed": "Security check failed. Please reload the page.",
    "error.code.validation_error": "Please check your input.",
    "error.code.not_found": "Not found.",
    "error.code.invite_quota_exceeded": "You've used up your invite quota.",
    "error.generic": "Something went wrong.",
    "error.retry": "Try again",
  },
};

export function detectLocale(): Locale {
  const stored = localStorage.getItem("pp_locale");
  if (stored === "de" || stored === "en") return stored;
  return navigator.language.toLowerCase().startsWith("de") ? "de" : "en";
}

type TFn = (key: string, vars?: Record<string, string | number>) => string;
interface I18nCtx {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: TFn;
}

const Ctx = createContext<I18nCtx | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(detectLocale);
  const setLocale = useCallback((l: Locale) => {
    localStorage.setItem("pp_locale", l);
    document.documentElement.lang = l;
    setLocaleState(l);
  }, []);
  const t = useCallback<TFn>(
    (key, vars) => {
      let s = resources[locale][key] ?? resources.de[key] ?? key;
      if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
      return s;
    },
    [locale],
  );
  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n(): I18nCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}

/** Localize an ApiError by its stable `code` (server messages are English/internal — API-09),
 *  falling back to the server message for codes we don't translate. */
export function errorText(err: unknown, t: TFn): string {
  if (err instanceof ApiError) {
    const key = `error.code.${err.code}`;
    const msg = t(key);
    return msg === key ? err.message : msg;
  }
  return t("error.generic");
}
