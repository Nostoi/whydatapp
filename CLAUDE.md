# CLAUDE.md — whydatApp

Project-level guidance for AI assistants working in this repo.

## Versioning

Version lives in **two** files and **must stay in sync**:

- `pyproject.toml` — `[project] version`
- `src/why/__init__.py` — `__version__`

### Bump rules (SemVer: `MAJOR.MINOR.PATCH`)

- **PATCH** (`x.y.Z+1`): bug fixes, internal refactors, doc/typo fixes, dependency bumps that don't change behavior, test-only changes.
- **MINOR** (`x.Y+1.0`): new commands, new flags, new web routes, new CLI/HTTP behavior — additive only, no breaking changes.
- **MAJOR** (`X+1.0.0`): schema migrations that aren't fully backward-compatible, removed/renamed CLI commands or flags, removed/changed HTTP routes, breaking config/file-format changes.

If a single push contains changes that would warrant different bumps, take the highest. Pre-1.0 conventions don't apply — we shipped 1.0 at MVP.

### Required before every push

1. Decide the bump per the rules above.
2. Update **both** `pyproject.toml` and `src/why/__init__.py` to the new version.
3. Run the gate (must all pass):
   ```
   uv run pytest -q
   uv run ruff check src tests
   uv run mypy src/why
   ```
4. Commit the version bump as part of the change (don't make it a standalone "chore: bump version" commit unless the only thing changing is the version).
5. Push.

If you forget the bump and the push already happened, push a follow-up that bumps PATCH at minimum.

## Code conventions

- Python 3.11+. `uv` for env + builds. `ruff` + `mypy --strict` must stay clean.
- Pure modules (`store`, `detect`, `resolve`, `markdown`, `project_infer`, `filters`) take no I/O beyond what their purpose requires and have no FastAPI/Typer imports.
- Web routes only read/write through `why.store`. The CLI never imports from `why.web`. The shell hook never contains business logic — it shells out to `why _hook`.
- Tests live in `tests/unit/` (pure) and `tests/integration/` (CLI runner, FastAPI TestClient, real shells). Use the `why_home` fixture (in `tests/conftest.py`) to isolate `~/.why` per test.
- New web templates compose existing partials in `src/why/web/templates/components/`. Don't introduce new component styles inside page templates.

## Project layout

- Spec: `docs/superpowers/specs/2026-04-29-whydatapp-design.md`
- Plans: `docs/superpowers/plans/2026-04-29-plan-{1-core-cli,2-web-ui,3-distribution-init}.md`
- Logos: `docs/assets/whydatapp-{light,dark}.png`
