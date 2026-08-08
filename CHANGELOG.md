# Changelog

All notable changes to whydatApp are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [SemVer](https://semver.org/).

---

## [2.3.2] — 2026-08-08

### Fixed
- **Every CLI-only install was broken, including the published 2.2.1.** `src/why/cli.py`
  did `import click`, which was only ever satisfied transitively through typer. typer 0.27
  vendored click as `typer._click` and dropped the top-level dependency, so
  `uv tool install why-cli` produced a tool that died with
  `ModuleNotFoundError: No module named 'click'` on **every** command, `why --version`
  included. The recommended `why-cli[web]` install survived only by accident — uvicorn
  happens to pull click in.
- **A quieter second failure on `[web]` installs:** with typer ≥ 0.27, `typer.Abort` is
  `typer._click.exceptions.Abort` and is *not* a subclass of `click.Abort`, so
  `except (click.Abort, EOFError)` in `why review` and `why purposes delete` had stopped
  catching user aborts — reintroducing the non-TTY bug the 2.2.0 review fixed.
- Both are fixed by dropping click entirely in favour of typer's own re-exports
  (`typer.echo`, `typer.Abort`), which resolve correctly on old and new typer alike. click
  is deliberately *not* added as a dependency.

### Why the tests didn't catch it
The suite runs against `uv.lock`, which pinned typer 0.25.0; users get whatever the
resolver picks from `typer>=0.12`. 365 tests passed against a resolution no user has had
for some time. Three things now close that gap:

- `uv.lock` moved to typer 0.27.1, so the dev env matches what a new install resolves to.
- `tests/unit/test_packaging.py` fails if any module under `src/why/` imports click, or if
  click is added to `pyproject.toml` dependencies to paper over it.
- The release workflow installs the built wheel into a clean venv with **fresh dependency
  resolution** — both bare and `[web]` — and runs `why --version`, `why list`, and
  `why --help` before publishing. This is the check that would have caught it.

`CLAUDE.md` records the rule and the reasoning under "What our test suite does NOT cover".

### Notes
- Found by running the real-shell hook verification for 2.3.0 against an actual
  `uv tool install`ed binary rather than `uv run`. The 2.3.0 feature itself was fine; the
  install underneath it was not.

---

## [2.3.1] — 2026-08-08

### Fixed
- **Upgrade docs contradicted the feature shipped one commit earlier.** `install.md` still
  said "after upgrades that change shell-hook behavior, re-run `why init`", and both
  hook-recovery recipes in `troubleshooting.md` prescribed `uv tool upgrade && why init`.
  All three now say what's true: `uv tool upgrade why-cli`, then any `why` command
  refreshes the hook, then restart your shell. `why init` remains the answer when the
  *rc-file block* is missing — auto-refresh updates the hook script, not your shell config.
- `install.md` gains a table of what an upgrade handles automatically (schema, config keys,
  hook) and states the one thing it can't: restarting your shell.

### Added
- README has an **upgrade** section. It had install and uninstall but never said how to
  update, which is the single most-asked question a CLI gets.

---

## [2.3.0] — 2026-08-08

### Added
- **Stale shell hooks now refresh themselves.** Every user-facing command compares the
  `WHY_HOOK_VERSION` in each installed `~/.why/hook.<shell>` against the version shipped
  with the running `why`, rewrites the file in place when it is older, and prints a
  one-time notice telling the user to start a new shell. Previously a hook bugfix only
  reached users who independently thought to re-run `why init` — and a broken hook fails
  silently, which is indistinguishable from "I haven't installed anything lately."
- `packaged_hook_text`, `packaged_hook_version`, `installed_hook_version`,
  `refresh_stale_hooks`, and `SHELLS` in `why.shells.installer`.

### Changed
- `WHY_HOOK_VERSION` bumped `2` → `3` in all three hook scripts. It had been stuck at `2`
  across the 2.2.0 hook rewrite, since nothing read it.
- `WHY_SUPPRESS` gains a second meaning: as well as being the shell-level recursion guard,
  it now tells the CLI it is running inside the prompt cycle and must stay quiet. Old
  hooks already set it on every `why` they invoke, so the gate works for the very users
  being upgraded.
- The notice is written to **stderr**, not stdout — `why export` emits markdown and
  `why follow status --porcelain` is machine-parsed, so stdout has to stay clean. Both
  streams reach the same terminal, so the user sees it either way.
- `tests/integration/test_init.py` derives the expected hook version instead of asserting
  the literal `WHY_HOOK_VERSION=2`.

### Fixed
- **`why uninstall` now deletes `~/.why/hook.*` as well as the rc-file block**, for every
  shell rather than just `$SHELL`. It only ever stripped the block, leaving the payload
  behind; with auto-refresh in place that orphan would be actively maintained, nagging an
  uninstalled user to restart their shell on every future version bump. Uninstall is now
  convergent, and safe to re-run when the files are already gone.

### Notes
- The refresh never creates a hook that was not already installed (keeping `why uninstall`
  convergent), never downgrades a newer hook, refreshes every installed shell rather than
  just `$SHELL`, and is silent during `_hook`, `_record`, `init`, `uninstall`, and when
  `~/.why` is read-only. Nothing is ever auto-`exec`'d.
- Still no PyPI version check — deliberately out of scope, it needs its own privacy and
  caching design.

---

## [2.2.1] — 2026-08-08

### Fixed
- `Auto-tag main` in the release workflow is now gated on `github.ref == 'refs/heads/main'`.
  A `workflow_dispatch` run from a feature branch tagged that branch's HEAD as the
  release; the stray tag then made the next real merge report `should_release=false`
  and skip publishing entirely.

### Changed
- Roadmap in `docs/guide/development.md` rewritten to match reality: PyPI publication
  and 2.2.0 task sessions moved to "Shipped", upgrade ergonomics added as the top
  remaining item, and known follow-ups recorded.
- `docs/guide/development.md` documents what an upgrade does and does not do
  automatically (migrations and config keys yes; hook refresh and update checks no).
- `.DS_Store` added to `.gitignore`.

---

## [2.2.0] — 2026-07-08

### Added
- `why follow start|stop|status|cancel` records an intentional terminal task
  transcript, with `[why rec]` prompt indicators in zsh, bash, and fish hooks.
- `why recall` saves recent command history after the fact, including
  interactive selection from a numbered list.
- `why sessions list|show|summarize|ignore-llm` lets users inspect saved
  transcripts locally, print the exact LLM payload, manually summarize a
  session, or mark a session as not needing LLM processing.
- `why llm configure|test` adds opt-in configuration for OpenAI-compatible
  task recap endpoints, including local Ollama-compatible URLs.
- Web UI sessions pages (`/sessions`, `/sessions/{id}`) for viewing
  transcripts, summary state, latest recap output, and summary history.
- Web UI LLM settings page (`/settings/llm`) for optional task recap
  configuration.
- Schema v6 task transcript tables: `task_sessions`,
  `task_session_commands`, `task_session_summaries`, and `command_journal`.
- Versioned LLM prompt builder and OpenAI-compatible HTTP client.
- `~/.why/llm-ignore.toml` for keeping commands in local transcripts while
  excluding them from LLM payloads.

### Changed
- Shell hooks now record a rolling command journal via internal `why _record`
  so `why recall` has recent commands even when `why follow` was not started.
- `~/.why/patterns.toml` custom install patterns are now active in the matcher
  for hook capture and manual `why log`.
- Documentation now covers follow/recall sessions, manual LLM processing,
  upgrade expectations, privacy review with `--print-payload`, and schema v6.

### Fixed
- Shell hooks no longer declare a local named `status`, which is read-only in both
  zsh and fish. In zsh this aborted `_why_precmd` entirely, silently disabling
  command recording *and* the pre-existing install capture; in fish it printed an
  error on every prompt draw and suppressed the `[why rec]` indicator.
- The `[why rec]` indicator now derives from the current prompt instead of a
  load-time snapshot, so themes that recompute the prompt each draw (starship,
  powerlevel10k, git-status prompts) are no longer frozen.
- In bash the prompt update now runs last in `PROMPT_COMMAND`, so a user entry
  that rewrites `PS1` no longer defeats the indicator, while command recording
  still runs first to observe the correct exit code.
- `why _record` now logs and exits 0 on any failure, matching `why _hook`, so a
  corrupt `config.toml` can no longer put a traceback on every prompt.
- Shell hooks create `~/.why` at load time; the `hook.log` redirect previously
  failed to the terminal when the directory was absent, and skipped recording.
- The web summarize route now honours `confirm_before_send`. It previously sent
  transcripts to a remote endpoint on a single click even when the user had
  configured `always` confirm. The confirmation names the endpoint, the model, and
  the exact command count before anything leaves the machine.
- Command positions are now assigned inside the INSERT, so two terminals recording
  into the same follow session can no longer produce duplicate positions and a
  nondeterministically ordered transcript.
- `~/.why/config.toml` is only rewritten when it actually changed, and the write is
  staged through a temp file. Previously every prompt rewrote it, stripping any
  comments the user had added.
- LLM payload truncation now keeps the **most recent** commands rather than the
  oldest, and reports `truncated_from` so the model knows which end was cut.
- `max_input_commands` is clamped to at least 1 server-side; a negative value
  previously beheaded the newest commands and reported a nonsensical omission count.
- An invalid regex in `llm-ignore.toml` is now a clean configuration error instead of
  a CLI traceback and an HTTP 500.
- LLM request timeouts and non-JSON responses are reported as clean errors instead of
  raw `TimeoutError` / `JSONDecodeError` tracebacks.
- The API key is read only from the configured `api_key_env`; the hardcoded
  `WHY_LLM_API_KEY` fallback that could send a stale credential is gone.
- `why sessions summarize` reports LLM failures cleanly and marks the session
  `failed`, matching the web path.
- Web summarize failures are logged to `~/.why/hook.log` instead of being silently
  swallowed by a blanket `contextlib.suppress(Exception)`.
- `why recall` refuses to create a zero-command session when the journal is empty.
- `PRAGMA busy_timeout` is now set explicitly rather than relying on the sqlite3
  driver default.
- The `/sessions` empty state shows session-specific copy. It passed `title=`/`body=`
  to a partial that reads `line=`, so Jinja silently ignored both and rendered the
  "No installs yet" default with escaped HTML.
- The web footer no longer claims "no network" when LLM summaries are enabled; it now
  reads "sends only when you summarize".
- `[llm].store_summaries = false` is now honoured by both the CLI and the web UI.
  It was documented and written into every config but read nowhere.
- `why llm test` now makes a real request and fails on an unreachable endpoint, a
  wrong key, or a malformed response. It previously printed config and exited 0.
- `why llm configure` and `why recall --interactive` have non-TTY fallbacks instead of
  aborting, so scripts, Dockerfiles, and CI can call them.
- `close_task_session`, `cancel_task_session`, and `set_task_session_summary_status`
  no longer report success for a soft-deleted session. Their `UPDATE` filtered
  `deleted=0` but the following `SELECT` did not, so a no-op write returned a stale
  row as though it had succeeded.
- A successful summarize with `store_summaries = false` now marks the session
  `complete`; it previously stayed `none` and reappeared in "needs summary" views.

### Added
- Hook tests that drive the real zsh, bash, and fish scripts through an actual prompt
  cycle (`tests/integration/test_hook_prompt_cycle.py`). The previous shell test
  sourced the hook but hand-wrote its own `why _hook` call, so it could not catch a
  hook whose control flow never reached it.
- CI now installs zsh and fish and fails the build if any shell test skips. Neither
  shell was present on the runner, so the hook tests were silently not running.
- `why sessions unignore-llm <id>` — the web UI had this action; the CLI did not.
- `why sessions delete <id>` and `--purge`, plus **Delete** / **Erase transcript**
  buttons on the session page. Saved transcripts previously could not be removed from
  either surface — the only recovery from an unwanted recording was hand-editing
  SQLite. Soft delete keeps a sync tombstone; `--purge` removes the session and
  cascades to its commands and summaries.

---

## [2.1.0] — 2026-06-08

### Changed
- The shell hook now enforces `[managers]` toggles from `~/.why/config.toml`
  for both installs and supported uninstalls. Disabled managers are ignored
  silently by the hook; manual `why log -- <cmd>` still captures explicitly.

---

## [1.7.0] — 2026-05-01

### Added
- **Shell history ring buffer** — the last 10 commands before each install are
  now captured by the shell hook and stored in the `command_history` table
  (migration 004). This gives context for *why* you ran an install.
- `why show <id>` — new CLI subcommand. Prints full install metadata plus the
  command history for an install.
- **Edit panel history block** — when an install has a recorded command
  history, the web edit modal shows a read-only "Commands before this install"
  list at the bottom.
- `redact.py` — new pure module that strips secrets (tokens, passwords, API
  keys, env-var assignments) from captured commands before storing. Uses
  conservative regex patterns so commands remain useful.
- `_hook --history` flag — internal flag added to `why _hook`; receives the
  record-separator-delimited decoded command buffer from the shell hook.

### Changed
- Schema version bumped from 3 → 4 (`004_command_history.sql`).
- `capture()` now returns `Install | None` (was `None`) so the hook runner can
  associate history with the correct install row.
- Shell hooks (zsh, bash, fish) updated to maintain `WHY_HISTORY` ring buffer
  and pass decoded commands to `why _hook` via `--history`.

---

## [1.6.0] — 2026-05-01

### Added
- **User-configurable purpose categories** — purpose labels, colors, and sort
  order are now stored in the `purposes` table (DB migration 003) instead of
  being hardcoded. Five built-in categories (Reference, Project setup, Trying
  out, Cleanup soon, Ignore) are seeded automatically; built-ins can be edited
  but not deleted.
- `why purposes list` — tabular view of all purpose categories.
- `why purposes add --key KEY --label LABEL [--color COLOR] [--sort-order N]`
  — add a custom purpose category.
- `why purposes edit KEY [--label LABEL] [--color COLOR] [--sort-order N]`
  — update an existing purpose category (built-ins included).
- `why purposes delete KEY` — delete a custom purpose category (built-ins
  are protected).
- **Settings → Purposes page** (`/settings/purposes`) in the web UI — list,
  add, edit, and delete purpose categories without touching the CLI.
- "Purposes" nav link in the web sidebar pointing to the settings page.
- CLI capture prompt now loads purpose options dynamically from the DB;
  falls back to built-in defaults if the DB is unavailable.

### Changed
- Schema version bumped from 2 → 3 (`003_purposes.sql`).
- All templates and routes now receive a `purposes` list and `purpose_map`
  dict from the DB rather than reading hardcoded key lists.

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
