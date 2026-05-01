-- Migration 004: command history ring buffer
-- Stores the last N shell commands that ran before each install event.
CREATE TABLE IF NOT EXISTS command_history (
    id          INTEGER PRIMARY KEY,
    install_id  INTEGER NOT NULL REFERENCES installs(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,   -- 0 = oldest, N-1 = most recent before install
    command     TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_command_history_install
    ON command_history(install_id, position);
