-- Migration 006: task sessions, command journal, and LLM summaries

CREATE TABLE IF NOT EXISTS task_sessions (
  id             INTEGER PRIMARY KEY,
  sync_id        TEXT NOT NULL UNIQUE,
  user_id        TEXT NOT NULL REFERENCES users(id),
  device_id      TEXT NOT NULL REFERENCES devices(id),
  title          TEXT,
  project        TEXT,
  source         TEXT NOT NULL,
  status         TEXT NOT NULL,
  shell          TEXT,
  started_at     TEXT NOT NULL,
  ended_at       TEXT,
  cwd_start      TEXT,
  cwd_end        TEXT,
  summary_status TEXT NOT NULL DEFAULT 'none',
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL,
  deleted        INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_task_sessions_status
  ON task_sessions(status, summary_status, started_at);
CREATE INDEX IF NOT EXISTS idx_task_sessions_project
  ON task_sessions(project, started_at);

CREATE TABLE IF NOT EXISTS task_session_commands (
  id                 INTEGER PRIMARY KEY,
  session_id         INTEGER NOT NULL REFERENCES task_sessions(id) ON DELETE CASCADE,
  position           INTEGER NOT NULL,
  command            TEXT NOT NULL,
  cwd                TEXT NOT NULL,
  exit_code          INTEGER,
  started_at         TEXT NOT NULL,
  ended_at           TEXT,
  matched_install_id INTEGER REFERENCES installs(id),
  redaction_version  INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_task_session_commands_session
  ON task_session_commands(session_id, position);

CREATE TABLE IF NOT EXISTS task_session_summaries (
  id               INTEGER PRIMARY KEY,
  session_id       INTEGER NOT NULL REFERENCES task_sessions(id) ON DELETE CASCADE,
  provider         TEXT NOT NULL,
  model            TEXT NOT NULL,
  endpoint         TEXT,
  prompt_version   INTEGER NOT NULL,
  input_hash       TEXT NOT NULL,
  summary_markdown TEXT NOT NULL,
  created_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_task_session_summaries_session
  ON task_session_summaries(session_id, created_at DESC);

CREATE TABLE IF NOT EXISTS command_journal (
  id        INTEGER PRIMARY KEY,
  command   TEXT NOT NULL,
  cwd       TEXT NOT NULL,
  shell     TEXT,
  exit_code INTEGER,
  ran_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_command_journal_ran_at
  ON command_journal(ran_at DESC);
