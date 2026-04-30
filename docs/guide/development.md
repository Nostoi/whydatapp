# Development

## Prerequisites

- Python **3.11+**
- [`uv`](https://docs.astral.sh/uv/) (fastest path; `pip` works too)
- Node + `npx` (only for rebuilding `tailwind.css` — the committed CSS is fine for most work)

## Setup

```bash
git clone https://github.com/Nostoi/whydatapp.git
cd whydatapp
uv venv
uv pip install -e '.[dev,web]'
```

Run an isolated `why init` against a sandbox home (so you don't touch your real `~/.why/`):

```bash
WHY_HOME=$(pwd)/.why-sandbox uv run why init
WHY_HOME=$(pwd)/.why-sandbox uv run why log -- brew install ripgrep
WHY_HOME=$(pwd)/.why-sandbox uv run why serve --no-open
```

## Quality gate

These three must stay clean:

```bash
uv run pytest -q             # 120+ tests
uv run ruff check src tests  # lint
uv run mypy src/why          # type check (strict)
```

The `tests/conftest.py` `why_home` fixture isolates `~/.why` per test via `WHY_HOME`.

## Running the web UI in dev

```bash
uv run why serve --no-open
# Open http://127.0.0.1:7873/ manually.
```

For Tailwind iteration:

```bash
make css-watch    # rebuilds src/why/web/static/css/tailwind.css on template change
```

The committed `tailwind.css` is what ships in the wheel. Rebuild and commit it whenever you change classes used in templates.

## Building the wheel

```bash
uv build
ls dist/
# why_cli-1.0.x-py3-none-any.whl
# why_cli-1.0.x.tar.gz
```

Smoke-test the wheel from a clean venv:

```bash
mkdir /tmp/why-smoke && cd /tmp/why-smoke
uv venv && uv pip install <path-to-built-wheel>'[web]'
WHY_HOME=$(pwd)/.why uv run why init
```

## Architecture in 60 seconds

Five pieces, one process model.

```
shell hook (~/.why/hook.zsh)  →  why _hook (Python)
                                       │
                                       ▼
                                 why.detect  (pure: pattern + ignore rules)
                                 why.store   (pure: SQLite)
                                 why.resolve (best-effort install path)
                                       │
                       ┌───────────────┴───────────────┐
                       ▼                               ▼
                  why CLI (Typer)                why.web (FastAPI + HTMX)
                  log/review/list/...            installs/dashboard/review
```

- **`why.store`** is the only module that touches SQLite. CLI and web both go through it.
- **`why.detect`** has no I/O. Pattern matching + ignore rules are pure functions, exhaustively tested.
- **`why.web`** never imports `why.cli`. The CLI never imports `why.web`. Both depend on `why.store`.
- **The shell hook** is a thin wrapper. All real logic is in `why _hook` (`hook_runner.py`). Any failure exits 0 and logs to `~/.why/hook.log` — the user's terminal is never broken.

Full architecture is in [`docs/superpowers/specs/2026-04-29-whydatapp-design.md`](../superpowers/specs/2026-04-29-whydatapp-design.md). The implementation plans are in [`docs/superpowers/plans/`](../superpowers/plans/).

## Project layout

```
src/why/
├── cli.py              # Typer app, all subcommands
├── store.py            # SQLite functions (pure)
├── schema.py           # migration runner
├── migrations/         # numbered .sql files
├── detect.py           # patterns + ignore rules (pure)
├── resolve.py          # best-effort install path resolution
├── prompts.py          # interactive metadata prompt (pure-ish)
├── markdown.py         # entry → Markdown snippet (shared CLI + web)
├── project_infer.py    # cwd → project name (pure)
├── config.py           # config + presentation loaders
├── paths.py            # ~/.why/* paths (honors WHY_HOME)
├── bootstrap.py        # idempotent first-run bootstrap
├── hook_runner.py      # `why _hook` entrypoint
├── init_wizard.py      # `why init` interactive wizard
├── autostart.py        # launchd + systemd-user unit gen
├── shells/             # zsh/bash/fish hook scripts + rc-file installer
├── presentation.toml   # default icons/colors per manager
└── web/
    ├── app.py          # FastAPI factory
    ├── csrf.py         # CSRF middleware
    ├── filters.py      # query-param → InstallFilters
    ├── deps.py         # FastAPI deps (db path, presentation)
    ├── routes/         # installs / dashboard / review / share / export
    ├── templates/      # Jinja partials + pages
    └── static/         # tailwind.css, htmx.min.js, logos
```

## Versioning

See [`CLAUDE.md`](../../CLAUDE.md) at the repo root. TL;DR:

- SemVer.
- Bump `pyproject.toml` and `src/why/__init__.py` together — they must always match.
- Bump before every push: PATCH for fixes/refactors, MINOR for additive features, MAJOR for breaking changes.

## Tests

- `tests/unit/` — pure-function tests for `detect`, `store`, `resolve`, `config`, `prompts`, `project_infer`, `markdown`, web `filters`, `autostart`, `paths`, `schema`.
- `tests/integration/` — Typer `CliRunner`, FastAPI `TestClient`, real-shell smoke test (`tests/integration/test_hook_shell.py`, skipped if zsh missing).

Coverage targets: ≥85% on `detect.py`, `store.py`, `prompts.py`. Run with `uv run pytest --cov=why --cov-report=term-missing`.

## Plans and specs

The product was designed before it was built. The reference docs:

- Spec: [`docs/superpowers/specs/2026-04-29-whydatapp-design.md`](../superpowers/specs/2026-04-29-whydatapp-design.md)
- Plan 1 (core CLI): [`docs/superpowers/plans/2026-04-29-plan-1-core-cli.md`](../superpowers/plans/2026-04-29-plan-1-core-cli.md)
- Plan 2 (web UI): [`docs/superpowers/plans/2026-04-29-plan-2-web-ui.md`](../superpowers/plans/2026-04-29-plan-2-web-ui.md)
- Plan 3 (distribution): [`docs/superpowers/plans/2026-04-29-plan-3-distribution-init.md`](../superpowers/plans/2026-04-29-plan-3-distribution-init.md)

Read the spec before proposing structural changes.

## Roadmap

In rough priority order:

1. PyPI publication (so `uv tool install why-cli` works).
2. Per-manager toggle enforcement at hook time (read `[managers]` from config, not just at wizard time).
3. Custom-patterns wiring (consume `~/.why/patterns.toml` in the matcher).
4. UI editor for `patterns.toml` and `presentation.toml`.
5. Homebrew tap.
6. Sync (pluggable backend + auth).
7. AI enrichment, source scraping, update discovery.
8. One-click remote install.

## Contributing

- One change per PR. Keep diffs small.
- Match the existing structure: pure modules stay pure; web reads/writes through `why.store`; CLI doesn't import `why.web`.
- Tests with the change. TDD if you can.
- Bump the version (see `CLAUDE.md`).
- Make sure ruff and mypy stay clean.
