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

## Documentation

User-facing docs live under `docs/guide/`. They are part of the contract, not an afterthought — **if your change affects how a user installs, runs, configures, or troubleshoots whydatApp, the docs must be updated in the same commit.**

### The doc map

| File                             | Owns                                                                  |
|----------------------------------|-----------------------------------------------------------------------|
| `README.md`                      | One-page overview, install snippet, quick command reference, doc index. |
| `docs/guide/install.md`          | Install paths, requirements, `why init` walkthrough, uninstall.       |
| `docs/guide/usage.md`            | Every CLI subcommand, flags, exit codes, capture-flow walkthrough.    |
| `docs/guide/web-ui.md`           | Web UI views, filters, sharing/export, customization.                 |
| `docs/guide/configuration.md`    | `~/.why/*.toml` schemas, env vars, ignore rules, FS layout.           |
| `docs/guide/troubleshooting.md`  | Symptom → cause → fix recipes.                                        |
| `docs/guide/development.md`      | Clone/setup/test/build/contribute, project layout, roadmap.           |
| `docs/superpowers/specs/`        | Design specs. Historical record + design rationale. Edit with care.   |
| `docs/superpowers/plans/`        | Implementation plans. Append new plans; don't rewrite finished ones.  |
| `docs/assets/`                   | Logos and images referenced by README and templates.                  |

### When to UPDATE an existing doc

Update the relevant doc(s) **before** you push, in the same commit as the code change.

| Code change                                         | Update at minimum                                  |
|-----------------------------------------------------|----------------------------------------------------|
| New / removed / renamed CLI subcommand or flag      | `usage.md`, `README.md` quick-reference table      |
| Changed prompt copy or capture flow                 | `usage.md`                                         |
| New / changed `~/.why/*.toml` key or default        | `configuration.md`                                 |
| New / changed env var                               | `configuration.md` env-vars table                  |
| New / changed schema column or table                | `configuration.md` Database section                |
| New / removed pattern or ignore rule                | `configuration.md` Ignore-rules section            |
| New / changed web route, filter, or button          | `web-ui.md`                                        |
| New install path or requirement                     | `install.md`, `README.md` install section          |
| New autostart unit, hook script, or shell support   | `install.md`, `troubleshooting.md`                 |
| New common error or failure mode                    | `troubleshooting.md`                               |
| New dev-time tool, build step, test pattern         | `development.md`                                   |
| New post-MVP item shipped, or roadmap reordering    | `development.md` Roadmap, `README.md` Status       |
| New top-level feature worth a paragraph             | `README.md` overview + add link if a new doc spawned |

A change that touches multiple categories updates multiple docs. Don't skip "small" updates — a flag rename without a doc update creates a hidden contract break.

### When to CREATE a new doc

Create a new file under `docs/guide/` (and link it from `README.md`'s Documentation list and from any related doc) when:

- A new feature has its own surface that won't fit cleanly in any existing file (e.g., when sync ships → `docs/guide/sync.md`; when AI enrichment ships → `docs/guide/ai.md`).
- A topic in an existing doc has grown past ~400 lines and splitting it improves findability.
- You're documenting a separate audience (e.g., a `docs/guide/api.md` if/when there's a stable HTTP API for third-party tools).

Naming: lowercase, hyphenated, `.md`. Match the heading style of existing guides (one H1 = the title, H2 sections, terse bullet lists, examples in fenced code blocks).

A new doc must:
1. Be linked from `README.md`'s Documentation section.
2. Be cross-linked from any existing doc that references the topic.
3. Match the tone of the existing guides — concise, factual, example-driven, no marketing copy.

### When to DELETE a doc

Delete a doc when its subject is genuinely gone — a feature was removed, a workflow was replaced, or the file was a temporary plan that's been superseded. When you delete:

1. Remove the link from `README.md`'s Documentation section.
2. Search for cross-links (`grep -r 'docs/guide/<file>' .`) and update or remove every one.
3. If the deleted topic merged into another doc, mention that in the commit message so the move is traceable.

Spec and plan files in `docs/superpowers/` are historical records — **do not delete them.** Mark a plan as superseded by editing its top section if needed.

### Pre-push gate (docs)

Before every push, in addition to the version bump and the test/lint gate:

1. Decide which docs (if any) the change affects.
2. Update them in the same commit as the code.
3. Verify links: `grep -r '\](docs/' README.md docs/` should resolve. Any new doc must be linked from `README.md`.
4. Re-read your update with fresh eyes — does a new user have everything they need to use this feature?

If a code change is genuinely doc-neutral (internal refactor, test-only change, dependency bump that doesn't touch behavior), state that in the commit message: `docs: none (internal refactor)`. Skipping the docs check silently is not allowed.

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
