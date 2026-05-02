# Usage

Every subcommand of the `why` CLI, with examples.

## At a glance

| Command              | What it does                                        |
|----------------------|-----------------------------------------------------|
| `why init`           | First-run interactive setup (also re-runs safely).  |
| `why`                | Show the top-level help and command list.           |
| `why log -- <cmd>`   | Manually log an install (used by hook + by you).    |
| `why review`         | Drain the skipped/incomplete review queue.          |
| `why list`           | Print installs as a table, with filters.            |
| `why export`         | Export to Markdown or JSON.                         |
| `why delete <id>`    | Soft-delete an entry by id.                         |
| `why serve`          | Start the local web UI and open the browser.        |
| `why show <id>`      | Print full details + command history for an install. |
| `why purposes`       | Manage purpose categories (list/add/edit/delete).   |
| `why uninstall`      | Remove the hook (and optionally the data dir).      |
| `why --version`      | Print the installed version.                        |

## How capture works

## `why` — top-level help

Running `why` with no subcommand prints the same top-level help you get from `why --help` and exits successfully:

```bash
why
why --help
```

Use this when you want a quick reminder of the available subcommands and global flags.

When the shell hook is installed, `why` watches every command you run interactively. After a command exits successfully, it checks: did this look like a user-intent install? If yes, and none of the [ignore rules](configuration.md#ignore-rules) match, it runs the capture flow.

**Re-install enrichment** — if a complete record already exists for the same `(manager, package)` pair, the hook skips the prompt entirely and silently updates the existing entry:

```
↻ ripgrep re-installed (id=47, last seen 14d ago)
```

If only an incomplete record exists (you hit `[s]` the first time), the prompt is surfaced again, pre-filled from the prior entry. Filling it in updates the same row.

See [Re-installs](configuration.md#re-installs) in the configuration guide for the full rules.

Otherwise the prompt fires:

```
$ brew install ripgrep
🍺  /opt/homebrew/Cellar/ripgrep/14.1.0: 19 files, 6.3MB

📝 why? — captured: brew install ripgrep  (~/dev/projects/whydatapp)

  Purpose? [1] Reference  [2] Project setup  [3] Trying out  [4] Cleanup soon  [5] Ignore
  [s] Skip for now    [q] Quit (treat as ignore)
> 1
  Display name [ripgrep]:
  What does it do? fast recursive grep written in rust
  Project [whydatapp]:
  Why install? need fast code search across all my repos
  Notes (optional, ↵ to skip):
  ✓ logged (id=1).
```

- The purpose is the only required field.
- `↵` accepts the suggested default (or skips, for optional fields).
- `[s]` saves the entry with metadata-incomplete; you'll see it in `why review` and on the dashboard's stale queue.
- `[q]` saves it with `purpose=ignore`. Permanent dismissal.
- `Ctrl-C` mid-prompt is treated as `[s]` — captures are never lost.

## `why log` — manual entry

For things the hook missed (curl-piped installers, GUI installs, retroactive logging):

```bash
why log -- brew install ripgrep
why log -- pipx install black
why log -- git clone https://github.com/foo/bar
```

Note the `--` separating `log` from the install command. Without it, your shell will try to interpret `--` flags. Behaviour is identical to the hook prompt above.

### `--enrich` flag

By default, `why log` **always creates a new entry**, even if one already exists for the same package. This lets you split history per project.

If you want `why log` to match hook behavior (update an existing complete entry instead of creating a new one), pass `--enrich`:

```bash
why log --enrich -- brew install ripgrep
```

This is the rare case — the shell hook handles enrichment automatically for most users.

If the command isn't recognized as an install pattern, you'll get exit code 2 and a yellow notice:

```
$ why log -- ls -la
not recognized as an install: ls -la
```

## `why list` — table view

```bash
why list                              # all installs (limit 50)
why list --purpose experimental   # filter by purpose
why list --project whydatapp          # filter by project
why list --manager brew               # filter by manager
why list --incomplete                 # only entries missing metadata
why list --limit 200                  # show more
```

## Uninstall capture

When you uninstall a package with a supported manager, the hook automatically records the removal — no extra steps needed.

```
$ brew uninstall ripgrep

📝 why? — captured removal: brew uninstall ripgrep

  Why did you remove it? (↵ to skip):
> no longer needed after switching to fd
  ✓ logged removal (id=1).
```

The removal prompt is always optional — pressing `↵`, `s`, or `Ctrl-C` records the timestamp and marks the entry removed without a reason. The entry stays in the database so your history is complete; it is just hidden from `why list` and the web UI by default.

**If the package was never logged** (e.g. installed before `why` was set up), a new removal-only row is created so the event isn't lost. The entry will appear in the review queue without a purpose.

**Exit code gate** — if the uninstall command exits non-zero, no removal is recorded.

### Supported managers (uninstall)

Same set as installs: `brew`, `npm`, `pnpm`, `yarn`, `bun`, `pip`/`pip3`, `pipx`, `uv`, `cargo`.
`git` / `gh` are not tracked (clones aren't uninstalls).

### Viewing removed entries

```bash
why list --show-removed          # include removed rows in table output
```

In the web UI, check **"Show removed"** in the filter bar.

## `why review` — drain the queue

Walks every entry where `metadata_complete=0` and prompts you for the metadata. Same prompts as the live capture flow.

```bash
why review
```

If the queue is empty, it just prints `Review queue is empty.` and exits.

## `why export` — Markdown or JSON

```bash
why export --format md   --out installs.md
why export --format json --out installs.json
why export --format md   --out doc-items.md  --purpose doc
why export --format md   --out project-x.md  --project x
```

The Markdown format produces one block per entry:

```markdown
**ripgrep** — `brew install ripgrep`
fast recursive grep written in rust
Installed 2026-04-29T19:32:11+00:00 in `/Users/you/dev/projects/whydatapp`
Why: need fast code search across all my repos
```

JSON contains the full row, including sync-related columns (`sync_id`, `updated_at`, `device_id`, `user_id`).

## `why delete <id>` — soft-delete

```bash
why delete 47
# Delete 'ripgrep'? [y/N]: y
# ✓ deleted (soft) id=47.

why delete 47 --yes   # skip confirmation
```

Soft-delete means the row is marked `deleted=1` and `updated_at` is bumped, but the row stays in the database (so future sync sees the tombstone). It no longer appears in `why list` or in the web UI.

## `why serve` — web UI

```bash
why serve                        # binds 127.0.0.1:7873, opens browser
why serve --no-open              # don't open browser
why serve --port 8080            # custom port
why serve --lan                  # expose to LAN (shortcut for --host 0.0.0.0)
why serve --host 0.0.0.0         # same as --lan
```

The startup banner shows the URL(s) the server is reachable on:

```
whydatApp v1.1.0 — web UI starting…
  → http://127.0.0.1:7873/
  localhost only · press Ctrl-C to stop
```

With `--lan` (or `--host 0.0.0.0`) it also enumerates your machine's LAN IP so you can hit it from another device:

```
whydatApp v1.1.0 — web UI starting…
  → http://127.0.0.1:7873/
  → http://192.168.1.42:7873/  (LAN)
  exposed to LAN — anyone on your network can reach this. Press Ctrl-C to stop.
```

LAN exposure is opt-in. There's no auth on the UI yet, so anyone on your network can read and edit your install history when `--lan` is on. Default (localhost only) is the safe choice. See [Web UI](web-ui.md) for the walkthrough.

## `why uninstall`

Removes the rc-file hook block and any autostart unit (`launchctl unload` on macOS, `systemctl --user disable` on Linux). Then asks whether to delete `~/.why/`:

```
✓ removed hook block from /Users/you/.zshrc
Also delete data directory /Users/you/.why? This wipes your install history. [y/N]:
```

Answer `n` (the default) to keep your data; answer `y` to wipe it.

## Exit codes

## `why purposes` — manage purpose categories

Purpose categories label why each install exists. Five built-in categories are
seeded on first run; you can edit them or add your own.

```
# List all categories
why purposes list

# Add a custom category
why purposes add --key work --label "Work" --color "#f59e0b" --sort-order 10

# Edit an existing category (built-ins included)
why purposes edit doc --label "Reference docs"

# Delete a custom category (built-ins are protected)
why purposes delete work
```

You can also manage categories from the web UI at **Settings → Purposes**
(`/settings/purposes`).

## Exit codes

| Code | Meaning                                          |
|------|--------------------------------------------------|
| 0    | Success.                                         |
| 1    | Generic error (e.g., id not found in `delete`).  |
| 2    | Invalid input (e.g., unrecognized install cmd).  |

The `_hook` subcommand always exits 0 — the shell hook must never break your terminal.

## `why show <id>` — inspect an install

Print full metadata and command history for a single install by ID:

```
why show 42
```

Output includes display name, manager, project, why, purpose, captured
timestamp, and — when available — the list of commands that ran immediately
before the install in that shell session.

IDs appear in `why list` output.
