ALTER TABLE installs ADD COLUMN reinstall_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE installs ADD COLUMN last_installed_at TEXT;
UPDATE schema_version SET version = 2;
