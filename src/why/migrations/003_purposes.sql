CREATE TABLE purposes (
  key        TEXT PRIMARY KEY,
  label      TEXT NOT NULL,
  color      TEXT NOT NULL DEFAULT '#6b7280',
  sort_order INTEGER NOT NULL DEFAULT 0,
  built_in   INTEGER NOT NULL DEFAULT 0
);

INSERT INTO purposes(key, label, color, sort_order, built_in) VALUES
  ('doc',          'Reference',     '#2563eb', 1, 1),
  ('setup',        'Project setup', '#16a34a', 2, 1),
  ('experimental', 'Trying out',    '#d97706', 3, 1),
  ('remove',       'Cleanup soon',  '#dc2626', 4, 1),
  ('ignore',       'Ignore',        '#6b7280', 5, 1);
