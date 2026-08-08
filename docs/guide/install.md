# Installation

## Requirements

- Python **3.11+**
- macOS (zsh, bash) or Linux (zsh, bash, fish). Windows is not supported.
- One of: [`uv`](https://docs.astral.sh/uv/) (recommended) or [`pipx`](https://pipx.pypa.io/).

## Option A — From PyPI (recommended)

```bash
uv tool install 'why-cli[web]'    # or: pipx install 'why-cli[web]'
why init
```

The `[web]` extra installs FastAPI, uvicorn, Jinja2, and friends. If you only want the CLI logger and don't need `why serve`, omit the extra:

```bash
uv tool install why-cli           # CLI only, no web UI
```

To upgrade later:

```bash
uv tool upgrade why-cli           # or: pipx upgrade why-cli
```

That is the whole procedure. Everything else catches up on its own the next time you
run any `why` command:

| Concern | What happens |
|---|---|
| Database schema | Migrated automatically, after a backup into `~/.why/backups/`. |
| New config keys | Merged into `~/.why/config.toml` over the current defaults. |
| Shell hook (`~/.why/hook.*`) | Rewritten automatically when it predates the installed version (2.3.0+). You'll see `↻ zsh shell hook updated (v2 → v3)`. |

The one thing whydatApp can't do for you is restart your shell — the old hook functions
live in the running shell's memory until it reloads. When you see the refresh notice,
open a new terminal or run `exec $SHELL -l` at your convenience. Nothing breaks in the
meantime; you're just still on the old hook.

Re-running `why init` after an upgrade is no longer necessary. It remains safe, and is
still how you *change* settings or reinstall the rc-file block if you removed it.

## Option B — From source (for development or pre-release)

```bash
git clone https://github.com/Nostoi/whydatapp.git
cd whydatapp
uv tool install --editable '.[web]'   # editable: live-reflects your edits
why init
```

`pipx` works the same way:

```bash
pipx install --editable '.[web]'
why init
```

If you don't need the web UI, drop the extra:

```bash
uv tool install --editable .
```

## Option C — From a locally built wheel

```bash
git clone https://github.com/Nostoi/whydatapp.git
cd whydatapp
uv build                          # produces dist/why_cli-*.whl
uv tool install ./dist/why_cli-1.2.0-py3-none-any.whl
# To include the web extra from a wheel:
uv tool install './dist/why_cli-1.2.0-py3-none-any.whl[web]'
why init
```

## What `why init` does

`why init` is interactive and idempotent — re-running it is safe.

1. Detects your shell (zsh / bash / fish) and confirms the rc file path.
2. Prompts for a device label (defaults to your hostname).
3. Lets you toggle each Tier-1 manager on/off (all on by default): `brew`, `npm`, `pnpm`, `yarn`, `bun`, `pip`, `pipx`, `uv`, `cargo`, `gh`, `git`.
4. Offers Tier-2 opt-in (`gem`, `go`, `apt`, `mas`, `vscode`, `docker` — all off by default).
5. Asks for the web UI port (default `7873`) and whether to autostart on login (launchd on macOS, systemd-user on Linux).
6. Appends a fenced hook block to your rc file:
   ```
   # >>> why-cli hook >>>
   [ -f ~/.why/hook.zsh ] && source ~/.why/hook.zsh
   # <<< why-cli hook <<<
   ```
7. Creates `~/.why/` with `data.db`, `config.toml`, the shell hook script, and a backups directory.
8. **Offers to reload your shell** so the hook activates immediately. This is opt-in and skipped silently in non-TTY contexts (scripts, CI, Dockerfiles). Answering `y` runs `exec $SHELL -l`, replacing the current shell with a fresh login shell — any background jobs and unsaved env in this session are lost. Set `WHY_INIT_NO_RELOAD=1` to suppress the prompt entirely.

If you decline the reload (or skip it in a script), restart your shell or run `source ~/.zshrc` before your first `brew install ripgrep` — the hook won't fire until your shell re-sources its rc file.

`why init` does not force LLM setup. Configure optional task recaps later with
`why llm configure` or in the web UI under **LLM**.

## Uninstall

```bash
why uninstall
```

Removes the rc-file hook block, the `~/.why/hook.*` scripts themselves (all shells, not just your current one), and any autostart unit. It then asks before deleting `~/.why/`; answer `n` to keep your install history, `y` to wipe it.

Answering `n` leaves a working `~/.why` you can still browse with `why list` and `why serve`; re-run `why init` whenever you want capture back.

## Next steps

- [Usage](usage.md) — every CLI subcommand with examples.
- [Configuration](configuration.md) — `~/.why/*.toml` files, env vars.
- [Web UI](web-ui.md) — walkthrough of the local web interface.
- [Troubleshooting](troubleshooting.md) — when the hook doesn't fire, when prompts don't appear, etc.
