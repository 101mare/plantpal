-- PlantPal initial schema. Datetimes are naive Berlin (ISO-8601, no tz suffix).

CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  is_admin INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
  email_reminders_enabled INTEGER NOT NULL DEFAULT 1,
  reminder_channel TEXT NOT NULL DEFAULT 'email'
      CHECK (reminder_channel IN ('email', 'instagram', 'both')),  -- M2 forward-compat
  reminder_last_sent_date TEXT,
  created_at TEXT NOT NULL,
  last_login_at TEXT
);

CREATE INDEX idx_users_reminder_due ON users(email_reminders_enabled, reminder_last_sent_date);

CREATE TABLE invite_tokens (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token_hash TEXT NOT NULL UNIQUE,
  email_hint TEXT,
  created_by_user_id INTEGER,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  used_at TEXT,
  used_by_user_id INTEGER,
  revoked_at TEXT,
  FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (used_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_invites_unused ON invite_tokens(expires_at) WHERE used_at IS NULL AND revoked_at IS NULL;

CREATE TABLE login_tokens (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token_hash TEXT NOT NULL UNIQUE,
  email TEXT NOT NULL COLLATE NOCASE,
  user_id INTEGER,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  used_at TEXT,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_login_tokens_email ON login_tokens(email, created_at);
CREATE INDEX idx_login_tokens_expiry ON login_tokens(expires_at) WHERE used_at IS NULL;

CREATE TABLE sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_hash TEXT NOT NULL UNIQUE,
  user_id INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  hard_expires_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  renewed_at TEXT NOT NULL,
  revoked_at TEXT,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_sessions_user ON sessions(user_id);

CREATE TABLE plants (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  interval_days INTEGER NOT NULL CHECK (interval_days BETWEEN 1 AND 365),
  -- Nullable by design: a plant row is inserted first to obtain its id, then the
  -- image is processed and image_path is set within the same create request.
  -- The API requires an image at create time; null only exists transiently.
  image_path TEXT,
  last_watered_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 1,
  notes TEXT,
  water_amount_ml INTEGER
      CHECK (water_amount_ml IS NULL OR water_amount_ml BETWEEN 1 AND 5000),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_plants_user_active ON plants(user_id) WHERE is_active = 1;

CREATE TABLE reminder_send_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  reminder_date TEXT NOT NULL,
  channel TEXT NOT NULL DEFAULT 'email',
  status TEXT NOT NULL CHECK (status IN ('sent', 'failed', 'skipped', 'sending')),
  error_message TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  UNIQUE (user_id, reminder_date, channel)
);

CREATE TABLE rate_limits (
  key TEXT NOT NULL,
  window_start INTEGER NOT NULL,
  count INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  PRIMARY KEY (key, window_start)
);

CREATE INDEX idx_rate_limits_expires ON rate_limits(expires_at);
