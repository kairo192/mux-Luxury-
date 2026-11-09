-- Tracking table for the versioned-migration runner.
-- The runner creates this itself on first run; the file exists so a fresh
-- repository check has at least one versioned migration to apply against,
-- and so the `schema_migrations` relation shows up in a schema dump.
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    filename    TEXT NOT NULL,
    checksum    TEXT NOT NULL,
    applied_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    duration_ms INTEGER NOT NULL DEFAULT 0
);
