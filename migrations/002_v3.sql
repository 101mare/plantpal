-- PlantPal migration 002 (v3). Extends the M1 baseline (001_initial.sql).
-- Datetimes are naive Berlin (ISO-8601, no tz suffix), set by Python (never
-- CURRENT_TIMESTAMP). Tracked exactly once in _migrations; idempotency comes from
-- the tracker (K9), so the bare ALTER ADD COLUMN statements run exactly once.
-- Runner constraints (F-DB-14): every statement ends with ';', no triggers,
-- no BEGIN/COMMIT, no ';' inside string literals or comments.

-- 1. Watering history (F-HIST-1..8)
CREATE TABLE IF NOT EXISTS waterings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plant_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  watered_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (plant_id) REFERENCES plants(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_waterings_plant ON waterings(plant_id, watered_at DESC);
CREATE INDEX IF NOT EXISTS idx_waterings_user ON waterings(user_id, watered_at DESC);

-- 2. Plant location/room (F-LOC-1)
ALTER TABLE plants ADD COLUMN location_room TEXT;

-- 3. User preferences (F-DB-6..8): invite quota, locale, reminder hour, theme
ALTER TABLE users ADD COLUMN invite_quota INTEGER NOT NULL DEFAULT 3 CHECK (invite_quota >= 0);
ALTER TABLE users ADD COLUMN locale TEXT NOT NULL DEFAULT 'de' CHECK (locale IN ('de', 'en'));
ALTER TABLE users ADD COLUMN reminder_hour INTEGER NOT NULL DEFAULT 8 CHECK (reminder_hour BETWEEN 0 AND 23);
ALTER TABLE users ADD COLUMN theme TEXT NOT NULL DEFAULT 'dark' CHECK (theme IN ('dark', 'light'));

-- 4. Multi-use invite links (F-AUTH-13..18, K2). used_at now means "exhausted".
ALTER TABLE invite_tokens ADD COLUMN max_uses INTEGER NOT NULL DEFAULT 1 CHECK (max_uses >= 1);
ALTER TABLE invite_tokens ADD COLUMN used_count INTEGER NOT NULL DEFAULT 0 CHECK (used_count >= 0);
UPDATE invite_tokens SET used_count = 1 WHERE used_at IS NOT NULL;

-- 5. Invite redemptions (F-DB-10)
CREATE TABLE IF NOT EXISTS invite_redemptions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  invite_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  redeemed_at TEXT NOT NULL,
  FOREIGN KEY (invite_id) REFERENCES invite_tokens(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  UNIQUE (invite_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_invite_redemptions_invite ON invite_redemptions(invite_id);
CREATE INDEX IF NOT EXISTS idx_invites_by_creator ON invite_tokens(created_by_user_id) WHERE revoked_at IS NULL;

-- 6. Login-code alternative (F-AUTH-19..25, K1). code_hash is the HMAC of the
-- 6-digit code, never plaintext. NULL for M1 tokens.
ALTER TABLE login_tokens ADD COLUMN code_hash TEXT;
ALTER TABLE login_tokens ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_login_tokens_code ON login_tokens(email, expires_at) WHERE used_at IS NULL AND code_hash IS NOT NULL;

-- 7. Email-change requests (F-AUTH-28..32, K1: code_hash NOT NULL + attempt_count)
CREATE TABLE IF NOT EXISTS email_change_requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  new_email TEXT NOT NULL COLLATE NOCASE,
  token_hash TEXT NOT NULL UNIQUE,
  code_hash TEXT NOT NULL,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  expires_at TEXT NOT NULL,
  used_at TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_email_change_user ON email_change_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_email_change_unused ON email_change_requests(expires_at) WHERE used_at IS NULL;
