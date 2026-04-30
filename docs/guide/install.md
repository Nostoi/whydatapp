# Installation

> **Status:** whydatApp is not yet published to PyPI. The install paths below assume you are installing from source or from a locally built wheel. PyPI publication is on the post-1.0 roadmap.

## Requirements

- Python **3.11+**
- macOS (zsh, bash) or Linux (zsh, bash, fish). Windows is not supported.
- One of: [`uv`](https://docs.astral.sh/uv/) (recommended) or [`pipx`](https://pipx.pypa.io/).

## Option A — From source (recommended for now)

```bash
git clone https://github.com/Nostoi/whydatapp.git
cd whydatapp
uv tool install --from . 'why-cli[web]'
why init
```

`pipx` works the same way:

```bash
pipx install --pip-args='-e' '.[web]'   # editable install
why init
```

## Option B — From a built wheel

```bash
git clone https://github.com/Nostoi/whydatapp.git
cd whydatapp
uv build                                  # produces dist/why_cli-*.whl
uv tool install --from ./dist/why_cli-1.0.1-py3-none-any.whl 'why-cli[web]'
why init
```

## Option C — From PyPI (planned)

Once whydatApp is published, this will be the canonical path:

```bash
uv tool install 'why-cli[web]'   # or: pipx install 'why-cli[web]'
why init
```

The `[web]` extra installs FastAPI, uvicorn, Jinja2, and friends. If you only want the CLI logger and don't need `why serve`, omit the extra.

## What `why init` does

`why init` is interactive and idempotent — re-running it is safe.

1. Detects your shell (zsh / bash / fish) and confirms the rc file path.
2. Prompts for a device label (defaults to your hostname).
3. Lets you toggle each Tier-1 manager on/off (all on by default): `brew`, `npm`, `pnpm`, `yarn`, `bun`, `pip`, `pipx`, `uv`, `cargo`, `git`.
4. Offers Tier-2 opt-in (`gem`, `go`, `apt`, `mas`, `vscode`, `docker` — all off by default).
5. Asks for the web UI port (default `7873`) and whether to autostart on login (launchd on macOS, systemd-user on Linux).
6. Appends a fenced hook block to your rc file:
   ```
   # >>> why-cli hook >>>
   [ -f ~/.why/hook.zsh ] && source ~/.why/hook.zsh
   # <<< why-cli hook <<<
   ```
7. Creates `~/.why/` with `data.db`, `config.toml`, the shell hook script, and a backups directory.

After it finishes, restart your shell (or `source ~/.zshrc`) and try a small install — e.g. `brew install ripgrep`.

## Uninstall

```bash
why uninstall
```

Removes the rc-file hook block and any autostart unit. It asks before deleting `~/.why/`; answer `n` to keep your install history, `y` to wipe it.

## Next steps

- [Usage](usage.md) — every CLI subcommand with examples.
- [Configuration](configuration.md) — `~/.why/*.toml` files, env vars.
- [Web UI](web-ui.md) — walkthrough of the local web interface.
- [Troubleshooting](troubleshooting.md) — when the hook doesn't fire, when prompts don't appear, etc.
