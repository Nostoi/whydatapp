<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/whydatapp-dark.png">
    <img src="docs/assets/whydatapp-light.png" alt="whydatApp" width="320">
  </picture>
</p>

# whydatApp (`why?`)

Track *why* you installed every tool on your machine.

`why?` watches for installs (`brew install`, `npm i -g`, `pip install`, `cargo install`, `git clone`, …) via a tiny shell hook, and asks five quick questions: name, what it does, project, why, and what to do with it (document, add to setup script, experimental, remove later, ignore). Local-only SQLite. Local web UI for search, sort, and sharing. Privacy-focused — nothing leaves your machine.

## Install

```bash
uv tool install why-cli   # or: pipx install why-cli
why init                  # interactive setup; edits your shell rc
```

Restart your shell, then try `brew install ripgrep` (or any tracked manager).

## Use

| Command           | What it does                                   |
|-------------------|------------------------------------------------|
| `why log -- <cmd>`| Manually log an install                        |
| `why review`      | Drain the skipped/incomplete review queue      |
| `why list`        | Print installs as a table                      |
| `why export`      | Export to Markdown or JSON                     |
| `why serve`       | Open the local web UI at 127.0.0.1:7873        |
| `why uninstall`   | Remove the hook (and optionally the data)      |

## Privacy

- All data lives in `~/.why/data.db`. No network calls.
- The web UI binds to `127.0.0.1` only.
- The shell hook ignores any install triggered by another tracked installer (no false positives from `brew` resolving deps).

## Status

MVP. Sync, auth, AI enrichment, source scraping, and one-click remote install are on the roadmap. See `docs/superpowers/specs/` and `docs/superpowers/plans/` for the design.

## Known follow-ups

- Keyboard shortcuts in the web UI.
- Manual dark-mode toggle (currently follows OS).
- Golden snapshot tests for Jinja partials.
- `brew install why` Homebrew tap.
