-- v2 Spross evolution: a DURABLE, server-side high-water-mark for the mascot's evolution stage.
-- localStorage alone cannot promise "the stage never downgrades" — iOS PWA storage eviction
-- (WebKit ITP after ~7 days of no interaction, the exact cadence of a watering app), a cleared
-- cache, a new device, or private mode all wipe it. The user row therefore holds the real
-- high-water-mark; both columns are max-ratcheted server-side and only ever climb.
ALTER TABLE users ADD COLUMN vitality_stage_max INTEGER NOT NULL DEFAULT 1
    CHECK (vitality_stage_max BETWEEN 1 AND 6);
ALTER TABLE users ADD COLUMN spross_peak_vitality INTEGER NOT NULL DEFAULT 0
    CHECK (spross_peak_vitality BETWEEN 0 AND 100);
