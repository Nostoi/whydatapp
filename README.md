<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Nostoi/whydatapp/main/docs/assets/whydatapp-dark.png">
    <img src="https://raw.githubusercontent.com/Nostoi/whydatapp/main/docs/assets/whydatapp-light.png" alt="whydatApp" width="320">
  </picture>
</p>

<p align="center">
  <a href="https://pypi.org/project/why-cli/"><img src="https://img.shields.io/pypi/v/why-cli.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/why-cli/"><img src="https://img.shields.io/pypi/pyversions/why-cli.svg" alt="Python"></a>
  <a href="https://github.com/Nostoi/whydatapp/blob/main/LICENSE"><img src="https://img.shields.io/pypi/l/why-cli.svg" alt="License"></a>
</p>

# whydatApp (`why?`)

Ever install something, then months later wonder *why* it's on your machine?

`why?` catches every package manager install (`brew`, `npm`, `pip`, `cargo`, `apt`, …) right as it happens via a lightweight shell hook, then prompts you to jot down what the tool is for, which project needed it, whether it's worth keeping, and what to do with it later. Everything stays in a local SQLite database — nothing is sent anywhere. Browse, search, filter, and export your install history through a built-in web UI, or right from the terminal.

**What you can answer with `why?`:**

- **What do I have installed?** — Full inventory across all package managers in one place
- **Why did I install this?** — Context captured at install time, while you remember
- **Which project needed it?** — Auto-inferred from your working directory
- **Is this still useful?** — Mark tools as experimental, for removal, or permanent docs
- **What's taking up space?** — See resolved install paths and identify candidates to uninstall
- **Did I ever install X?** — Search by name, command, or description — find it instantly
- **What should I clean up?** — Review queue surfaces incomplete entries and stale experimental installs
- **How do I set up this project elsewhere?** — Export your setup dependencies to Markdown or JSON
- **Which managers do I use most?** — Dashboard shows install trends by manager, project, and month

## Screenshots

**The shell hook catches installs as they happen and prompts you inline:**

<p align="center">
  <img src="https://raw.githubusercontent.com/Nostoi/whydatapp/main/docs/assets/screenshot-hook-prompt.png" alt="Shell hook capturing brew install sl with interactive prompt" width="780">
</p>

**Browse and filter your full install history in the web UI:**

<p align="center">
  <img src="https://raw.githubusercontent.com/Nostoi/whydatapp/main/docs/assets/screenshot-web-installs.jpg" alt="Web UI — Installs list with filters and purpose badges" width="780">
</p>

**The dashboard shows installs by purpose, manager, project, and trend over time:**

<p align="center">
  <img src="https://raw.githubusercontent.com/Nostoi/whydatapp/main/docs/assets/screenshot-web-dashboard.jpg" alt="Web UI — Dashboard with stats, breakdowns, and installs-per-month chart" width="780">
</p>

<details>
<summary>More screenshots — edit modal, purposes, CLI commands</summary>

**Edit any entry directly in the web UI:**

<p align="center">
  <img src="https://raw.githubusercontent.com/Nostoi/whydatapp/main/docs/assets/screenshot-web-edit.jpg" alt="Web UI — Edit install modal" width="780">
</p>

**Customize or add your own purpose categories:**

<p align="center">
  <img src="https://raw.githubusercontent.com/Nostoi/whydatapp/main/docs/assets/screenshot-web-purposes.jpg" alt="Web UI — Purpose categories management" width="780">
</p>

**The CLI: `why` help, `why list`, and `why show`:**

<p align="center">
  <img src="https://raw.githubusercontent.com/Nostoi/whydatapp/main/docs/assets/screenshot-cli-overview.png" alt="why help and why list output" width="780">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/Nostoi/whydatapp/main/docs/assets/screenshot-show.png" alt="why show — full details for a single install" width="780">
</p>

**The hook also captures removals:**

<p align="center">
  <img src="https://raw.githubusercontent.com/Nostoi/whydatapp/main/docs/assets/screenshot-hook-remove.png" alt="Shell hook capturing brew uninstall with removal reason prompt" width="780">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/Nostoi/whydatapp/main/docs/assets/screenshot-serve.png" alt="why serve — web UI startup" width="780">
</p>

</details>

## Install

**From PyPI** (recommended):

```bash
uv tool install 'why-cli[web]'   # or: pipx install 'why-cli[web]'
why init                          # interactive setup; edits your shell rc
```

**From source** (for development or pre-release):

```bash
git clone https://github.com/Nostoi/whydatapp.git
cd whydatapp
uv tool install --editable '.[web]'
why init
```

Restart your shell, then try `brew install ripgrep` (or any tracked manager).

Full install instructions, including building from a wheel: **[Install guide](https://github.com/Nostoi/whydatapp/blob/main/docs/guide/install.md)**.

## Quick reference

| Command           | What it does                                   |
|-------------------|------------------------------------------------|
| `why init`        | Interactive first-run setup                    |
| `why`             | Show help and the available subcommands        |
| `why log -- <cmd>`| Manually log an install                        |
| `why review`      | Drain the skipped/incomplete review queue      |
| `why list`        | Print installs as a table                      |
| `why export`      | Export to Markdown or JSON                     |
| `why serve`       | Open the local web UI at `127.0.0.1:7873`      |
| `why uninstall`   | Remove the hook (and optionally the data)      |

Detailed usage with examples: **[Usage guide](https://github.com/Nostoi/whydatapp/blob/main/docs/guide/usage.md)**.

## Documentation

- **[Install](https://github.com/Nostoi/whydatapp/blob/main/docs/guide/install.md)** — Requirements, install paths (PyPI / source / wheel), what `why init` does, uninstall.
- **[Usage](https://github.com/Nostoi/whydatapp/blob/main/docs/guide/usage.md)** — Every CLI subcommand with examples.
- **[Web UI](https://github.com/Nostoi/whydatapp/blob/main/docs/guide/web-ui.md)** — Walkthrough of the local web interface.
- **[Configuration](https://github.com/Nostoi/whydatapp/blob/main/docs/guide/configuration.md)** — `~/.why/*.toml` files, env vars, ignore rules.
- **[Troubleshooting](https://github.com/Nostoi/whydatapp/blob/main/docs/guide/troubleshooting.md)** — Hook not firing, prompt missed, address-in-use, restoring data, filing bugs.
- **[Development](https://github.com/Nostoi/whydatapp/blob/main/docs/guide/development.md)** — Clone, set up, run tests, build the wheel, project layout, contribute.
- **[Changelog](https://github.com/Nostoi/whydatapp/blob/main/CHANGELOG.md)** — Release history.
- **[Design spec](https://github.com/Nostoi/whydatapp/blob/main/docs/superpowers/specs/2026-04-29-whydatapp-design.md)** — Architecture, data model, decisions, post-MVP roadmap.

## Privacy

- All data lives in `~/.why/data.db`. No network calls.
- The web UI binds to `127.0.0.1` only.
- All static assets vendored locally — no CDN, no Google Fonts, no analytics.
- The shell hook ignores any install triggered by another tracked installer (no false positives from `brew` resolving deps).

## License

[MIT](https://github.com/Nostoi/whydatapp/blob/main/LICENSE)
