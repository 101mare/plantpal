export interface Plant {
  id: number;
  name: string;
  interval_days: number;
  image_url: string | null;
  last_watered_at: string;
  created_at: string;
  notes: string | null;
  water_amount_ml: number | null;
  is_thirsty: boolean;
  days_overdue: number;
}

export interface Me {
  id: number;
  email: string;
  is_admin: boolean;
}

export interface UserSettings {
  email: string;
  email_reminders_enabled: boolean;
  reminder_channel: string;
}

export interface Stats {
  total_plants: number;
  thirsty_count: number;
}

export interface ApiError {
  error: { code: string; message: string };
}
