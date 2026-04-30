# Web UI

A local web UI at `http://127.0.0.1:7873/`. Bound to localhost only — no remote access, no external traffic.

```bash
why serve              # opens the browser
why serve --no-open    # don't open
why serve --port 8080  # custom port
```

## Layout

A single-page-feel app (HTMX, no SPA build) with three views and a search box.

```
┌──────────────────────────────────────────────────────────────────┐
│ 🐘 whydatApp   [Installs] [Dashboard] [Review N]  🔍 search...   │
├──────────────────────────────────────────────────────────────────┤
│   (active view)                                                  │
└──────────────────────────────────────────────────────────────────┘
🔒 localhost · no network
```

The footer indicator is always present. When sync ships post-MVP, it will change to `🔒 localhost · sync paused` or `🔄 syncing to <endpoint>` — never hidden.

## Installs view (default)

Sortable, filterable table.

- **Filter pills** at the top: disposition (Doc / Setup / Experimental / Remove / Ignore), plus dropdowns for project, manager, device, and an "incomplete only" toggle.
- **Search box** in the header runs SQLite FTS5 across name, command, what-it-does, project, why, notes.
- **Sort** by clicking any column header.
- **Edit inline**: click the row's name → an edit form expands in place. Save commits and re-renders just the row.
- **Share** (per-row): returns the same Markdown snippet as the CLI's `why export --format md`.
- **Filters live in the URL** (`?disposition=experimental&manager=brew&q=ripgrep`). Back/forward navigation works; you can deep-link or bookmark a filtered view.

## Dashboard

Five cards:

- **By disposition** — counts per disposition.
- **By manager** — counts per manager, with icon and color from `presentation.toml`.
- **By project (top 10)** — clickable, links into a filtered Installs view.
- **Installs per month** — sparkline of the last 12 months.
- **Stale review queue** — combines: incomplete metadata, `experimental` items older than 30 days, and `remove` items older than 14 days that haven't been marked actually-removed. Each item links to its row in the Installs view.

## Review

A focused, one-at-a-time form for draining the skipped queue. Same fields as the CLI's `why review`. Save & next, Skip, or pick `Ignore` from the disposition dropdown.

The badge `Review N` in the nav bar shows queue size; it disappears when the queue is empty.

## Privacy posture

- Bound to `127.0.0.1` only.
- All static assets vendored locally — no CDN, no Google Fonts, no analytics.
- No outbound network calls.
- CSRF middleware on POST/PUT/DELETE (forward-compat for when auth lands).

## Keyboard shortcuts

Not yet implemented (it's on the [post-MVP roadmap](../superpowers/specs/2026-04-29-whydatapp-design.md#15-post-mvp-roadmap-priority-order)). The whole UI is mouse-and-form-driven for now.

## Customization

- Icons / colors / labels per manager and per disposition: edit `~/.why/presentation.toml`. See [Configuration](configuration.md#presentationtoml).
- Dark mode follows your OS preference (`prefers-color-scheme`). A manual toggle is on the roadmap.
