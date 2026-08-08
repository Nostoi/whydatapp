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

# Shells under test. The hook tests SKIP for any shell that isn't installed,
# so without these you get a green run that never exercised those hooks.
# macOS ships zsh and bash; fish does not.
brew install fish                      # macOS
sudo apt-get install -y zsh fish       # Debian/Ubuntu
```

These are system shells, not Python packages, so they can't live in `pyproject.toml`. CI installs them explicitly and **fails the build if any shell test skips** — see `.github/workflows/release.yml`.

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
shell hook (~/.why/hook.zsh)  →  why _hook / why _record (Python)
                                       │
                                       ▼
                                 why.detect  (pure: pattern + ignore rules)
                                 why.store   (pure: SQLite)
                                 why.resolve (best-effort install path)
                                       │
                       ┌───────────────┴───────────────┐
                       ▼                               ▼
                  why CLI (Typer)                why.web (FastAPI + HTMX)
                  log/review/follow/...          installs/dashboard/sessions
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
├── sessions.py         # follow/recall session orchestration
├── llm.py              # versioned task recap prompts + OpenAI-compatible client
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
    ├── routes/         # installs / dashboard / review / sessions / share / export
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
- `tests/integration/test_hook_prompt_cycle.py` — drives the **real** hook scripts through an actual prompt cycle in zsh, bash, and fish, using a shimmed `why` on `PATH`. This is the layer `test_hook_shell.py` misses: that file sources the hook but then hand-writes its own `why _hook` call, so it cannot catch a hook whose control flow never reaches it.

### Shell coverage depends on which shells are installed

Each shell's tests skip when that shell is absent, so a green run does **not** mean every shell was checked. Watch the skip count.

```bash
uv run pytest -q                      # note "N skipped"
uv run pytest -q -rs                  # show exactly which shells were skipped
brew install fish                     # then fish is covered too
```

macOS ships zsh and bash, so those run by default; **fish must be installed to be covered.** Two bugs in this area were shipped precisely because a shell's own control flow was never executed — a local named `status` (read-only in both zsh and fish) and a load-time prompt snapshot that froze dynamic prompts.

### Non-TTY tests must use a subprocess

`CliRunner(input="")` is **not** a faithful non-TTY harness — it reports no abort where a real `< /dev/null` pipe does. Test non-TTY fallbacks with `subprocess.run(..., stdin=subprocess.DEVNULL)`. For the same reason, prefer catching `click.Abort`/`EOFError` over checking `sys.stdin.isatty()`: stdin is not a TTY under `CliRunner` even when input has been piped in.

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

### Shipped

- **PyPI publication** — `uv tool install why-cli` works; releases are automated (see `.github/workflows/release.yml`).
- **Task sessions + opt-in LLM recaps** (2.2.0) — `why follow`, `why recall`, `why sessions`, `why llm`, and the `/sessions` + `/settings/llm` web views. This was not on the original roadmap; it is recorded here so the plan matches the product.
- **Stale shell-hook auto-refresh** (2.3.0) — `WHY_HOOK_VERSION` is finally read. Any user-facing command rewrites an out-of-date `~/.why/hook.*` in place and prints a one-time notice. Half of roadmap item 1; see "Shell-hook auto-refresh" in `configuration.md`.

### Next, in rough priority order

1. **Update discovery.** The stale-hook half of upgrade ergonomics shipped in 2.3.0, but nothing still checks whether a newer `why-cli` exists — the user has to decide to run `uv tool upgrade why-cli` on their own. Deliberately deferred: it is a network call on a local-first tool and needs its own privacy decision, opt-out, and cache design. See "Upgrade path" below.
2. **UI editor for `patterns.toml` and `presentation.toml`.** `/settings` currently manages purposes only.
3. **Homebrew tap.**
4. **Sync** (pluggable backend + auth). Schema already carries `sync_id` / `updated_at` / `deleted` on every table, including task sessions.
5. **AI supplementation** — enrich `what_it_does` / `why` from the command plus a scraped homepage. Cheaper than originally scoped: 2.2.0 already ships the `[llm]` config block and an OpenAI-compatible client (`why/llm.py`) that this can reuse rather than rebuild.
6. **Source scraping.** `source_url` exists on `installs` and is displayed, but nothing populates it.
7. **One-click remote install.**

### Known follow-ups

- **TestPyPI has no trusted publisher.** `workflow_dispatch` runs the full gate and then fails at publish with `invalid-publisher`. Everything before that step is still a useful dry run — it is how the missing-shells gap in CI was found — but configuring it at test.pypi.org would make the rehearsal complete.
- **`.github/workflows/release.yml` `Auto-tag main`** is now gated on `github.ref == 'refs/heads/main'`. Without that, a dispatch from a feature branch tags that branch and the stray tag makes the next real merge skip its release.

## Upgrade path

What happens today when a user upgrades:

| Concern | Status |
|---|---|
| Schema migrations | **Automatic.** `ensure_ready()` runs `migrate()` on every command, with a pre-migration backup in `~/.why/backups/`. |
| New config keys | **Automatic.** `load_config()` deep-merges over current defaults. |
| Shell hook refresh | **Automatic since 2.3.0.** Every user-facing command compares `WHY_HOOK_VERSION` in each installed `~/.why/hook.*` against the packaged one and rewrites in place, printing a one-time notice on stderr. Suppressed for `_hook` / `_record` / `init` / `uninstall` and whenever `WHY_SUPPRESS` is set. |
| Knowing an update exists | **Nothing.** No version check anywhere. |

The last row is what's left of roadmap item 1.

Notes for anyone touching the hook refresh:

- The check lives in the `main()` Typer group callback (`cli.py`), **not** `ensure_ready()`. `ensure_ready()` also runs from `why/web/deps.py` and the init wizard, and sits on the per-prompt hot path via `why _record` — a `console.print` there would land in server logs or corrupt the terminal.
- The notice goes to **stderr** because `why export` writes markdown to stdout and `why follow status --porcelain` is machine-parsed. Same tty either way, so the user still sees it.
- **Bump `WHY_HOOK_VERSION` in all three hook scripts** whenever you change hook behaviour. `tests/unit/test_hook_refresh.py` fails if the three drift apart or a marker goes missing. Never assert a literal version in a test — derive it from `packaged_hook_version()`.

## Contributing

- One change per PR. Keep diffs small.
- Match the existing structure: pure modules stay pure; web reads/writes through `why.store`; CLI doesn't import `why.web`.
- Tests with the change. TDD if you can.
- Bump the version (see `CLAUDE.md`).
- Make sure ruff and mypy stay clean.
