-- Migration 005: index on removed_at for efficient "show removed" filter queries.
-- (removed_at column was present in the initial schema; this migration adds the index.)
CREATE INDEX IF NOT EXISTS installs_removed ON installs(removed_at);
