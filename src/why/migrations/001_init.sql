CREATE TABLE users (
  id            TEXT PRIMARY KEY,
  email         TEXT,
  display_name  TEXT,
  created_at    TEXT NOT NULL
);

CREATE TABLE devices (
  id            TEXT PRIMARY KEY,
  hostname      TEXT NOT NULL,
  label         TEXT,
  created_at    TEXT NOT NULL,
  last_seen_at  TEXT NOT NULL
);

CREATE TABLE projects (
  name          TEXT PRIMARY KEY,
  created_at    TEXT NOT NULL
);

CREATE TABLE installs (
  id                 INTEGER PRIMARY KEY,
  sync_id            TEXT NOT NULL UNIQUE,
  user_id            TEXT NOT NULL REFERENCES users(id),
  device_id          TEXT NOT NULL REFERENCES devices(id),
  command            TEXT NOT NULL,
  package_name       TEXT,
  manager            TEXT NOT NULL,
  install_dir        TEXT NOT NULL,
  resolved_path      TEXT,
  installed_at       TEXT NOT NULL,
  exit_code          INTEGER NOT NULL,
  display_name       TEXT,
  what_it_does       TEXT,
  project            TEXT,
  why                TEXT,
  disposition        TEXT,
  notes              TEXT,
  source_url         TEXT,
  metadata_complete  INTEGER NOT NULL DEFAULT 0,
  reviewed_at        TEXT,
  removed_at         TEXT,
  updated_at         TEXT NOT NULL,
  deleted            INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX installs_disposition ON installs(disposition);
CREATE INDEX installs_project     ON installs(project);
CREATE INDEX installs_manager     ON installs(manager);
CREATE INDEX installs_installed   ON installs(installed_at);
CREATE INDEX installs_device      ON installs(device_id);
CREATE INDEX installs_complete    ON installs(metadata_complete);

CREATE VIRTUAL TABLE installs_fts USING fts5(
  display_name, package_name, command, what_it_does, project, why, notes,
  content='installs', content_rowid='id'
);

CREATE TRIGGER installs_ai AFTER INSERT ON installs BEGIN
  INSERT INTO installs_fts(rowid, display_name, package_name, command, what_it_does, project, why, notes)
  VALUES (new.id, new.display_name, new.package_name, new.command, new.what_it_does, new.project, new.why, new.notes);
END;

CREATE TRIGGER installs_ad AFTER DELETE ON installs BEGIN
  INSERT INTO installs_fts(installs_fts, rowid, display_name, package_name, command, what_it_does, project, why, notes)
  VALUES ('delete', old.id, old.display_name, old.package_name, old.command, old.what_it_does, old.project, old.why, old.notes);
END;

CREATE TRIGGER installs_au AFTER UPDATE ON installs BEGIN
  INSERT INTO installs_fts(installs_fts, rowid, display_name, package_name, command, what_it_does, project, why, notes)
  VALUES ('delete', old.id, old.display_name, old.package_name, old.command, old.what_it_does, old.project, old.why, old.notes);
  INSERT INTO installs_fts(rowid, display_name, package_name, command, what_it_does, project, why, notes)
  VALUES (new.id, new.display_name, new.package_name, new.command, new.what_it_does, new.project, new.why, new.notes);
END;

CREATE TABLE schema_version (version INTEGER NOT NULL);
INSERT INTO schema_version(version) VALUES (1);
