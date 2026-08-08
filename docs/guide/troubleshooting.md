# Troubleshooting

## I installed something but no prompt appeared (versions ≤ 1.1.0)

Upgrade. `1.0.x` and `1.1.0` had a bug where the Python `_hook` process treated the shell-level recursion-guard env var (`WHY_SUPPRESS=1`) as a self-ignore signal, silently cancelling every capture. Fixed in **1.1.1**:

```bash
uv tool upgrade why-cli
# or for editable installs from source:
git pull
```

If you're on 1.1.1+ and still don't see the prompt, the section below applies.

## `why follow` or `why recall` is not recording commands

These commands require the newer shell hook. Upgrade the package, then refresh
the copied hook script and rc block:

```bash
uv tool upgrade why-cli
why init
```

Restart or reload your shell afterwards. Existing install capture may keep
working with an older hook, but follow/recall recording needs the hook that
calls `why _record`.

## Errors on every prompt, or `[why rec]` never appears (versions ≤ 2.1.0)

If your terminal prints something like `read-only variable: status` (zsh) or
`set: Tried to modify the special variable 'status'` (fish) on every prompt, you are
running an older hook. In zsh this also silently disabled **all** capture — installs
included. Refresh the hook:

```bash
uv tool upgrade why-cli
why init
```

Then restart your shell. Related symptom on the same versions: a prompt that stops
updating (frozen git branch, stale directory) with starship, powerlevel10k, or any
theme that recomputes the prompt each draw. The current hook derives the indicator
from the live prompt, so it no longer freezes.

## Removing a saved transcript

Transcripts hold raw command history. There are two levels:

```bash
why sessions delete <id>          # hide it; the row stays in the database
why sessions delete <id> --purge  # erase the transcript, commands, and summaries
```

Only `--purge` actually removes the data from disk. The same two actions appear on the
session page in the web UI as **Delete** and **Erase transcript**.

## `why sessions summarize` failed

The CLI prints the reason and marks the session `failed`; it never dumps a traceback.
Common causes:

| Message | Cause |
|---|---|
| `LLM request timed out after Ns` | Endpoint too slow — a local model still loading, usually. Raise `timeout_seconds` in `[llm]`. |
| `LLM request failed: ... Connection refused` | Nothing listening at `base_url`. Check the endpoint and that your local server is running. |
| `LLM returned a non-JSON response` | Something returned HTML — often a proxy or SSO login page in front of the endpoint. |
| `LLM response did not include choices[0]...` | The endpoint is not OpenAI-compatible, or the model name is wrong. |
| `Invalid pattern ... in llm-ignore.toml` | A typo in your regex. The message names the offending pattern. |

Check connectivity before summarizing anything:

```bash
why llm test
```

This sends a one-word probe and exits non-zero if the endpoint is unreachable, the key
is wrong, or the response is malformed.

If a **key** is the problem, note that only the variable named by `[llm].api_key_env`
is read — there is no fallback to any other environment variable.

In the **web UI** a failed summarize shows the session as `failed`; the reason is
written to `~/.why/hook.log`:

```bash
tail -20 ~/.why/hook.log
```

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

If your install pattern is unusual (a custom installer script, `flatpak`, `pkg add`, …), add a pattern to `~/.why/patterns.toml`. Prefer a named `(?P<package>...)` group; otherwise whydatApp uses the last non-flag token as the package name.

## The hook captures things I don't want

- **Tool-installs-its-own-deps cases** (e.g., `brew` shelling to `curl`) are auto-ignored — the hook checks the parent process name. If something slips through, file an issue with the parent name and we'll add it to `IGNORED_PARENTS`.
- **Always ignore a specific pattern**: add it to `~/.why/ignore.toml`:
  ```toml
  patterns = [
    "^pip install -e \\.",
    "^npm install --save-dev"
  ]
  ```
- **Toggle a whole manager off**: re-run `why init` and answer `n` to the manager's prompt, or edit `~/.why/config.toml` and set that manager under `[managers]` to `false`. The hook ignores disabled managers for both installs and supported uninstalls.
- **Keep a command local but exclude it from LLM summaries**: add a regex to
  `~/.why/llm-ignore.toml`. This does not remove the command from local
  transcripts.

## I want to inspect what would be sent to the LLM

Use:

```bash
why sessions summarize <id> --print-payload
```

Redaction is best-effort. Review the payload before using remote endpoints when
commands or paths might contain sensitive project names, tokens, or customer
details.

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
