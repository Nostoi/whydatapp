# Changelog

All notable changes to whydatApp are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [SemVer](https://semver.org/).

---

## [1.5.0] — 2026-05-01

### Changed
- Renamed "Disposition" → "Purpose" everywhere user-visible: CLI prompt,
  `why list` column header, `--purpose` filter flag (was `--disposition`),
  all web templates (table header, edit form, review form, bulk-action bar,
  dashboard card, filter aria-label), and all docs.
- Updated default purpose labels in `presentation.toml`:
  `doc` → "Reference", `setup` → "Project setup",
  `experimental` → "Trying out", `remove` → "Cleanup soon".
  Stored DB values (`doc`, `setup`, etc.) are unchanged — no migration needed.
- `why list` timestamps now show `YYYY-MM-DD HH:MM` instead of ISO 8601.
- `why list` now includes a "Run from" column (`install_dir`).
- Web table `installed_at` column now shows `HH:MM` alongside the date.
- Web edit panel now shows read-only "Run from", "Installed to (best-effort)",
  and formatted timestamp below the form fields.

### Added
- `gh repo clone` tracking: `gh` added to `resolve.py` (resolves cloned
  directory under `cwd`, same logic as `git`). Previously `gh` was detected
  and captured but its install path was never resolved.

---

## [1.4.0] — 2026-04-30

> Version 1.4.0 was incorporated into 1.5.0 before a standalone release.
> The `gh` detection work (detect.py, init_wizard.py, config.py,
> presentation.toml, tests) shipped together with the Purpose rename above.

### Added
- `gh repo clone` detection and capture (`_extract_gh_clone` in `detect.py`).
- `gh` added to Tier-1 manager list in `init_wizard.py` and default config.
- `[gh]` presentation entry in `presentation.toml`.

---

## [1.3.3] — 2026-04-30

### Fixed
- Install row hover state stuck highlighted after closing the edit modal.
- Installs page interactions (row click, modal open/close) broken in certain
  browsers after the pass-4 frontend rewrite.
- `why` bare invocation (no subcommand) showed an unhelpful error instead of
  the help text.
- CI test failure introduced by frontend pass 4.

---

## [1.3.0] — 2026-04-30

### Added
- Re-install enrichment: when a package that already has a record is installed
  again, whydatApp prompts only for any missing fields and increments
  `reinstall_count` / updates `last_installed_at` rather than creating a
  duplicate row.
- Opt-in shell reload (`exec $SHELL -l`) at the end of `why init` so the hook
  is active immediately without a manual restart.

### Changed
- Frontend pass 4: tabs on the installs page (All / Incomplete / by manager),
  sort indicators, action-reveal on row hover, bulk disposition bar,
  bent-corner detail expand.
- Frontend pass 5: fixed badge HTML escaping, modal edit wiring, self-install
  filter (hides the `why` package itself from the default list).
- Design system: token-based color palette, brand colors, primitive component
  layer (`btn`, `input`, `select`, `card`).
- Typography: Plus Jakarta Sans, tightened spacing, responsive layout.

### Fixed
- Docs: corrected `uv tool install` source-install command (uv rejects
  `--from` combined with a bare package name).

---

## [1.2.0] — 2026-04-30

### Changed
- Full frontend polish: typography, spacing, color tokens, table layout,
  pill component, responsive grid. Matches the v1.2.0 design spec.

---

## [1.1.3] — 2026-04-30

### Changed
- Pre-commit hook automatically rebuilds `tailwind.css` when templates or
  `tailwind.src.css` change, preventing stale CSS from shipping. See
  `scripts/rebuild-css-if-templates-changed.sh`.

---

## [1.1.2] — 2026-04-30

### Fixed
- Tailwind CSS was not rebuilt before the 1.1.0/1.1.1 releases; utility
  classes added in new templates were silently absent in the browser.
- `WHY_SUPPRESS=1` env var was being checked in the Python hook runner
  instead of only in the shell wrapper, causing the hook to no-op when
  run via `CliRunner` in tests and in some shell configurations.

---

## [1.1.0] — 2026-04-30

### Added
- `why serve` startup banner showing all reachable URLs (localhost + LAN).
- `--lan` flag on `why serve` to bind to `0.0.0.0` for local network access.

---

## [1.0.5] — 2026-04-30

### Changed
- README updated to lead with `uv tool install` (PyPI) instead of source
  install; all links made absolute for PyPI rendering.
- Added MIT license badge and LICENSE file reference.

---

## [1.0.4] — 2026-04-29

### Fixed
- CI release workflow: removed redundant `uv venv` step that caused the
  PyPI publish job to fail.

---

## [1.0.3] — 2026-04-29

### Added
- GitHub Actions release workflow: builds wheel + sdist, publishes to PyPI
  on version tags, uploads release assets.

---

## [1.0.2] — 2026-04-29

### Added
- Comprehensive user-facing docs under `docs/guide/` (install, usage, web UI,
  configuration, troubleshooting, development).

---

## [1.0.1] — 2026-04-29

### Fixed
- Dark-mode logo had a white background; replaced with transparent PNG.

---

## [1.0.0] — 2026-04-29

Initial public release.

### Added
- Shell hook (zsh / bash / fish) — captures every install command silently
  in the background via `why _hook`.
- `why init` wizard — detects shell, installs hook into rc file, configures
  Tier-1 managers, sets up autostart, optionally reloads shell.
- `why uninstall` — removes hook, autostart unit, and optionally all data.
- `why log` — interactive capture for commands not caught by the hook.
- `why list` — tabular view of recorded installs with filters.
- `why review` — focused one-at-a-time form to drain the skipped queue.
- `why export` — export to Markdown or JSON, filterable by purpose/project.
- `why serve` — boots the web UI and opens it in the browser.
- Web UI: installs table with HTMX live filters, inline edit panel, bulk
  disposition action, dashboard (by purpose / manager / project / month /
  stale queue), browser review flow, share and export endpoints.
- Autostart: `launchd` plist (macOS) and `systemd --user` unit (Linux).
- SQLite-backed store with automatic schema migrations and pre-migration
  backups.
- `presentation.toml` for per-manager and per-purpose icon/color/label
  customization.
- CSRF protection on all mutating web endpoints.

[1.5.0]: https://github.com/Nostoi/whydatapp/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/Nostoi/whydatapp/compare/v1.3.3...v1.4.0
[1.3.3]: https://github.com/Nostoi/whydatapp/compare/v1.3.0...v1.3.3
[1.3.0]: https://github.com/Nostoi/whydatapp/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/Nostoi/whydatapp/compare/v1.1.3...v1.2.0
[1.1.3]: https://github.com/Nostoi/whydatapp/compare/v1.1.2...v1.1.3
[1.1.2]: https://github.com/Nostoi/whydatapp/compare/v1.1.0...v1.1.2
[1.1.0]: https://github.com/Nostoi/whydatapp/compare/v1.0.5...v1.1.0
[1.0.5]: https://github.com/Nostoi/whydatapp/compare/v1.0.4...v1.0.5
[1.0.4]: https://github.com/Nostoi/whydatapp/compare/v1.0.3...v1.0.4
[1.0.3]: https://github.com/Nostoi/whydatapp/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/Nostoi/whydatapp/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/Nostoi/whydatapp/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/Nostoi/whydatapp/releases/tag/v1.0.0
