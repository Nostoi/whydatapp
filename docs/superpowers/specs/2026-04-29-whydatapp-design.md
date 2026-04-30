# why? — Design Spec

**Date:** 2026-04-29
**Status:** Draft, awaiting user review
**Working name:** `why?` (CLI binary: `why`)

## 1. Purpose

A local-first tool that captures the context behind every install on a developer machine — the command, the directory, the date, and (most importantly) *why*. The user gets a searchable, sortable, shareable record of every tool they've installed, with explicit dispositions ("document this," "add to setup script," "experimental," "remove later," "ignore"), plus a dashboard that surfaces stale items needing review.

Privacy-focused, single-user, localhost-only in the MVP. Built so multi-device sync, auth, AI enrichment, and one-click remote install can land later without schema migrations or rewrites.

## 2. MVP scope

In scope:
- Shell hook that detects user-intent installs across major package managers and triggers an interactive metadata prompt immediately after the install completes.
- Manual fallback for retroactive logging and for cases the hook misses.
- SQLite-backed local storage with FTS5 search.
- Local web UI: searchable/sortable installs table, dashboard with counts and a stale-review queue, and a review flow for skipped entries.
- Per-entry and bulk sharing/export (Markdown, JSON).
- One-command install with an interactive setup wizard. No user-edited `.env` files.

Out of scope (forward-compat seams only — see §11):
- Sync between devices.
- Authentication / multi-user.
- AI enrichment, chat, advice.
- Source scraping, update discovery.
- One-click remote install.
- UI editors for custom patterns and theming.

## 3. Architecture

```
Shell (zsh/bash/fish)
  └── why hook (preexec captures cmd; precmd checks exit code)
         │ matched + intentful?
         ▼
       why CLI (Python, single entrypoint)
         subcommands: init / log / review / serve / list / export / uninstall / _hook
         │
         ├─► why.store     (SQLite, pure functions)
         ├─► why.detect    (pattern matching + ignore rules, pure)
         └─► why.web       (FastAPI + HTMX, binds 127.0.0.1)
```

Five components, one process model:

1. **Shell hook** (`~/.why/hook.{zsh,bash,fish}`): minimal shell wrapper. Captures command, cwd, exit code; execs `why _hook` only when relevant.
2. **CLI** (`why`): single Python package, all subcommands. Owns the interactive prompts.
3. **Storage layer** (`why.store`): pure functions over SQLite. No FastAPI/CLI imports. Used by both CLI and web.
4. **Detection layer** (`why.detect`): pattern matching and ignore heuristics. Pure, well-tested, no I/O.
5. **Web UI** (`why serve`): FastAPI + Jinja + HTMX + Tailwind, binds `127.0.0.1`. Read/write through `why.store`.

The CLI and web UI never call each other. Both call `why.store`. The web UI never runs installs; the shell hook never contains business logic.

## 4. Detection & ignore logic (`why.detect`)

### Patterns

A `PATTERNS` list drives matching. Each entry: `(manager, regex, package_extractor)`. Tier-1 managers ship enabled. Tier-2 ship as commented entries the user can opt in to during `why init`. Custom patterns load from `~/.why/patterns.toml`.

**Tier-1 (default on):**
- `brew install <pkg...>`
- `npm install -g <pkg>` / `npm i -g <pkg>` / `npm install --global <pkg>`
- `pnpm add -g <pkg>` / `pnpm add --global <pkg>`
- `yarn global add <pkg>`
- `bun add -g <pkg>` / `bun add --global <pkg>`
- `pip install <pkg>` / `pip3 install <pkg>` (excluding `-r`, `-e`)
- `pipx install <pkg>`
- `uv tool install <pkg>`
- `cargo install <pkg>`
- `git clone <url>`

**Tier-2 (off by default, opt-in at `why init`):**
- `gem install`, `go install`, `apt install`, `apt-get install`, `mas install`, `code --install-extension`, `docker pull`.

The `manager` column in the schema is free-text, so users adding custom patterns can introduce new manager names without schema changes.

### Ignore rules

Applied in order; first match drops the event:

1. Exit code ≠ 0.
2. Non-interactive shell.
3. `WHY_SUPPRESS=1` in env (prevents recursion).
4. Parent process is in `IGNORED_PARENTS`: `brew`, `pip`, `npm`, `pnpm`, `yarn`, `bun`, `cargo`, `make`, `docker`, `nix`, `asdf`, `mise`, `volta`, `nvm`, `why`. Catches "tool installs its own deps."
5. Dependency-restore commands (no explicit packages): bare `npm install`, `pnpm install`, `yarn`, `pip install -r ...`, `bundle install`, `cargo build`, etc.
6. `$PWD` contains a lockfile matching the manager AND the command lacks explicit package args (belt-and-suspenders for #5).
7. Command matches a regex in `~/.why/ignore.toml` (user escape hatch).
8. Same exact `(command, cwd)` already logged within the last 60 seconds (debounce).

### Resolution

Best-effort post-install, never blocks the prompt:
- `brew`: `brew --prefix <pkg>` → `resolved_path`.
- `pipx` / `uv tool`: known venv path under `~/.local/share/`.
- `cargo install`: `~/.cargo/bin/<name>`.
- `npm/pnpm/yarn/bun -g`: `$(npm root -g)/<pkg>` (cached once per session).
- `git clone`: derived from cwd + repo name.
- Failure → leave `resolved_path` null.

### Hook handoff

Shell hook does almost nothing:

```zsh
why_preexec() { WHY_LAST_CMD="$1"; WHY_LAST_PWD="$PWD"; }
why_precmd() {
  local code=$?
  [[ -z $WHY_LAST_CMD ]] && return
  [[ $code -ne 0 ]] && { WHY_LAST_CMD=; return; }
  WHY_SUPPRESS=1 why _hook --cmd "$WHY_LAST_CMD" --cwd "$WHY_LAST_PWD" --code $code </dev/tty >/dev/tty 2>&1
  WHY_LAST_CMD=
}
```

All real logic in `why _hook`. Bash and fish equivalents ship in the same `~/.why/` directory.

The hook is paranoid: any failure exits 0 and logs to `~/.why/hook.log`. The user's terminal is never broken.

## 5. Data model

```sql
CREATE TABLE users (
  id              TEXT PRIMARY KEY,         -- UUID
  email           TEXT,                     -- nullable in MVP
  display_name    TEXT,
  created_at      TEXT NOT NULL
);

CREATE TABLE devices (
  id              TEXT PRIMARY KEY,         -- UUID
  hostname        TEXT NOT NULL,
  label           TEXT,                     -- "work-mbp", set during init
  created_at      TEXT NOT NULL,
  last_seen_at    TEXT NOT NULL
);

CREATE TABLE projects (                     -- autocomplete + dashboard grouping
  name            TEXT PRIMARY KEY,
  created_at      TEXT NOT NULL
);

CREATE TABLE installs (
  id              INTEGER PRIMARY KEY,
  sync_id         TEXT NOT NULL UNIQUE,     -- stable cross-device UUID
  user_id         TEXT NOT NULL REFERENCES users(id),
  device_id       TEXT NOT NULL REFERENCES devices(id),

  -- captured automatically
  command         TEXT NOT NULL,
  package_name    TEXT,
  manager         TEXT NOT NULL,            -- free-text; ships with known set
  install_dir     TEXT NOT NULL,            -- $PWD at install time
  resolved_path   TEXT,
  installed_at    TEXT NOT NULL,            -- ISO8601 UTC
  exit_code       INTEGER NOT NULL,

  -- user-supplied
  display_name    TEXT,
  what_it_does    TEXT,
  project         TEXT,
  why             TEXT,
  disposition     TEXT,                     -- doc|setup|experimental|remove|ignore
  notes           TEXT,
  source_url      TEXT,                     -- post-MVP scraping target

  -- lifecycle
  metadata_complete  INTEGER NOT NULL DEFAULT 0,
  reviewed_at     TEXT,
  removed_at      TEXT,                     -- soft delete / "actually removed"

  -- sync
  updated_at      TEXT NOT NULL,
  deleted         INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX installs_disposition ON installs(disposition);
CREATE INDEX installs_project     ON installs(project);
CREATE INDEX installs_manager     ON installs(manager);
CREATE INDEX installs_installed   ON installs(installed_at);
CREATE INDEX installs_device      ON installs(device_id);

CREATE VIRTUAL TABLE installs_fts USING fts5(
  display_name, package_name, command, what_it_does, project, why, notes,
  content='installs', content_rowid='id'
);
-- + AFTER INSERT/UPDATE/DELETE triggers to keep FTS in sync.

CREATE TABLE schema_version (version INTEGER NOT NULL);
```

Notes:
- `disposition` is a text enum, not an FK. Simpler, easy to extend.
- `metadata_complete = 0` flags skipped/incomplete entries for the review queue.
- `removed_at` lets a user mark "actually removed" without losing history.
- `sync_id`, `updated_at`, `deleted` are populated from day one but never read in the MVP. They are the entire data shape any sync protocol (CRDT or LWW) needs.
- All migrations are numbered SQL files (`migrations/001.sql`, …). A backup of `data.db` is taken before any migration runs.

## 6. Configuration & filesystem layout

```
~/.why/
├── data.db                  # SQLite + WAL
├── data.db-wal
├── data.db-shm
├── config.toml              # user-editable, written by `why init`
├── patterns.toml            # custom detection patterns (empty by default)
├── ignore.toml              # custom ignore regexes (empty by default)
├── presentation.toml        # icon/color/label per manager (user-overridable)
├── hook.zsh
├── hook.bash
├── hook.fish
├── hook.log                 # paranoid hook errors
├── web.log
└── backups/                 # pre-migration snapshots
```

`config.toml` (example, all keys generated by the wizard):

```toml
[device]
id    = "01HX..."             # UUID
label = "work-mbp"

[user]
id           = "01HX..."
display_name = "mark"
email        = ""

[managers]
brew = true
npm = true
pnpm = true
yarn = true
bun = true
pip = true
pipx = true
uv = true
cargo = true
git = true
# Tier-2 (off by default)
gem = false
go = false
apt = false
mas = false
vscode = false
docker = false

[web]
host = "127.0.0.1"
port = 7873
autostart = false             # if true, install launchd/systemd unit

[ui]
# Empty in MVP; populated post-MVP for theme/customization.

[sync]
enabled = false
# endpoint = "https://..."
```

## 7. Distribution & first-run

Canonical path: `uv tool install why-cli` (or `pipx install why-cli`). Runs interactive setup with `why init`.

`why init` does:

1. Detect shell (zsh / bash / fish). Confirm hook installation.
2. Write the hook block (fenced) to the rc file:
   ```
   # >>> why-cli hook >>>
   [ -f ~/.why/hook.zsh ] && source ~/.why/hook.zsh
   # <<< why-cli hook <<<
   ```
3. Generate device UUID + user UUID. Ask for device label (default: hostname).
4. Show Tier-1 managers with confirm-toggle. Offer Tier-2 opt-in.
5. Pick web UI port (default 7873). Optionally install launchd/systemd autostart unit.
6. Create `~/.why/`, run schema migrations, seed `users` and `devices` rows.
7. Print "you're done — try `brew install <something small>` to test."

`why uninstall` removes the rc-file hook block and (with confirmation) `~/.why/`.

A Homebrew tap (`brew install why`) is a post-MVP additive distribution path.

## 8. Interaction flows

### Flow A — Capture (immediate prompt)

```
$ brew install ripgrep
🍺  /opt/homebrew/Cellar/ripgrep/14.1.0: 19 files, 6.3MB

📝 why? — captured: brew install ripgrep  (~/dev/projects/whydatapp)

  Disposition? [1] Doc  [2] Setup  [3] Experimental  [4] Remove later  [5] Ignore
  [s] Skip for now    [q] Quit (treat as ignore)
> 1

  Display name [ripgrep]:
  What does it do? fast recursive grep written in rust
  Project [whydatapp]:
  Why install? need fast code search across all my repos
  Notes (optional, ↵ to skip):

  ✓ Logged. View at http://127.0.0.1:7873/i/47
```

- `display_name` defaults to parsed `package_name`.
- `project` defaults to nearest `package.json` / `pyproject.toml` / `.git` ancestor's directory name.
- `[s]` writes the row with `metadata_complete = 0`. Surfaces in `why review` and the dashboard's stale queue.
- `[q]` writes the row with `disposition = ignore` and `metadata_complete = 1`.
- `Ctrl-C` mid-prompt is treated as `[s]` — the capture is never lost.
- Only `disposition` is required; everything else is optional.

### Flow B — `why review`

Drains the skipped queue one entry at a time, same prompts as Flow A.

### Flow C — `why init`

Setup wizard described in §7.

### Flow D — `why serve`

Starts FastAPI on `127.0.0.1:7873`, opens the browser. Idempotent: if already running, opens the browser only.

### Flow E — `why uninstall`

Removes the rc hook block, optionally removes `~/.why/`. Confirms before deleting data.

## 9. Web UI

Single-page-feel via HTMX. No SPA, no build step on the user's machine. Tailwind CSS shipped pre-compiled.

### Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ why?     [Installs]  [Dashboard]  [Review N]      🔍 search...   │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   (active view)                                                  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
🔒 localhost · no network
```

### View 1 — Installs (default)

- Sticky filter bar: disposition pills, project dropdown, manager dropdown (with icons/colors from `presentation.toml`), date range, device dropdown, "incomplete only" toggle.
- Table columns: icon · name · package · manager · project · disposition · installed_at · device · actions.
- Sortable by any column (HTMX swap on header click).
- Search box hits FTS5; results re-render the table inline.
- Click a row → expands inline to detail + edit form (`hx-get` returns the row's edit panel).
- Per-row actions: **Share** (clipboard Markdown), **Mark removed**, **Edit**, **Delete**.
- Multi-select checkboxes → bulk **Export** (Markdown or JSON download), bulk **Set disposition**, bulk **Copy install commands**.

### View 2 — Dashboard

Cards:
- Counts by disposition (5 numbers + total).
- Counts by project (top 10 + Other).
- Installs-per-month sparkline (last 12 months).
- Counts by manager (with icons).
- **Stale review queue**, clickable list of:
  - `metadata_complete = 0` (skipped/incomplete).
  - `experimental` items older than 30 days.
  - `remove` items older than 14 days, not yet `removed_at`.
  - Each item links to its edit panel in View 1.

### View 3 — Review

Same shape as Flow B in the browser. One entry at a time, big form, "Save and next" / "Skip" / "Mark ignore." The nav-bar `Review N` badge shows the queue size.

### Sharing & export

- Per-entry **Share**: copies a clean Markdown snippet —
  ```
  **ripgrep** — `brew install ripgrep`
  Fast recursive grep written in Rust. Installed 2026-04-29 in ~/dev/projects/whydatapp
  Why: needed fast code search across all my repos.
  ```
- **Export selection** → `.md` (one entry per heading) or `.json` (raw rows).
- **Copy install commands** → runnable shell snippet (groundwork for post-MVP one-click remote install).

### Backend endpoints

- `GET /` → table view (full page).
- `GET /installs` → table fragment (HTMX swap target).
- `GET /installs/{id}/edit` → row-edit fragment.
- `POST /installs/{id}` → update, returns updated row fragment.
- `GET /dashboard` → dashboard view.
- `GET /review` / `POST /review/{id}` → review flow.
- `GET /export?ids=...&format=md|json` → file download.

All endpoints localhost-only. Per-session CSRF cookie token from day one (cheap to add now, removes a thing-to-fix when auth lands).

### URL state

All filter/sort state lives in URL query params (`?disposition=experimental&project=foo&q=ripgrep`). Back/forward works. Dashboard cards deep-link into pre-filtered table views.

## 10. Design principles

1. **Calm, not clever.** Maintenance tool aesthetic. No animations beyond ~150ms transitions, no marketing copy, no novelty fonts. Density between Linear and Bloomberg.
2. **One typeface, one mono.** Inter (UI) + JetBrains Mono (commands, paths). Both pre-bundled.
3. **Restrained palette, semantic color.** Neutral grays do 90% of the work. Color carries meaning:
   - Disposition pills: Doc=blue, Setup=green, Experimental=amber, Remove=red, Ignore=gray.
   - Manager badges: one accent color each from `presentation.toml`. Used only on the small badge.
   - Stale-review items get a thin amber left border, nothing more.
   - True dark mode (deep neutral, not pure black). Off-white light mode.
4. **The command is the hero.** Monospace, copyable on click, never truncated in detail view. `why` field is second-most prominent. Everything else is metadata.
5. **Filters are URL state.** Deep-linkable, back-button-friendly, shareable.
6. **Empty states teach.** One-line example + the command that would create it. No empty-state illustrations.
7. **Keyboard-first where it matters.** `/` focuses search, `j/k` moves selection, `e` edits, `s` shares, `?` opens shortcut help. Mouse works for everything.
8. **Components, not pages.** Every visual element is a Jinja partial in `web/templates/components/` (`pill.html`, `manager_badge.html`, `card.html`, `row.html`, `filter_bar.html`, `empty_state.html`). Pages compose partials. New views reuse or extend the partial library.
9. **Privacy is visible.** A small `🔒 localhost · no network` indicator in the footer, always. Becomes `🔒 localhost · sync paused` or `🔄 syncing to <endpoint>` when sync exists. Never hidden.
10. **Forgiving inputs.** Every field tolerates empty except `disposition`. `project` autocompletes from prior values but accepts anything. Disposition is changeable any time. No destructive action without undo: delete is soft-delete first; hard-delete requires a second confirm.

## 11. Forward-compat seams (MVP carries the shape, not the feature)

- **Sync:** `sync_id`, `updated_at`, `deleted`, `device_id`, `users` table all present. `[sync]` config section stubbed.
- **Auth:** `users` table present and populated; CSRF token on web; web stays localhost-only until auth lands.
- **Custom commands & user-extensible managers:** `~/.why/patterns.toml` exists day one; `manager` column is free-text. Post-MVP adds a UI editor.
- **User customization:** `[ui]` config section stubbed. Post-MVP adds a settings UI.
- **Icons/colors per manager:** `~/.why/presentation.toml` ships pre-populated and is user-editable. v1 reads it for table-row badges so visuals are pretty day one. Post-MVP adds a UI editor on top of the same file.
- **AI enrichment, scraping, update discovery:** `source_url` and `notes` columns reserved.
- **One-click remote install:** "Copy install commands" action in the web UI is the first step.

## 12. Testing

- `why.detect` and `why.store` unit-tested with high coverage (pattern matching, ignore rules, FTS queries, schema migrations).
- CLI subcommands tested via Typer's runner against a temp `~/.why/`.
- Web tested via FastAPI's `TestClient` against an in-memory SQLite.
- One integration test boots a real shell, sources the hook, runs a fake `brew` shim, asserts a row appears.
- One golden snapshot test per Jinja partial to catch accidental visual regressions.

## 13. Errors

- Hook is paranoid: any failure in `why _hook` exits 0 and logs to `~/.why/hook.log`. Terminal is never broken.
- DB writes use WAL mode. CLI and web write concurrently without corruption.
- Schema migrations run automatically at startup. Pre-migration backup of `data.db` taken every time.
- Web shows real error pages (not stack traces), full traces logged to `~/.why/web.log`.
- All user-facing errors point at the relevant log path.

## 14. Performance budget

- Hook overhead on non-matching commands: <20ms. Lazy imports in `why _hook`.
- Hook overhead on matching commands: prompt visible <100ms after install completes.
- Web table renders 10k rows in <300ms (FTS5 + indexed columns + 100/page pagination).
- DB stays <50MB at 10k entries (text-only, no blobs).

## 15. Post-MVP roadmap (priority order)

1. Custom command UI — edit `patterns.toml` from web.
2. Theme/customization UI — edit `presentation.toml` and `[ui]` config.
3. Homebrew tap (`brew install why`).
4. Sync — pluggable backend. Ship a self-hostable FastAPI sync server first; offer a "shared SQLite over iCloud/Dropbox" no-server fallback.
5. Auth — login on web UI once sync exists.
6. AI supplementation — local LLM or API-key option to enrich `what_it_does` / `why` from `command` + scraped homepage.
7. AI advice & chat — "what experimental things should I clean up?", "find similar tools to X."
8. Source scraping — fill `source_url`, README excerpt, current latest version.
9. Update discovery — periodic check vs. installed version, dashboard card.
10. One-click remote install — given a peer device, generate and run install commands for selected entries.

## 16. Repository layout (proposed)

```
whydatapp/
├── pyproject.toml
├── README.md
├── docs/
│   └── superpowers/specs/2026-04-29-whydatapp-design.md
├── src/why/
│   ├── __init__.py
│   ├── cli.py                 # Typer app, all subcommands
│   ├── detect.py              # patterns + ignore rules (pure)
│   ├── store.py               # SQLite functions (pure)
│   ├── resolve.py             # best-effort install path resolution
│   ├── hook_runner.py         # `why _hook` entrypoint
│   ├── init_wizard.py
│   ├── config.py              # config.toml + presentation.toml loaders
│   ├── shells/
│   │   ├── hook.zsh
│   │   ├── hook.bash
│   │   └── hook.fish
│   ├── migrations/
│   │   └── 001_init.sql
│   ├── presentation.toml      # default icons/colors per manager
│   └── web/
│       ├── app.py             # FastAPI factory
│       ├── routes/
│       │   ├── installs.py
│       │   ├── dashboard.py
│       │   ├── review.py
│       │   └── export.py
│       ├── templates/
│       │   ├── base.html
│       │   ├── installs.html
│       │   ├── dashboard.html
│       │   ├── review.html
│       │   └── components/
│       │       ├── pill.html
│       │       ├── manager_badge.html
│       │       ├── card.html
│       │       ├── row.html
│       │       ├── filter_bar.html
│       │       └── empty_state.html
│       └── static/
│           ├── css/tailwind.css   # pre-built
│           └── js/htmx.min.js     # vendored
└── tests/
    ├── unit/
    ├── integration/
    └── snapshots/
```
