export interface Plant {
  id: number;
  name: string;
  interval_days: number;
  image_url: string | null;
  last_watered_at: string;
  created_at: string;
  notes: string | null;
  water_amount_ml: number | null;
  location_room: string | null;
  is_thirsty: boolean;
  days_overdue: number;
}

export interface Me {
  id: number;
  email: string;
  is_admin: boolean;
}

export type Locale = "de" | "en";
export type Theme = "dark" | "light";
export type Background = "vines" | "night" | "jungle" | "greenhouse" | "none";

export interface UserSettings {
  email: string;
  email_reminders_enabled: boolean;
  reminder_channel: string;
  locale: Locale;
  reminder_hour: number;
  theme: Theme;
  invite_quota: number;
  is_admin: boolean;
}

export interface SettingsPatch {
  email_reminders_enabled?: boolean;
  locale?: Locale;
  reminder_hour?: number;
  theme?: Theme;
}

interface LongestOverdue {
  plant_id: number;
  name: string;
  days_overdue: number;
}

export interface Stats {
  total_plants: number;
  thirsty_count: number;
  watering_streak_days: number;
  watering_consistency_pct: number;
  longest_overdue: LongestOverdue | null;
  avg_interval_days: number | null;
  avg_configured_interval_days: number | null;
}

export interface InviteListItem {
  id: number;
  max_uses: number;
  used_count: number;
  expires_at: string;
  revoked_at: string | null;
  created_at: string;
  status: "active" | "exhausted" | "expired" | "revoked";
}

export interface InviteCreated {
  invite_url: string;
  expires_at: string;
  max_uses: number;
  used_count: number;
  remaining_quota: number;
}
