# Troubleshooting

## The hook isn't firing after I install something

1. **Did you restart your shell?** The rc-file change only takes effect in new sessions. Either open a new terminal or `source ~/.zshrc` (or `~/.bashrc`, `~/.config/fish/config.fish`).
2. **Confirm the hook block is in your rc file.** Look for:
   ```
   # >>> why-cli hook >>>
   [ -f ~/.why/hook.zsh ] && source ~/.why/hook.zsh
   # <<< why-cli hook <<<
   ```
   If missing, run `why init` again.
3. **Confirm the hook script exists.** `ls ~/.why/hook.{zsh,bash,fish}` should show your shell's variant.
4. **Tail the hook error log.** Any failure inside the hook is silently logged here (the hook never breaks your terminal):
   ```bash
   tail -f ~/.why/hook.log
   ```
5. **Try a manual log.** This bypasses the hook and tests the rest of the stack:
   ```bash
   why log -- brew install ripgrep
   ```
   If that works but the hook doesn't, the issue is in the shell-side wiring.

## The prompt fires but my command isn't recognized

The Tier-1 patterns are conservative on purpose (high signal, low false-positive). Tier-2 managers (`gem`, `go`, `apt`, `mas`, `vscode`, `docker`) are off by default. Re-run `why init` and opt in to the ones you want.

If your install pattern is unusual (a custom installer script, `flatpak`, `pkg add`, …), use `why log -- <cmd>` for now. Custom-pattern support via `~/.why/patterns.toml` is wired but not yet active in the matcher; it's a near-term follow-up.

## The hook captures things I don't want

- **Tool-installs-its-own-deps cases** (e.g., `brew` shelling to `curl`) are auto-ignored — the hook checks the parent process name. If something slips through, file an issue with the parent name and we'll add it to `IGNORED_PARENTS`.
- **Always ignore a specific pattern**: add it to `~/.why/ignore.toml`:
  ```toml
  patterns = [
    "^pip install -e \\.",
    "^npm install --save-dev"
  ]
  ```
- **Toggle a whole manager off**: re-run `why init` and answer `n` to the manager's prompt. (Per-manager toggle enforcement at hook time is rolling out as a follow-up; the patterns are on by default in the meantime.)

## "recent duplicate; skipping" appeared and I didn't expect it

The hook debounces identical `(command, cwd)` events that fire within 60 seconds. If you genuinely re-ran a real install you want to log, use `why log -- <cmd>` to force it.

## The web UI shows old data after I edited a row

HTMX swaps the row in place after each save. If you see staleness, hard-reload (`⌘⇧R` / `Ctrl-F5`) — but report it; that's a bug.

## "CSRF token missing or invalid" on POST

Almost always means the cookie wasn't issued (you hit a POST endpoint without first loading a page). In normal browser use you won't see this. If you're scripting against the API, GET any page once to receive the `why_csrf` cookie, then send the cookie value back as either an `X-CSRF-Token` header or a `csrf_token` form field.

## `why serve` fails with "Address already in use"

Either another `why serve` is running or another process owns port 7873. Find it:

```bash
lsof -iTCP:7873 -sTCP:LISTEN
```

Either kill the old process or pick a different port: `why serve --port 8080`. To make the new port stick, edit `[web].port` in `~/.why/config.toml`.

## I want to start over

```bash
why uninstall
# Answer 'y' when it asks to delete the data directory.
```

That removes the rc-file hook block, any autostart unit, and `~/.why/`. Re-running `why init` afterwards is a clean slate.

## Backing up

Just copy `~/.why/data.db`. WAL is in use, so for a fully-flushed snapshot run:

```bash
sqlite3 ~/.why/data.db "VACUUM INTO '/path/to/why-backup.db'"
```

Pre-migration backups land in `~/.why/backups/` automatically.

## Restoring on a new machine

Until sync ships, the simplest path is:

1. Install whydatApp on the new machine and run `why init`.
2. Stop any running `why serve`.
3. Copy your old `~/.why/data.db` over the new one.
4. Start the web UI again. Any new device will appear as a separate row in the `devices` table once you run `why init` on it.

## Filing a bug

Include:

- OS and shell.
- whydatApp version (`why --version`).
- Output of `tail -50 ~/.why/hook.log` if the hook is involved.
- The exact command that triggered the issue (and `echo $?` after it).

Open an issue at https://github.com/Nostoi/whydatapp/issues.
