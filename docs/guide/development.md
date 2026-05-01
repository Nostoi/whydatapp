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

# Install pre-commit hooks (recommended — auto-rebuilds tailwind.css
# and runs ruff before every commit):
pip install pre-commit
pre-commit install
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

The committed `tailwind.css` is what ships in the wheel and what every dev install uses. **Three layers protect against shipping stale CSS:**

1. **pre-commit hook** (recommended; see Setup above). Auto-rebuilds + re-stages the CSS whenever you commit a change under `src/why/web/templates/`. Zero-touch.
2. **CI guard.** The release workflow rebuilds the CSS before `uv build` and fails the release if `.flex` isn't in the output. Catches anything that slipped past pre-commit.
3. **Manual fallback.** If you used `--no-verify` or skipped pre-commit setup, run `make css && git add src/why/web/static/css/tailwind.css` before pushing.

Layer 1 is the only one that helps local users running editable installs from your branch — CI only fires for releases, so don't rely on it during development.

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
├── capture.py          # re-install enrichment logic
├── humanize.py         # human-readable time-ago formatting
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

## Publishing to PyPI

Releases are automated by [`.github/workflows/release.yml`](../../.github/workflows/release.yml). It uses **Trusted Publishing** — no API tokens are stored in the repo or GitHub Secrets.

### One-time setup (per project name)

Done once when the project name is first claimed.

1. **Confirm name availability** at `https://pypi.org/project/<name>/` and `https://test.pypi.org/project/<name>/`. A 404 means free.
2. **Add pending Trusted Publishers** at https://pypi.org/manage/account/publishing/ and https://test.pypi.org/manage/account/publishing/. For each:
   - PyPI Project Name: `why-cli`
   - Owner: `Nostoi`
   - Repository name: `whydatapp`
   - Workflow filename: `release.yml`
   - Environment name: `pypi` (real) / `testpypi` (test)
3. **Create matching GitHub environments** under repo Settings → Environments: `pypi` and `testpypi`. No protection rules required, though "required reviewers" is a sensible safeguard for `pypi`.

After the first successful publish, the "pending" publisher converts to a real one automatically.

### Release flow (every version)

1. Decide the bump per [`CLAUDE.md`](../../CLAUDE.md#bump-rules-semver-majorminorpatch). Update `pyproject.toml` and `src/why/__init__.py`. Update any docs the change touches.
2. Commit with the version bump.
3. Run the local gate (`pytest`, `ruff`, `mypy` — same as CI).
4. Tag and push:
   ```bash
   git tag v1.0.2
   git push origin v1.0.2
   ```
5. The `release.yml` workflow:
   - Verifies the tag matches both version files (fails fast if they drift).
   - Re-runs the full quality gate.
   - Builds wheel + sdist.
   - Publishes to PyPI via Trusted Publishing.

### Dry-run on TestPyPI

Trigger the workflow manually (Actions tab → release → "Run workflow") to publish to TestPyPI without tagging. Then verify install:

```bash
uv tool install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  'why-cli[web]'
```

The `--extra-index-url` is needed because TestPyPI doesn't mirror dependencies (FastAPI, Typer, etc. live on real PyPI).

### Filenames are immutable

Once a wheel is on PyPI, that exact `why_cli-X.Y.Z-py3-none-any.whl` is locked forever. You can `yank` a release (hides it from new installs) but cannot delete it or re-upload the same version. Always TestPyPI first if you're unsure.

If a release is broken: yank it, bump PATCH, fix, re-release.

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
