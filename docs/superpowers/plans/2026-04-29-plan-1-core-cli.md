# why? — Plan 1: Core Data + Detection + CLI Capture

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working CLI-only install logger: SQLite store, pattern detection, ignore heuristics, path resolution, and the `why log` / `why review` / `why list` / `why export` subcommands. After this plan, the user can manually run `why log -- <command>` and capture metadata; the shell hook integration is Plan 3.

**Architecture:** Pure-function `store` and `detect` layers (no I/O outside SQLite for `store`); Typer-based CLI orchestrates prompts and calls those layers. SQLite with WAL + FTS5. Single `~/.why/` directory holds db + config + logs.

**Tech Stack:** Python 3.11+, Typer, Rich (prompts), tomli/tomli-w (config), pytest, ruff, mypy. Stdlib `sqlite3`, `uuid`, `pathlib`, `subprocess`. Package manager: `uv`.

---

## File Structure

```
whydatapp/
├── pyproject.toml
├── README.md
├── src/why/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                  # Typer app + all subcommands
│   ├── paths.py                # ~/.why path resolution (override via WHY_HOME)
│   ├── config.py               # config.toml + presentation.toml loaders
│   ├── store.py                # SQLite functions (pure)
│   ├── schema.py               # migration runner
│   ├── detect.py               # patterns + ignore rules + extractors (pure)
│   ├── resolve.py              # best-effort install path resolution
│   ├── prompts.py              # interactive metadata prompts (Rich)
│   ├── hook_runner.py          # `why _hook` entrypoint (used in Plan 3)
│   ├── presentation.toml       # default icons/colors per manager
│   └── migrations/
│       └── 001_init.sql
└── tests/
    ├── conftest.py
    ├── unit/
    │   ├── test_detect.py
    │   ├── test_store.py
    │   ├── test_resolve.py
    │   └── test_config.py
    └── integration/
        └── test_cli.py
```

---

## Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/why/__init__.py`
- Create: `src/why/__main__.py`
- Create: `tests/conftest.py`
- Create: `.gitignore`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "why-cli"
version = "0.1.0"
description = "Track why you installed every tool on your machine."
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "typer>=0.12",
  "rich>=13.7",
  "tomli-w>=1.0",
]

[project.scripts]
why = "why.cli:app"

[project.optional-dependencies]
web = []  # populated in Plan 2
dev = [
  "pytest>=8",
  "pytest-cov>=5",
  "ruff>=0.5",
  "mypy>=1.10",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/why"]

[tool.hatch.build.targets.wheel.force-include]
"src/why/migrations" = "why/migrations"
"src/why/presentation.toml" = "why/presentation.toml"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true
files = ["src/why"]
```

- [ ] **Step 2: Write `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
dist/
build/
*.egg-info/
.venv/
.coverage
htmlcov/
```

- [ ] **Step 3: Write minimal `README.md`**

```markdown
# why?

Track *why* you installed every tool on your machine.

Status: pre-MVP. See `docs/superpowers/specs/` for the design.
```

- [ ] **Step 4: Write `src/why/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 5: Write `src/why/__main__.py`**

```python
from why.cli import app

if __name__ == "__main__":
    app()
```

- [ ] **Step 6: Write `tests/conftest.py`**

```python
from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def why_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate ~/.why per test by setting WHY_HOME to a tmp dir."""
    home = tmp_path / "why"
    home.mkdir()
    monkeypatch.setenv("WHY_HOME", str(home))
    return home
```

- [ ] **Step 7: Install dev environment and verify**

Run: `uv venv && uv pip install -e '.[dev]'`
Expected: success. Then `uv run pytest -q`. Expected: `no tests ran`.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml README.md .gitignore src/why/__init__.py src/why/__main__.py tests/conftest.py
git commit -m "chore: project scaffolding for why-cli"
```

---

## Task 2: Path resolution

**Files:**
- Create: `src/why/paths.py`
- Create: `tests/unit/test_paths.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_paths.py
from __future__ import annotations

from pathlib import Path

import pytest

from why.paths import why_home, db_path, log_path, config_path


def test_why_home_uses_env_override(why_home: Path) -> None:
    assert why_home == why_home


def test_db_path_under_home(why_home: Path) -> None:
    assert db_path() == why_home / "data.db"


def test_log_paths_under_home(why_home: Path) -> None:
    assert log_path("hook") == why_home / "hook.log"
    assert log_path("web") == why_home / "web.log"


def test_config_path_under_home(why_home: Path) -> None:
    assert config_path("config") == why_home / "config.toml"
    assert config_path("presentation") == why_home / "presentation.toml"


def test_default_home_is_dotwhy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("WHY_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    from why import paths
    # Reimport-safe: function reads env each call.
    assert paths.why_home() == tmp_path / ".why"
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/test_paths.py -v`
Expected: ImportError / ModuleNotFoundError.

- [ ] **Step 3: Implement `paths.py`**

```python
# src/why/paths.py
from __future__ import annotations

import os
from pathlib import Path


def why_home() -> Path:
    override = os.environ.get("WHY_HOME")
    if override:
        return Path(override)
    return Path.home() / ".why"


def db_path() -> Path:
    return why_home() / "data.db"


def log_path(name: str) -> Path:
    return why_home() / f"{name}.log"


def config_path(name: str) -> Path:
    return why_home() / f"{name}.toml"


def ensure_home() -> Path:
    home = why_home()
    home.mkdir(parents=True, exist_ok=True)
    (home / "backups").mkdir(exist_ok=True)
    return home
```

- [ ] **Step 4: Run test to verify pass**

Run: `uv run pytest tests/unit/test_paths.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/why/paths.py tests/unit/test_paths.py
git commit -m "feat: path resolution honors WHY_HOME override"
```

---

## Task 3: Schema migration 001

**Files:**
- Create: `src/why/migrations/001_init.sql`
- Create: `src/why/schema.py`
- Create: `tests/unit/test_schema.py`

- [ ] **Step 1: Write `001_init.sql`**

```sql
-- src/why/migrations/001_init.sql
CREATE TABLE users (
  id            TEXT PRIMARY KEY,
  email         TEXT,
  display_name  TEXT,
  created_at    TEXT NOT NULL
);

CREATE TABLE devices (
  id            TEXT PRIMARY KEY,
  hostname      TEXT NOT NULL,
  label         TEXT,
  created_at    TEXT NOT NULL,
  last_seen_at  TEXT NOT NULL
);

CREATE TABLE projects (
  name          TEXT PRIMARY KEY,
  created_at    TEXT NOT NULL
);

CREATE TABLE installs (
  id                 INTEGER PRIMARY KEY,
  sync_id            TEXT NOT NULL UNIQUE,
  user_id            TEXT NOT NULL REFERENCES users(id),
  device_id          TEXT NOT NULL REFERENCES devices(id),
  command            TEXT NOT NULL,
  package_name       TEXT,
  manager            TEXT NOT NULL,
  install_dir        TEXT NOT NULL,
  resolved_path      TEXT,
  installed_at       TEXT NOT NULL,
  exit_code          INTEGER NOT NULL,
  display_name       TEXT,
  what_it_does       TEXT,
  project            TEXT,
  why                TEXT,
  disposition        TEXT,
  notes              TEXT,
  source_url         TEXT,
  metadata_complete  INTEGER NOT NULL DEFAULT 0,
  reviewed_at        TEXT,
  removed_at         TEXT,
  updated_at         TEXT NOT NULL,
  deleted            INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX installs_disposition ON installs(disposition);
CREATE INDEX installs_project     ON installs(project);
CREATE INDEX installs_manager     ON installs(manager);
CREATE INDEX installs_installed   ON installs(installed_at);
CREATE INDEX installs_device      ON installs(device_id);
CREATE INDEX installs_complete    ON installs(metadata_complete);

CREATE VIRTUAL TABLE installs_fts USING fts5(
  display_name, package_name, command, what_it_does, project, why, notes,
  content='installs', content_rowid='id'
);

CREATE TRIGGER installs_ai AFTER INSERT ON installs BEGIN
  INSERT INTO installs_fts(rowid, display_name, package_name, command, what_it_does, project, why, notes)
  VALUES (new.id, new.display_name, new.package_name, new.command, new.what_it_does, new.project, new.why, new.notes);
END;

CREATE TRIGGER installs_ad AFTER DELETE ON installs BEGIN
  INSERT INTO installs_fts(installs_fts, rowid, display_name, package_name, command, what_it_does, project, why, notes)
  VALUES ('delete', old.id, old.display_name, old.package_name, old.command, old.what_it_does, old.project, old.why, old.notes);
END;

CREATE TRIGGER installs_au AFTER UPDATE ON installs BEGIN
  INSERT INTO installs_fts(installs_fts, rowid, display_name, package_name, command, what_it_does, project, why, notes)
  VALUES ('delete', old.id, old.display_name, old.package_name, old.command, old.what_it_does, old.project, old.why, old.notes);
  INSERT INTO installs_fts(rowid, display_name, package_name, command, what_it_does, project, why, notes)
  VALUES (new.id, new.display_name, new.package_name, new.command, new.what_it_does, new.project, new.why, new.notes);
END;

CREATE TABLE schema_version (version INTEGER NOT NULL);
INSERT INTO schema_version(version) VALUES (1);
```

- [ ] **Step 2: Write the failing test**

```python
# tests/unit/test_schema.py
from __future__ import annotations

import sqlite3
from pathlib import Path

from why.schema import current_version, migrate


def test_migrate_creates_schema_v1(tmp_path: Path) -> None:
    db = tmp_path / "x.db"
    migrate(db)
    assert current_version(db) == 1
    with sqlite3.connect(db) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"users", "devices", "projects", "installs", "installs_fts", "schema_version"} <= tables


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "x.db"
    migrate(db)
    migrate(db)
    assert current_version(db) == 1


def test_migrate_creates_backup_when_db_exists(tmp_path: Path) -> None:
    db = tmp_path / "x.db"
    backups = tmp_path / "backups"
    backups.mkdir()
    db.write_bytes(b"")  # pretend pre-existing
    migrate(db, backups_dir=backups)
    # First-run migration on empty file should NOT make a backup; only later ones do.
    assert list(backups.iterdir()) == []
```

- [ ] **Step 3: Run test to verify failure**

Run: `uv run pytest tests/unit/test_schema.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `schema.py`**

```python
# src/why/schema.py
from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def current_version(db_path: Path) -> int:
    if not db_path.exists() or db_path.stat().st_size == 0:
        return 0
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchone()
        if not row:
            return 0
        v = conn.execute("SELECT version FROM schema_version").fetchone()
        return int(v[0]) if v else 0


def _backup(db_path: Path, backups_dir: Path) -> None:
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    shutil.copy2(db_path, backups_dir / f"data.{stamp}.db")


def _read_migration(n: int) -> str:
    return resources.files("why.migrations").joinpath(f"{n:03d}_init.sql").read_text()


MIGRATIONS = {1: lambda: _read_migration(1)}


def migrate(db_path: Path, backups_dir: Path | None = None) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    cur = current_version(db_path)
    target = max(MIGRATIONS)
    if cur == target:
        return
    if cur > 0 and backups_dir is not None:
        _backup(db_path, backups_dir)
    with _connect(db_path) as conn:
        for v in range(cur + 1, target + 1):
            if v == 1:
                conn.executescript(MIGRATIONS[v]())
            else:
                conn.executescript(MIGRATIONS[v]())
            conn.execute("UPDATE schema_version SET version = ?", (v,))
        conn.commit()
```

Add `src/why/migrations/__init__.py` (empty file) so `importlib.resources` finds the package.

- [ ] **Step 5: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_schema.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/why/migrations/ src/why/schema.py tests/unit/test_schema.py
git commit -m "feat: schema v1 migration with backups + idempotency"
```

---

## Task 4: Store — users, devices, projects

**Files:**
- Create: `src/why/store.py`
- Create: `tests/unit/test_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_store.py
from __future__ import annotations

from pathlib import Path

import pytest

from why import store
from why.schema import migrate


@pytest.fixture
def db(tmp_path: Path) -> Path:
    p = tmp_path / "data.db"
    migrate(p)
    return p


def test_create_and_get_user(db: Path) -> None:
    user = store.create_user(db, display_name="mark")
    assert user.id
    assert user.display_name == "mark"
    fetched = store.get_user(db, user.id)
    assert fetched == user


def test_create_and_get_device(db: Path) -> None:
    user = store.create_user(db, display_name="mark")
    device = store.create_device(db, hostname="mbp", label="work")
    fetched = store.get_device(db, device.id)
    assert fetched.hostname == "mbp"
    assert fetched.label == "work"


def test_upsert_project_dedupes(db: Path) -> None:
    store.upsert_project(db, "whydatapp")
    store.upsert_project(db, "whydatapp")
    assert store.list_projects(db) == ["whydatapp"]
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/test_store.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the user/device/project parts of `store.py`**

```python
# src/why/store.py
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return str(uuid.uuid4())


@contextmanager
def _conn(db_path: Path) -> Iterator[sqlite3.Connection]:
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c
        c.commit()
    finally:
        c.close()


@dataclass(frozen=True)
class User:
    id: str
    email: str | None
    display_name: str | None
    created_at: str


@dataclass(frozen=True)
class Device:
    id: str
    hostname: str
    label: str | None
    created_at: str
    last_seen_at: str


def create_user(db: Path, *, display_name: str | None = None, email: str | None = None) -> User:
    uid = _new_id()
    now = _now()
    with _conn(db) as c:
        c.execute(
            "INSERT INTO users(id,email,display_name,created_at) VALUES (?,?,?,?)",
            (uid, email, display_name, now),
        )
    return User(uid, email, display_name, now)


def get_user(db: Path, uid: str) -> User | None:
    with _conn(db) as c:
        r = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return User(**dict(r)) if r else None


def get_solo_user(db: Path) -> User | None:
    """Return the single user row in MVP single-user mode, or None."""
    with _conn(db) as c:
        r = c.execute("SELECT * FROM users LIMIT 1").fetchone()
    return User(**dict(r)) if r else None


def create_device(db: Path, *, hostname: str, label: str | None = None) -> Device:
    did = _new_id()
    now = _now()
    with _conn(db) as c:
        c.execute(
            "INSERT INTO devices(id,hostname,label,created_at,last_seen_at) VALUES (?,?,?,?,?)",
            (did, hostname, label, now, now),
        )
    return Device(did, hostname, label, now, now)


def get_device(db: Path, did: str) -> Device | None:
    with _conn(db) as c:
        r = c.execute("SELECT * FROM devices WHERE id=?", (did,)).fetchone()
    return Device(**dict(r)) if r else None


def get_solo_device(db: Path) -> Device | None:
    with _conn(db) as c:
        r = c.execute("SELECT * FROM devices LIMIT 1").fetchone()
    return Device(**dict(r)) if r else None


def touch_device(db: Path, did: str) -> None:
    with _conn(db) as c:
        c.execute("UPDATE devices SET last_seen_at=? WHERE id=?", (_now(), did))


def upsert_project(db: Path, name: str) -> None:
    with _conn(db) as c:
        c.execute(
            "INSERT OR IGNORE INTO projects(name, created_at) VALUES (?, ?)",
            (name, _now()),
        )


def list_projects(db: Path) -> list[str]:
    with _conn(db) as c:
        rows = c.execute("SELECT name FROM projects ORDER BY name").fetchall()
    return [r["name"] for r in rows]
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_store.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/why/store.py tests/unit/test_store.py
git commit -m "feat(store): users, devices, projects"
```

---

## Task 5: Store — installs CRUD + FTS search

**Files:**
- Modify: `src/why/store.py`
- Modify: `tests/unit/test_store.py`

- [ ] **Step 1: Extend the test file with install tests**

Append to `tests/unit/test_store.py`:

```python
from why.store import Install, InstallFilters


def _make_install(db: Path, **overrides) -> Install:
    user = store.get_solo_user(db) or store.create_user(db, display_name="t")
    device = store.get_solo_device(db) or store.create_device(db, hostname="h")
    payload = dict(
        command="brew install ripgrep",
        package_name="ripgrep",
        manager="brew",
        install_dir="/tmp",
        resolved_path=None,
        exit_code=0,
        user_id=user.id,
        device_id=device.id,
    )
    payload.update(overrides)
    return store.create_install(db, **payload)


def test_create_install_assigns_sync_id_and_timestamps(db: Path) -> None:
    inst = _make_install(db)
    assert inst.sync_id
    assert inst.installed_at
    assert inst.updated_at
    assert inst.metadata_complete == 0


def test_update_install_metadata(db: Path) -> None:
    inst = _make_install(db)
    updated = store.update_install(
        db,
        inst.id,
        display_name="ripgrep",
        what_it_does="fast grep",
        project="whydatapp",
        why="speed",
        disposition="doc",
        metadata_complete=1,
    )
    assert updated.disposition == "doc"
    assert updated.metadata_complete == 1
    assert updated.updated_at >= inst.updated_at


def test_list_installs_filters(db: Path) -> None:
    _make_install(db, command="brew install a", package_name="a")
    _make_install(db, command="npm i -g b", package_name="b", manager="npm")
    installs = store.list_installs(db, InstallFilters(manager="brew"))
    assert len(installs) == 1
    assert installs[0].package_name == "a"


def test_search_installs_uses_fts(db: Path) -> None:
    inst = _make_install(db)
    store.update_install(db, inst.id, why="needed for code search")
    results = store.search_installs(db, "code")
    assert len(results) == 1
    assert results[0].id == inst.id


def test_soft_delete_install(db: Path) -> None:
    inst = _make_install(db)
    store.soft_delete_install(db, inst.id)
    assert store.list_installs(db, InstallFilters()) == []
    assert store.list_installs(db, InstallFilters(include_deleted=True))[0].deleted == 1


def test_recent_duplicate_detection(db: Path) -> None:
    _make_install(db)
    assert store.recent_duplicate_exists(
        db, command="brew install ripgrep", install_dir="/tmp", within_seconds=60
    )
    assert not store.recent_duplicate_exists(
        db, command="brew install ripgrep", install_dir="/elsewhere", within_seconds=60
    )
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_store.py -v`
Expected: ImportError on `Install`, `InstallFilters`.

- [ ] **Step 3: Implement install functions in `store.py`**

Append to `src/why/store.py`:

```python
@dataclass(frozen=True)
class Install:
    id: int
    sync_id: str
    user_id: str
    device_id: str
    command: str
    package_name: str | None
    manager: str
    install_dir: str
    resolved_path: str | None
    installed_at: str
    exit_code: int
    display_name: str | None
    what_it_does: str | None
    project: str | None
    why: str | None
    disposition: str | None
    notes: str | None
    source_url: str | None
    metadata_complete: int
    reviewed_at: str | None
    removed_at: str | None
    updated_at: str
    deleted: int


@dataclass(frozen=True)
class InstallFilters:
    disposition: str | None = None
    project: str | None = None
    manager: str | None = None
    device_id: str | None = None
    incomplete_only: bool = False
    include_deleted: bool = False
    limit: int = 1000
    offset: int = 0
    order_by: str = "installed_at"  # column name, validated below
    order_dir: str = "desc"


_ALLOWED_ORDER = {"installed_at", "manager", "project", "disposition", "display_name", "id"}


def _row_to_install(r: sqlite3.Row) -> Install:
    return Install(**dict(r))


def create_install(
    db: Path,
    *,
    user_id: str,
    device_id: str,
    command: str,
    package_name: str | None,
    manager: str,
    install_dir: str,
    resolved_path: str | None,
    exit_code: int,
    installed_at: str | None = None,
) -> Install:
    sid = _new_id()
    now = _now()
    inst_at = installed_at or now
    with _conn(db) as c:
        cur = c.execute(
            """INSERT INTO installs(
                sync_id,user_id,device_id,command,package_name,manager,install_dir,
                resolved_path,installed_at,exit_code,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (sid, user_id, device_id, command, package_name, manager, install_dir,
             resolved_path, inst_at, exit_code, now),
        )
        new_id = cur.lastrowid
        r = c.execute("SELECT * FROM installs WHERE id=?", (new_id,)).fetchone()
    return _row_to_install(r)


_UPDATABLE = {
    "display_name", "what_it_does", "project", "why", "disposition", "notes",
    "source_url", "metadata_complete", "reviewed_at", "removed_at",
    "package_name", "resolved_path",
}


def update_install(db: Path, install_id: int, **fields) -> Install:
    bad = set(fields) - _UPDATABLE
    if bad:
        raise ValueError(f"unknown fields: {bad}")
    if not fields:
        raise ValueError("no fields to update")
    fields["updated_at"] = _now()
    sets = ",".join(f"{k}=?" for k in fields)
    params = list(fields.values()) + [install_id]
    with _conn(db) as c:
        c.execute(f"UPDATE installs SET {sets} WHERE id=?", params)
        r = c.execute("SELECT * FROM installs WHERE id=?", (install_id,)).fetchone()
    if not r:
        raise KeyError(install_id)
    return _row_to_install(r)


def get_install(db: Path, install_id: int) -> Install | None:
    with _conn(db) as c:
        r = c.execute("SELECT * FROM installs WHERE id=?", (install_id,)).fetchone()
    return _row_to_install(r) if r else None


def list_installs(db: Path, f: InstallFilters) -> list[Install]:
    if f.order_by not in _ALLOWED_ORDER:
        raise ValueError(f"bad order_by: {f.order_by}")
    direction = "DESC" if f.order_dir.lower() == "desc" else "ASC"
    where = []
    params: list[object] = []
    if not f.include_deleted:
        where.append("deleted=0")
    if f.disposition:
        where.append("disposition=?"); params.append(f.disposition)
    if f.project:
        where.append("project=?"); params.append(f.project)
    if f.manager:
        where.append("manager=?"); params.append(f.manager)
    if f.device_id:
        where.append("device_id=?"); params.append(f.device_id)
    if f.incomplete_only:
        where.append("metadata_complete=0")
    sql = "SELECT * FROM installs"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {f.order_by} {direction} LIMIT ? OFFSET ?"
    params += [f.limit, f.offset]
    with _conn(db) as c:
        rows = c.execute(sql, params).fetchall()
    return [_row_to_install(r) for r in rows]


def search_installs(db: Path, query: str, limit: int = 100) -> list[Install]:
    with _conn(db) as c:
        rows = c.execute(
            """SELECT installs.* FROM installs
               JOIN installs_fts ON installs_fts.rowid=installs.id
               WHERE installs_fts MATCH ? AND installs.deleted=0
               ORDER BY rank LIMIT ?""",
            (query, limit),
        ).fetchall()
    return [_row_to_install(r) for r in rows]


def soft_delete_install(db: Path, install_id: int) -> None:
    with _conn(db) as c:
        c.execute(
            "UPDATE installs SET deleted=1, updated_at=? WHERE id=?",
            (_now(), install_id),
        )


def recent_duplicate_exists(
    db: Path, *, command: str, install_dir: str, within_seconds: int
) -> bool:
    with _conn(db) as c:
        r = c.execute(
            """SELECT 1 FROM installs
               WHERE command=? AND install_dir=?
                 AND installed_at >= datetime('now', ?)
               LIMIT 1""",
            (command, install_dir, f"-{within_seconds} seconds"),
        ).fetchone()
    return r is not None


def stats_by_disposition(db: Path) -> dict[str, int]:
    with _conn(db) as c:
        rows = c.execute(
            """SELECT COALESCE(disposition,'(unset)') AS d, COUNT(*) AS n
               FROM installs WHERE deleted=0 GROUP BY d"""
        ).fetchall()
    return {r["d"]: r["n"] for r in rows}


def stats_by_manager(db: Path) -> dict[str, int]:
    with _conn(db) as c:
        rows = c.execute(
            "SELECT manager, COUNT(*) AS n FROM installs WHERE deleted=0 GROUP BY manager"
        ).fetchall()
    return {r["manager"]: r["n"] for r in rows}


def stats_by_project(db: Path, limit: int = 10) -> list[tuple[str, int]]:
    with _conn(db) as c:
        rows = c.execute(
            """SELECT COALESCE(project,'(unset)') AS p, COUNT(*) AS n
               FROM installs WHERE deleted=0 GROUP BY p ORDER BY n DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [(r["p"], r["n"]) for r in rows]


def installs_per_month(db: Path, months: int = 12) -> list[tuple[str, int]]:
    with _conn(db) as c:
        rows = c.execute(
            """SELECT substr(installed_at,1,7) AS m, COUNT(*) AS n
               FROM installs WHERE deleted=0
               GROUP BY m ORDER BY m DESC LIMIT ?""",
            (months,),
        ).fetchall()
    return [(r["m"], r["n"]) for r in rows]


def stale_review_queue(db: Path) -> list[Install]:
    """Skipped/incomplete + stale experimental + stale remove."""
    with _conn(db) as c:
        rows = c.execute(
            """SELECT * FROM installs WHERE deleted=0 AND (
                 metadata_complete=0
                 OR (disposition='experimental' AND installed_at < datetime('now','-30 days'))
                 OR (disposition='remove' AND removed_at IS NULL
                     AND installed_at < datetime('now','-14 days'))
               ) ORDER BY installed_at ASC"""
        ).fetchall()
    return [_row_to_install(r) for r in rows]


def list_skipped(db: Path) -> list[Install]:
    with _conn(db) as c:
        rows = c.execute(
            "SELECT * FROM installs WHERE deleted=0 AND metadata_complete=0 ORDER BY installed_at ASC"
        ).fetchall()
    return [_row_to_install(r) for r in rows]
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_store.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/why/store.py tests/unit/test_store.py
git commit -m "feat(store): installs CRUD, FTS search, stats, review queue"
```

---

## Task 6: Detection — pattern matching + extractors

**Files:**
- Create: `src/why/detect.py`
- Create: `tests/unit/test_detect.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_detect.py
from __future__ import annotations

import pytest

from why.detect import match_install, MatchResult


@pytest.mark.parametrize("cmd,manager,pkgs", [
    ("brew install ripgrep", "brew", ["ripgrep"]),
    ("brew install ripgrep fd", "brew", ["ripgrep", "fd"]),
    ("npm install -g typescript", "npm", ["typescript"]),
    ("npm i -g typescript prettier", "npm", ["typescript", "prettier"]),
    ("npm install --global eslint", "npm", ["eslint"]),
    ("pnpm add -g pnpm-bin", "pnpm", ["pnpm-bin"]),
    ("yarn global add nodemon", "yarn", ["nodemon"]),
    ("bun add -g zx", "bun", ["zx"]),
    ("pip install httpx", "pip", ["httpx"]),
    ("pip3 install requests urllib3", "pip", ["requests", "urllib3"]),
    ("pipx install black", "pipx", ["black"]),
    ("uv tool install ruff", "uv", ["ruff"]),
    ("cargo install ripgrep", "cargo", ["ripgrep"]),
    ("git clone https://github.com/foo/bar", "git", ["bar"]),
    ("git clone https://github.com/foo/bar.git baz", "git", ["baz"]),
])
def test_matches_tier1(cmd: str, manager: str, pkgs: list[str]) -> None:
    m = match_install(cmd)
    assert m is not None
    assert m.manager == manager
    assert m.packages == pkgs


@pytest.mark.parametrize("cmd", [
    "ls -la",
    "echo hello",
    "npm install",
    "pnpm install",
    "yarn",
    "pip install -r requirements.txt",
    "pip install -e .",
    "cargo build",
    "bundle install",
    "git pull",
    "brew update",
    "npm install lodash",       # local, no -g
])
def test_no_match_for_non_install_or_dependency_restore(cmd: str) -> None:
    assert match_install(cmd) is None
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/test_detect.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `detect.py`**

```python
# src/why/detect.py
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class MatchResult:
    manager: str
    packages: list[str]


_GLOBAL_NPM = re.compile(r"^(-g|--global)$")


def _strip_flags(tokens: list[str]) -> list[str]:
    return [t for t in tokens if not t.startswith("-")]


def _extract_brew(tokens: list[str]) -> list[str]:
    # tokens like ["brew", "install", "pkg", ...]
    return _strip_flags(tokens[2:])


def _extract_npm_global(tokens: list[str]) -> list[str] | None:
    # npm install -g <pkg...> or npm i -g <pkg...> or npm install --global <pkg...>
    if len(tokens) < 4:
        return None
    if tokens[1] not in ("install", "i"):
        return None
    if not any(_GLOBAL_NPM.match(t) for t in tokens[2:]):
        return None
    pkgs = _strip_flags(tokens[2:])
    return pkgs or None


def _extract_pnpm(tokens: list[str]) -> list[str] | None:
    # pnpm add -g|--global <pkg...>
    if len(tokens) < 4 or tokens[1] != "add":
        return None
    if not any(t in ("-g", "--global") for t in tokens[2:]):
        return None
    return _strip_flags(tokens[2:]) or None


def _extract_yarn(tokens: list[str]) -> list[str] | None:
    # yarn global add <pkg...>
    if len(tokens) >= 4 and tokens[1] == "global" and tokens[2] == "add":
        return _strip_flags(tokens[3:]) or None
    return None


def _extract_bun(tokens: list[str]) -> list[str] | None:
    # bun add -g|--global <pkg...>
    if len(tokens) < 4 or tokens[1] != "add":
        return None
    if not any(t in ("-g", "--global") for t in tokens[2:]):
        return None
    return _strip_flags(tokens[2:]) or None


def _extract_pip(tokens: list[str]) -> list[str] | None:
    # pip[3] install <pkg...> ; reject -r and -e
    if len(tokens) < 3 or tokens[1] != "install":
        return None
    if any(t in ("-r", "--requirement", "-e", "--editable") for t in tokens[2:]):
        return None
    pkgs = _strip_flags(tokens[2:])
    return pkgs or None


def _extract_pipx(tokens: list[str]) -> list[str] | None:
    if len(tokens) < 3 or tokens[1] != "install":
        return None
    return _strip_flags(tokens[2:]) or None


def _extract_uv_tool(tokens: list[str]) -> list[str] | None:
    if len(tokens) < 4 or tokens[1] != "tool" or tokens[2] != "install":
        return None
    return _strip_flags(tokens[3:]) or None


def _extract_cargo(tokens: list[str]) -> list[str] | None:
    if len(tokens) < 3 or tokens[1] != "install":
        return None
    return _strip_flags(tokens[2:]) or None


def _extract_git_clone(tokens: list[str]) -> list[str] | None:
    if len(tokens) < 3 or tokens[1] != "clone":
        return None
    args = _strip_flags(tokens[2:])
    if not args:
        return None
    # If a destination dir is provided, prefer it; else derive from URL.
    if len(args) >= 2:
        return [args[1]]
    url = args[0]
    name = url.rstrip("/").rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return [name] if name else None


_HEAD = {
    "brew":  ("brew",  _extract_brew),
    "npm":   ("npm",   _extract_npm_global),
    "pnpm":  ("pnpm",  _extract_pnpm),
    "yarn":  ("yarn",  _extract_yarn),
    "bun":   ("bun",   _extract_bun),
    "pip":   ("pip",   _extract_pip),
    "pip3":  ("pip",   _extract_pip),
    "pipx":  ("pipx",  _extract_pipx),
    "uv":    ("uv",    _extract_uv_tool),
    "cargo": ("cargo", _extract_cargo),
    "git":   ("git",   _extract_git_clone),
}


def match_install(command: str) -> MatchResult | None:
    """Return a MatchResult if the command is a user-intent install. Else None."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    if not tokens:
        return None
    head = tokens[0].rsplit("/", 1)[-1]  # tolerate /usr/local/bin/brew
    rule = _HEAD.get(head)
    if not rule:
        return None
    manager, extractor = rule
    # brew is special: brew install always wants packages
    if head == "brew":
        if len(tokens) < 3 or tokens[1] != "install":
            return None
        pkgs = extractor(tokens)
        if not pkgs:
            return None
        return MatchResult(manager=manager, packages=pkgs)
    pkgs = extractor(tokens)
    if not pkgs:
        return None
    return MatchResult(manager=manager, packages=pkgs)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_detect.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/why/detect.py tests/unit/test_detect.py
git commit -m "feat(detect): tier-1 pattern matching + extractors"
```

---

## Task 7: Detection — ignore rules

**Files:**
- Modify: `src/why/detect.py`
- Modify: `tests/unit/test_detect.py`

- [ ] **Step 1: Extend test file**

Append to `tests/unit/test_detect.py`:

```python
from why.detect import IgnoreContext, should_ignore


def _ctx(**kw) -> IgnoreContext:
    base = dict(
        command="brew install ripgrep",
        cwd="/tmp",
        exit_code=0,
        interactive=True,
        suppress_env=False,
        parent_process_name=None,
        recent_duplicate=False,
        user_ignore_patterns=(),
    )
    base.update(kw)
    return IgnoreContext(**base)


def test_ignore_when_exit_nonzero():
    assert should_ignore(_ctx(exit_code=1))


def test_ignore_when_non_interactive():
    assert should_ignore(_ctx(interactive=False))


def test_ignore_when_suppress_env():
    assert should_ignore(_ctx(suppress_env=True))


def test_ignore_when_parent_is_tracked_installer():
    assert should_ignore(_ctx(parent_process_name="brew"))
    assert should_ignore(_ctx(parent_process_name="cargo"))


def test_ignore_when_recent_duplicate():
    assert should_ignore(_ctx(recent_duplicate=True))


def test_ignore_when_user_pattern_matches():
    assert should_ignore(_ctx(user_ignore_patterns=(r"^brew\s+install\s+ripgrep$",)))


def test_does_not_ignore_normal_case():
    assert not should_ignore(_ctx())
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/unit/test_detect.py -v`
Expected: ImportError on `IgnoreContext`, `should_ignore`.

- [ ] **Step 3: Extend `detect.py`**

Append to `src/why/detect.py`:

```python
IGNORED_PARENTS = frozenset({
    "brew", "pip", "pip3", "npm", "pnpm", "yarn", "bun", "cargo", "make",
    "docker", "nix", "asdf", "mise", "volta", "nvm", "why",
})


@dataclass(frozen=True)
class IgnoreContext:
    command: str
    cwd: str
    exit_code: int
    interactive: bool
    suppress_env: bool
    parent_process_name: str | None
    recent_duplicate: bool
    user_ignore_patterns: tuple[str, ...]


def should_ignore(ctx: IgnoreContext) -> bool:
    if ctx.exit_code != 0:
        return True
    if not ctx.interactive:
        return True
    if ctx.suppress_env:
        return True
    if ctx.parent_process_name and ctx.parent_process_name in IGNORED_PARENTS:
        return True
    if ctx.recent_duplicate:
        return True
    for p in ctx.user_ignore_patterns:
        if re.search(p, ctx.command):
            return True
    return False
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_detect.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/why/detect.py tests/unit/test_detect.py
git commit -m "feat(detect): ignore rules"
```

---

## Task 8: Resolve — best-effort install path

**Files:**
- Create: `src/why/resolve.py`
- Create: `tests/unit/test_resolve.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_resolve.py
from __future__ import annotations

from why.resolve import resolve_path


def test_resolve_returns_none_for_unknown_manager(monkeypatch):
    assert resolve_path(manager="custom", package="x", cwd="/tmp") is None


def test_resolve_brew_uses_prefix(monkeypatch):
    calls = {}

    def fake_run(args, **kw):
        calls["args"] = args
        class R:
            stdout = "/opt/homebrew/Cellar/ripgrep/14.1.0\n"
            returncode = 0
        return R()

    monkeypatch.setattr("why.resolve.subprocess.run", fake_run)
    p = resolve_path(manager="brew", package="ripgrep", cwd="/tmp")
    assert p == "/opt/homebrew/Cellar/ripgrep/14.1.0"
    assert calls["args"][:3] == ["brew", "--prefix", "ripgrep"]


def test_resolve_brew_returns_none_on_failure(monkeypatch):
    def fake_run(args, **kw):
        class R:
            stdout = ""
            returncode = 1
        return R()
    monkeypatch.setattr("why.resolve.subprocess.run", fake_run)
    assert resolve_path(manager="brew", package="ripgrep", cwd="/tmp") is None


def test_resolve_git_uses_cwd_plus_name(tmp_path):
    target = tmp_path / "myrepo"
    target.mkdir()
    p = resolve_path(manager="git", package="myrepo", cwd=str(tmp_path))
    assert p == str(target)


def test_resolve_cargo_default_path(monkeypatch, tmp_path):
    monkeypatch.setenv("CARGO_HOME", str(tmp_path))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "ripgrep").touch()
    p = resolve_path(manager="cargo", package="ripgrep", cwd="/tmp")
    assert p == str(bin_dir / "ripgrep")
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/test_resolve.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `resolve.py`**

```python
# src/why/resolve.py
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _run(args: list[str], timeout: float = 2.0) -> str | None:
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip() or None


def _resolve_brew(pkg: str) -> str | None:
    return _run(["brew", "--prefix", pkg])


def _resolve_cargo(pkg: str) -> str | None:
    home = os.environ.get("CARGO_HOME") or str(Path.home() / ".cargo")
    candidate = Path(home) / "bin" / pkg
    return str(candidate) if candidate.exists() else None


def _resolve_pipx(pkg: str) -> str | None:
    home = Path.home() / ".local/share/pipx/venvs" / pkg
    return str(home) if home.exists() else None


def _resolve_uv_tool(pkg: str) -> str | None:
    base = Path.home() / ".local/share/uv/tools" / pkg
    return str(base) if base.exists() else None


def _resolve_npm_global(pkg: str) -> str | None:
    root = _run(["npm", "root", "-g"])
    if not root:
        return None
    candidate = Path(root) / pkg
    return str(candidate) if candidate.exists() else None


def _resolve_git(pkg: str, cwd: str) -> str | None:
    candidate = Path(cwd) / pkg
    return str(candidate) if candidate.exists() else None


def resolve_path(*, manager: str, package: str, cwd: str) -> str | None:
    """Best-effort resolution of where the install landed. Never raises."""
    try:
        match manager:
            case "brew":  return _resolve_brew(package)
            case "cargo": return _resolve_cargo(package)
            case "pipx":  return _resolve_pipx(package)
            case "uv":    return _resolve_uv_tool(package)
            case "npm" | "pnpm" | "yarn" | "bun":
                return _resolve_npm_global(package)
            case "git":   return _resolve_git(package, cwd)
            case _:       return None
    except Exception:
        return None
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_resolve.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/why/resolve.py tests/unit/test_resolve.py
git commit -m "feat(resolve): best-effort path resolution per manager"
```

---

## Task 9: Config & presentation loaders

**Files:**
- Create: `src/why/config.py`
- Create: `src/why/presentation.toml`
- Create: `tests/unit/test_config.py`

- [ ] **Step 1: Write `presentation.toml` (default, ships with package)**

```toml
# src/why/presentation.toml
[brew]
icon = "🍺"
color = "#f59e0b"
label = "Homebrew"

[npm]
icon = "📦"
color = "#dc2626"
label = "npm"

[pnpm]
icon = "📦"
color = "#ea580c"
label = "pnpm"

[yarn]
icon = "🧶"
color = "#2563eb"
label = "Yarn"

[bun]
icon = "🍞"
color = "#fbbf24"
label = "Bun"

[pip]
icon = "🐍"
color = "#3b82f6"
label = "pip"

[pipx]
icon = "🐍"
color = "#1d4ed8"
label = "pipx"

[uv]
icon = "🟪"
color = "#7c3aed"
label = "uv tool"

[cargo]
icon = "📦"
color = "#a16207"
label = "Cargo"

[git]
icon = "🌿"
color = "#6b7280"
label = "git clone"

[disposition.doc]
color = "#2563eb"
label = "Doc"

[disposition.setup]
color = "#16a34a"
label = "Setup"

[disposition.experimental]
color = "#d97706"
label = "Experimental"

[disposition.remove]
color = "#dc2626"
label = "Remove"

[disposition.ignore]
color = "#6b7280"
label = "Ignore"
```

- [ ] **Step 2: Write the failing test**

```python
# tests/unit/test_config.py
from __future__ import annotations

from pathlib import Path

from why.config import (
    DEFAULT_CONFIG,
    load_config,
    write_config,
    load_presentation,
    load_user_ignore_patterns,
    load_custom_patterns,
)


def test_load_config_returns_defaults_when_missing(why_home: Path) -> None:
    cfg = load_config()
    assert cfg["managers"]["brew"] is True
    assert cfg["web"]["port"] == 7873


def test_round_trip_config(why_home: Path) -> None:
    cfg = DEFAULT_CONFIG.copy()
    cfg["device"] = {"id": "abc", "label": "x"}
    write_config(cfg)
    loaded = load_config()
    assert loaded["device"]["label"] == "x"


def test_presentation_includes_brew(why_home: Path) -> None:
    p = load_presentation()
    assert p["brew"]["icon"]
    assert p["brew"]["color"].startswith("#")


def test_presentation_user_override(why_home: Path) -> None:
    (why_home / "presentation.toml").write_text(
        '[brew]\nicon = "X"\ncolor = "#000000"\nlabel = "Brew"\n'
    )
    p = load_presentation()
    assert p["brew"]["icon"] == "X"
    # Other managers still come from default
    assert p["npm"]["label"] == "npm"


def test_user_ignore_patterns_empty_when_missing(why_home: Path) -> None:
    assert load_user_ignore_patterns() == ()


def test_user_ignore_patterns_loads(why_home: Path) -> None:
    (why_home / "ignore.toml").write_text('patterns = ["^foo", "^bar"]\n')
    assert load_user_ignore_patterns() == ("^foo", "^bar")


def test_custom_patterns_empty_when_missing(why_home: Path) -> None:
    assert load_custom_patterns() == []
```

- [ ] **Step 3: Run test to verify failure**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `config.py`**

```python
# src/why/config.py
from __future__ import annotations

import tomllib
from importlib import resources
from typing import Any

import tomli_w

from why.paths import config_path, ensure_home, why_home


DEFAULT_CONFIG: dict[str, Any] = {
    "device": {"id": "", "label": ""},
    "user":   {"id": "", "display_name": "", "email": ""},
    "managers": {
        "brew": True, "npm": True, "pnpm": True, "yarn": True, "bun": True,
        "pip": True, "pipx": True, "uv": True, "cargo": True, "git": True,
        "gem": False, "go": False, "apt": False, "mas": False,
        "vscode": False, "docker": False,
    },
    "web": {"host": "127.0.0.1", "port": 7873, "autostart": False},
    "ui": {},
    "sync": {"enabled": False},
}


def load_config() -> dict[str, Any]:
    p = config_path("config")
    if not p.exists():
        return _deep_copy(DEFAULT_CONFIG)
    with p.open("rb") as f:
        cfg = tomllib.load(f)
    return _merge(_deep_copy(DEFAULT_CONFIG), cfg)


def write_config(cfg: dict[str, Any]) -> None:
    ensure_home()
    p = config_path("config")
    with p.open("wb") as f:
        tomli_w.dump(cfg, f)


def _default_presentation() -> dict[str, Any]:
    text = resources.files("why").joinpath("presentation.toml").read_text()
    return tomllib.loads(text)


def load_presentation() -> dict[str, Any]:
    base = _default_presentation()
    user = config_path("presentation")
    if user.exists():
        with user.open("rb") as f:
            override = tomllib.load(f)
        return _merge(base, override)
    return base


def load_user_ignore_patterns() -> tuple[str, ...]:
    p = why_home() / "ignore.toml"
    if not p.exists():
        return ()
    with p.open("rb") as f:
        data = tomllib.load(f)
    return tuple(data.get("patterns", ()))


def load_custom_patterns() -> list[dict[str, Any]]:
    p = why_home() / "patterns.toml"
    if not p.exists():
        return []
    with p.open("rb") as f:
        data = tomllib.load(f)
    return list(data.get("pattern", []))


def _deep_copy(d: dict[str, Any]) -> dict[str, Any]:
    return {k: (_deep_copy(v) if isinstance(v, dict) else v) for k, v in d.items()}


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = _deep_copy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/why/config.py src/why/presentation.toml tests/unit/test_config.py
git commit -m "feat(config): config + presentation loaders with user overrides"
```

---

## Task 10: Prompts module

**Files:**
- Create: `src/why/prompts.py`
- Create: `tests/unit/test_prompts.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_prompts.py
from __future__ import annotations

import io

from why.prompts import (
    DispositionChoice,
    parse_disposition_input,
    PromptResult,
    run_metadata_prompt,
)


def test_parse_disposition_input_numeric():
    assert parse_disposition_input("1") == DispositionChoice.DOC
    assert parse_disposition_input("2") == DispositionChoice.SETUP
    assert parse_disposition_input("3") == DispositionChoice.EXPERIMENTAL
    assert parse_disposition_input("4") == DispositionChoice.REMOVE
    assert parse_disposition_input("5") == DispositionChoice.IGNORE


def test_parse_disposition_input_skip_and_quit():
    assert parse_disposition_input("s") == DispositionChoice.SKIP
    assert parse_disposition_input("q") == DispositionChoice.QUIT


def test_parse_disposition_input_invalid():
    assert parse_disposition_input("x") is None
    assert parse_disposition_input("") is None


def test_run_metadata_prompt_skip_path():
    inp = io.StringIO("s\n")
    out = io.StringIO()
    res = run_metadata_prompt(
        default_name="ripgrep",
        default_project="whydatapp",
        command="brew install ripgrep",
        cwd="/tmp",
        input=inp,
        output=out,
    )
    assert res.disposition == "skip"
    assert res.metadata_complete is False


def test_run_metadata_prompt_full_path():
    answers = "\n".join([
        "1",                # disposition: doc
        "ripgrep",          # display name (default accepted)
        "fast grep",        # what
        "whydatapp",        # project (default accepted)
        "needed for code search",
        "",                 # notes
    ]) + "\n"
    res = run_metadata_prompt(
        default_name="ripgrep",
        default_project="whydatapp",
        command="brew install ripgrep",
        cwd="/tmp",
        input=io.StringIO(answers),
        output=io.StringIO(),
    )
    assert res.disposition == "doc"
    assert res.display_name == "ripgrep"
    assert res.what_it_does == "fast grep"
    assert res.project == "whydatapp"
    assert res.why == "needed for code search"
    assert res.notes is None
    assert res.metadata_complete is True


def test_run_metadata_prompt_quit_marks_ignore():
    res = run_metadata_prompt(
        default_name="x", default_project=None,
        command="brew install x", cwd="/tmp",
        input=io.StringIO("q\n"),
        output=io.StringIO(),
    )
    assert res.disposition == "ignore"
    assert res.metadata_complete is True
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/test_prompts.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `prompts.py`**

```python
# src/why/prompts.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import IO


class DispositionChoice(Enum):
    DOC = "doc"
    SETUP = "setup"
    EXPERIMENTAL = "experimental"
    REMOVE = "remove"
    IGNORE = "ignore"
    SKIP = "skip"
    QUIT = "quit"


_NUMERIC = {
    "1": DispositionChoice.DOC,
    "2": DispositionChoice.SETUP,
    "3": DispositionChoice.EXPERIMENTAL,
    "4": DispositionChoice.REMOVE,
    "5": DispositionChoice.IGNORE,
    "s": DispositionChoice.SKIP,
    "q": DispositionChoice.QUIT,
}


def parse_disposition_input(s: str) -> DispositionChoice | None:
    return _NUMERIC.get(s.strip().lower())


@dataclass(frozen=True)
class PromptResult:
    disposition: str          # one of: doc|setup|experimental|remove|ignore|skip
    display_name: str | None
    what_it_does: str | None
    project: str | None
    why: str | None
    notes: str | None
    metadata_complete: bool


def _ask(prompt: str, *, input: IO[str], output: IO[str], default: str | None = None) -> str:
    if default:
        output.write(f"  {prompt} [{default}]: ")
    else:
        output.write(f"  {prompt}: ")
    output.flush()
    line = input.readline()
    if not line:
        return ""
    val = line.rstrip("\n")
    return val if val else (default or "")


def run_metadata_prompt(
    *,
    default_name: str | None,
    default_project: str | None,
    command: str,
    cwd: str,
    input: IO[str],
    output: IO[str],
) -> PromptResult:
    output.write(f"\n📝 why? — captured: {command}  ({cwd})\n\n")
    output.write("  Disposition? [1] Doc  [2] Setup  [3] Experimental  "
                 "[4] Remove later  [5] Ignore\n")
    output.write("  [s] Skip for now    [q] Quit (treat as ignore)\n")
    output.flush()

    while True:
        output.write("> ")
        output.flush()
        line = input.readline()
        if not line:
            return PromptResult("skip", None, None, None, None, None, False)
        choice = parse_disposition_input(line)
        if choice is not None:
            break
        output.write("  invalid choice; try again.\n")

    if choice == DispositionChoice.SKIP:
        return PromptResult("skip", None, None, None, None, None, False)
    if choice == DispositionChoice.QUIT:
        return PromptResult("ignore", None, None, None, None, None, True)

    name = _ask("Display name", default=default_name or "", input=input, output=output) or None
    what = _ask("What does it do?", default=None, input=input, output=output) or None
    project = _ask("Project", default=default_project or "", input=input, output=output) or None
    why = _ask("Why install?", default=None, input=input, output=output) or None
    notes = _ask("Notes (optional, ↵ to skip)", default=None, input=input, output=output) or None

    return PromptResult(
        disposition=choice.value,
        display_name=name,
        what_it_does=what,
        project=project,
        why=why,
        notes=notes,
        metadata_complete=True,
    )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_prompts.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/why/prompts.py tests/unit/test_prompts.py
git commit -m "feat(prompts): metadata prompt with skip/quit semantics"
```

---

## Task 11: Project inference helper

**Files:**
- Create: `src/why/project_infer.py`
- Create: `tests/unit/test_project_infer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_project_infer.py
from pathlib import Path

from why.project_infer import infer_project


def test_infer_uses_git_dir(tmp_path: Path):
    repo = tmp_path / "myrepo"
    (repo / ".git").mkdir(parents=True)
    (repo / "src").mkdir()
    assert infer_project(str(repo / "src")) == "myrepo"


def test_infer_uses_pyproject(tmp_path: Path):
    proj = tmp_path / "py-thing"
    proj.mkdir()
    (proj / "pyproject.toml").touch()
    assert infer_project(str(proj)) == "py-thing"


def test_infer_uses_package_json(tmp_path: Path):
    proj = tmp_path / "node-thing"
    proj.mkdir()
    (proj / "package.json").touch()
    assert infer_project(str(proj)) == "node-thing"


def test_infer_returns_none_outside_project(tmp_path: Path):
    assert infer_project(str(tmp_path)) is None
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/unit/test_project_infer.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `project_infer.py`**

```python
# src/why/project_infer.py
from __future__ import annotations

from pathlib import Path

_MARKERS = (".git", "pyproject.toml", "package.json", "Cargo.toml", "go.mod")


def infer_project(cwd: str) -> str | None:
    p = Path(cwd).resolve()
    for ancestor in [p, *p.parents]:
        for m in _MARKERS:
            if (ancestor / m).exists():
                return ancestor.name
    return None
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_project_infer.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/why/project_infer.py tests/unit/test_project_infer.py
git commit -m "feat: infer project name from cwd ancestors"
```

---

## Task 12: CLI scaffolding + bootstrap helper

**Files:**
- Create: `src/why/cli.py`
- Create: `src/why/bootstrap.py`
- Create: `tests/integration/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_cli.py
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from why.cli import app

runner = CliRunner()


def test_version_command(why_home: Path) -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "why" in result.stdout


def test_list_command_on_empty_db(why_home: Path) -> None:
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No installs" in result.stdout
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest tests/integration/test_cli.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `bootstrap.py`**

```python
# src/why/bootstrap.py
"""Idempotent first-run bootstrap. Used by every CLI subcommand except `init`."""
from __future__ import annotations

import socket
from pathlib import Path

from why import store
from why.config import load_config, write_config
from why.paths import db_path, ensure_home, why_home
from why.schema import migrate


def ensure_ready() -> Path:
    home = ensure_home()
    db = db_path()
    migrate(db, backups_dir=home / "backups")
    cfg = load_config()
    user = store.get_solo_user(db)
    if user is None:
        u = store.create_user(db, display_name=cfg["user"].get("display_name") or "user")
        cfg["user"]["id"] = u.id
    device = store.get_solo_device(db)
    if device is None:
        hostname = socket.gethostname()
        d = store.create_device(db, hostname=hostname, label=cfg["device"].get("label") or hostname)
        cfg["device"]["id"] = d.id
    write_config(cfg)
    return db
```

- [ ] **Step 4: Implement `cli.py` (skeleton + `list` only)**

```python
# src/why/cli.py
from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from why import __version__, store
from why.bootstrap import ensure_ready
from why.store import InstallFilters

app = typer.Typer(add_completion=False, help="Track why you installed every tool.")
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"why {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True),
) -> None:
    """why?"""


@app.command("list")
def list_cmd(
    disposition: str | None = typer.Option(None),
    project: str | None = typer.Option(None),
    manager: str | None = typer.Option(None),
    incomplete_only: bool = typer.Option(False, "--incomplete"),
    limit: int = typer.Option(50),
) -> None:
    """List installs as a table."""
    db = ensure_ready()
    rows = store.list_installs(
        db,
        InstallFilters(
            disposition=disposition,
            project=project,
            manager=manager,
            incomplete_only=incomplete_only,
            limit=limit,
        ),
    )
    if not rows:
        console.print("No installs.")
        return
    t = Table()
    for col in ("id", "name", "manager", "project", "disposition", "installed_at"):
        t.add_column(col)
    for r in rows:
        t.add_row(
            str(r.id),
            r.display_name or r.package_name or "",
            r.manager,
            r.project or "",
            r.disposition or "—",
            r.installed_at,
        )
    console.print(t)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/integration/test_cli.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/why/cli.py src/why/bootstrap.py tests/integration/test_cli.py
git commit -m "feat(cli): app skeleton + list subcommand + bootstrap"
```

---

## Task 13: CLI — `log` subcommand (interactive capture)

**Files:**
- Modify: `src/why/cli.py`
- Modify: `tests/integration/test_cli.py`

- [ ] **Step 1: Extend test file**

Append to `tests/integration/test_cli.py`:

```python
def test_log_records_install_with_interactive_input(why_home: Path) -> None:
    answers = "\n".join(["1", "ripgrep", "fast grep", "whydatapp", "speed", ""]) + "\n"
    result = runner.invoke(
        app, ["log", "--", "brew", "install", "ripgrep"], input=answers
    )
    assert result.exit_code == 0
    # Now list shows it
    listed = runner.invoke(app, ["list"])
    assert "ripgrep" in listed.stdout
    assert "doc" in listed.stdout


def test_log_skip_creates_incomplete_entry(why_home: Path) -> None:
    result = runner.invoke(app, ["log", "--", "brew", "install", "fd"], input="s\n")
    assert result.exit_code == 0
    listed = runner.invoke(app, ["list", "--incomplete"])
    assert "fd" in listed.stdout


def test_log_rejects_non_install_command(why_home: Path) -> None:
    result = runner.invoke(app, ["log", "--", "ls", "-la"])
    assert result.exit_code != 0
    assert "not recognized" in result.stdout.lower()
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/integration/test_cli.py -v`
Expected: failures (no `log` command yet).

- [ ] **Step 3: Implement the `log` subcommand**

Append to `src/why/cli.py`:

```python
import os
import sys

from why.detect import match_install
from why.project_infer import infer_project
from why.prompts import run_metadata_prompt
from why.resolve import resolve_path


@app.command("log")
def log_cmd(
    cmd: list[str] = typer.Argument(..., help="The install command, after `--`."),
    cwd: str = typer.Option(None, help="Override cwd; defaults to current directory."),
) -> None:
    """Log an install interactively. Used by the shell hook and for manual entries."""
    db = ensure_ready()
    command_str = " ".join(cmd)
    work_dir = cwd or os.getcwd()

    match = match_install(command_str)
    if match is None:
        console.print(
            f"[yellow]not recognized as an install: {command_str}[/yellow]"
        )
        raise typer.Exit(code=2)

    if store.recent_duplicate_exists(
        db, command=command_str, install_dir=work_dir, within_seconds=60
    ):
        console.print("[dim]recent duplicate; skipping.[/dim]")
        raise typer.Exit(code=0)

    user = store.get_solo_user(db)
    device = store.get_solo_device(db)
    assert user is not None and device is not None  # ensured by bootstrap

    primary_pkg = match.packages[0]
    resolved = resolve_path(manager=match.manager, package=primary_pkg, cwd=work_dir)

    inst = store.create_install(
        db,
        user_id=user.id,
        device_id=device.id,
        command=command_str,
        package_name=primary_pkg,
        manager=match.manager,
        install_dir=work_dir,
        resolved_path=resolved,
        exit_code=0,
    )

    inferred_project = infer_project(work_dir)
    result = run_metadata_prompt(
        default_name=primary_pkg,
        default_project=inferred_project,
        command=command_str,
        cwd=work_dir,
        input=sys.stdin,
        output=sys.stdout,
    )

    if result.disposition == "skip":
        console.print(
            f"  [dim]skipped — review later via `why review` (id={inst.id})[/dim]"
        )
        return

    if result.project:
        store.upsert_project(db, result.project)

    store.update_install(
        db,
        inst.id,
        display_name=result.display_name,
        what_it_does=result.what_it_does,
        project=result.project,
        why=result.why,
        notes=result.notes,
        disposition=result.disposition,
        metadata_complete=1 if result.metadata_complete else 0,
    )
    console.print(f"  [green]✓[/green] logged (id={inst.id}).")
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/integration/test_cli.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/why/cli.py tests/integration/test_cli.py
git commit -m "feat(cli): log subcommand for interactive capture"
```

---

## Task 14: CLI — `review`, `export`, `delete`

**Files:**
- Modify: `src/why/cli.py`
- Modify: `tests/integration/test_cli.py`

- [ ] **Step 1: Extend test file**

Append to `tests/integration/test_cli.py`:

```python
def test_review_drains_skipped(why_home: Path) -> None:
    runner.invoke(app, ["log", "--", "brew", "install", "ripgrep"], input="s\n")
    answers = "\n".join(["1", "ripgrep", "grep", "p", "speed", ""]) + "\n"
    result = runner.invoke(app, ["review"], input=answers)
    assert result.exit_code == 0
    listed = runner.invoke(app, ["list", "--incomplete"])
    assert "ripgrep" not in listed.stdout


def test_export_json(why_home: Path, tmp_path: Path) -> None:
    answers = "\n".join(["1", "ripgrep", "grep", "p", "speed", ""]) + "\n"
    runner.invoke(app, ["log", "--", "brew", "install", "ripgrep"], input=answers)
    out = tmp_path / "out.json"
    result = runner.invoke(app, ["export", "--format", "json", "--out", str(out)])
    assert result.exit_code == 0
    text = out.read_text()
    assert "ripgrep" in text
    assert "\"disposition\": \"doc\"" in text


def test_delete_soft(why_home: Path) -> None:
    answers = "\n".join(["1", "rg", "g", "p", "w", ""]) + "\n"
    runner.invoke(app, ["log", "--", "brew", "install", "ripgrep"], input=answers)
    listed = runner.invoke(app, ["list"])
    # find id 1
    result = runner.invoke(app, ["delete", "1", "--yes"])
    assert result.exit_code == 0
    listed_after = runner.invoke(app, ["list"])
    assert "ripgrep" not in listed_after.stdout
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/integration/test_cli.py -v`
Expected: failures.

- [ ] **Step 3: Implement the new subcommands**

Append to `src/why/cli.py`:

```python
import json
from pathlib import Path as _P


@app.command("review")
def review_cmd() -> None:
    """Drain the skipped/incomplete queue, one entry at a time."""
    db = ensure_ready()
    pending = store.list_skipped(db)
    if not pending:
        console.print("Review queue is empty.")
        return
    for inst in pending:
        result = run_metadata_prompt(
            default_name=inst.display_name or inst.package_name,
            default_project=inst.project,
            command=inst.command,
            cwd=inst.install_dir,
            input=sys.stdin,
            output=sys.stdout,
        )
        if result.disposition == "skip":
            console.print(f"  [dim]still skipped (id={inst.id})[/dim]")
            continue
        if result.project:
            store.upsert_project(db, result.project)
        store.update_install(
            db, inst.id,
            display_name=result.display_name,
            what_it_does=result.what_it_does,
            project=result.project,
            why=result.why,
            notes=result.notes,
            disposition=result.disposition,
            metadata_complete=1 if result.metadata_complete else 0,
        )
        console.print(f"  [green]✓[/green] reviewed (id={inst.id}).")


def _to_md(inst: store.Install) -> str:
    name = inst.display_name or inst.package_name or "(unnamed)"
    parts = [f"**{name}** — `{inst.command}`"]
    if inst.what_it_does:
        parts.append(inst.what_it_does)
    parts.append(
        f"Installed {inst.installed_at} in `{inst.install_dir}`"
    )
    if inst.why:
        parts.append(f"Why: {inst.why}")
    return "\n".join(parts) + "\n"


@app.command("export")
def export_cmd(
    fmt: str = typer.Option("md", "--format"),
    out: _P = typer.Option(..., "--out"),
    disposition: str | None = typer.Option(None),
    project: str | None = typer.Option(None),
) -> None:
    """Export installs to a file (md|json)."""
    db = ensure_ready()
    rows = store.list_installs(
        db,
        InstallFilters(disposition=disposition, project=project, limit=10_000),
    )
    if fmt == "md":
        out.write_text("\n".join(_to_md(r) for r in rows))
    elif fmt == "json":
        out.write_text(json.dumps([r.__dict__ for r in rows], indent=2, default=str))
    else:
        console.print("[red]format must be md or json[/red]")
        raise typer.Exit(code=2)
    console.print(f"wrote {len(rows)} entries → {out}")


@app.command("delete")
def delete_cmd(
    install_id: int,
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation."),
) -> None:
    """Soft-delete an install by id."""
    db = ensure_ready()
    inst = store.get_install(db, install_id)
    if not inst:
        console.print(f"[red]no install with id={install_id}[/red]")
        raise typer.Exit(code=1)
    if not yes:
        ok = typer.confirm(f"Delete '{inst.display_name or inst.package_name}'?")
        if not ok:
            raise typer.Exit(code=0)
    store.soft_delete_install(db, install_id)
    console.print(f"[green]✓[/green] deleted (soft) id={install_id}.")
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/integration/test_cli.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/why/cli.py tests/integration/test_cli.py
git commit -m "feat(cli): review, export, delete subcommands"
```

---

## Task 15: CLI — `_hook` entrypoint

**Files:**
- Create: `src/why/hook_runner.py`
- Modify: `src/why/cli.py`
- Modify: `tests/integration/test_cli.py`

- [ ] **Step 1: Extend test file**

Append to `tests/integration/test_cli.py`:

```python
def test_hook_no_match_silent(why_home: Path) -> None:
    result = runner.invoke(app, ["_hook", "--cmd", "ls -la", "--cwd", "/tmp", "--code", "0"])
    assert result.exit_code == 0
    assert result.stdout == ""


def test_hook_nonzero_exit_silent(why_home: Path) -> None:
    result = runner.invoke(
        app, ["_hook", "--cmd", "brew install x", "--cwd", "/tmp", "--code", "1"]
    )
    assert result.exit_code == 0
    assert result.stdout == ""


def test_hook_matched_runs_prompt(why_home: Path) -> None:
    answers = "\n".join(["1", "rg", "g", "p", "w", ""]) + "\n"
    result = runner.invoke(
        app,
        ["_hook", "--cmd", "brew install ripgrep", "--cwd", "/tmp", "--code", "0"],
        input=answers,
    )
    assert result.exit_code == 0
    listed = runner.invoke(app, ["list"])
    assert "ripgrep" in listed.stdout
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/integration/test_cli.py -v`
Expected: failures (no `_hook` yet).

- [ ] **Step 3: Implement `hook_runner.py`**

```python
# src/why/hook_runner.py
from __future__ import annotations

import os
import sys
from pathlib import Path

from why import store
from why.bootstrap import ensure_ready
from why.config import load_user_ignore_patterns
from why.detect import IgnoreContext, match_install, should_ignore
from why.paths import log_path


def _parent_process_name() -> str | None:
    ppid = os.getppid()
    try:
        # macOS / Linux: read /proc or use ps
        import subprocess
        r = subprocess.run(
            ["ps", "-o", "comm=", "-p", str(ppid)],
            capture_output=True, text=True, timeout=1.0,
        )
        if r.returncode != 0:
            return None
        name = r.stdout.strip().rsplit("/", 1)[-1]
        return name or None
    except Exception:
        return None


def _log_error(msg: str) -> None:
    try:
        with log_path("hook").open("a") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def run_hook(*, command: str, cwd: str, exit_code: int) -> int:
    """Returns 0 always. Triggers `why log` flow only when warranted."""
    try:
        if not command.strip():
            return 0
        match = match_install(command)
        if match is None:
            return 0

        db = ensure_ready()
        ctx = IgnoreContext(
            command=command,
            cwd=cwd,
            exit_code=exit_code,
            interactive=sys.stdin.isatty(),
            suppress_env=os.environ.get("WHY_SUPPRESS") == "1",
            parent_process_name=_parent_process_name(),
            recent_duplicate=store.recent_duplicate_exists(
                db, command=command, install_dir=cwd, within_seconds=60
            ),
            user_ignore_patterns=load_user_ignore_patterns(),
        )
        if should_ignore(ctx):
            return 0

        # Delegate to the same code path as `why log`
        from why.cli import log_cmd
        # Typer's command is itself a callable; invoke with the parsed args.
        log_cmd(cmd=command.split(), cwd=cwd)
        return 0
    except SystemExit:
        raise
    except Exception as e:  # paranoid hook
        _log_error(f"hook error: {e!r} cmd={command!r}")
        return 0
```

- [ ] **Step 4: Wire `_hook` subcommand into CLI**

Append to `src/why/cli.py`:

```python
@app.command("_hook", hidden=True)
def hook_cmd(
    cmd: str = typer.Option(...),
    cwd: str = typer.Option(...),
    code: int = typer.Option(...),
) -> None:
    """Internal: invoked by the shell hook. Always exits 0."""
    from why.hook_runner import run_hook
    rc = run_hook(command=cmd, cwd=cwd, exit_code=code)
    raise typer.Exit(code=rc)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/integration/test_cli.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/why/hook_runner.py src/why/cli.py tests/integration/test_cli.py
git commit -m "feat(cli): _hook entrypoint with paranoid error handling"
```

---

## Task 16: Final lint, type-check, full test pass

- [ ] **Step 1: Run ruff**

Run: `uv run ruff check src tests`
Expected: no errors. Fix any reported issues inline.

- [ ] **Step 2: Run mypy**

Run: `uv run mypy src/why`
Expected: success. Fix any reported issues inline.

- [ ] **Step 3: Run full test suite with coverage**

Run: `uv run pytest --cov=why --cov-report=term-missing`
Expected: all tests pass; coverage on `detect.py`, `store.py`, `prompts.py` at ≥90%.

- [ ] **Step 4: Commit any fixups**

```bash
git add -A
git commit -m "chore: lint + type-check fixups"
```

---

## Plan 1 — Self-Review

- ✅ Spec §3 storage layer → Tasks 3, 4, 5.
- ✅ Spec §3 detection layer → Tasks 6, 7.
- ✅ Spec §4 patterns/ignore/resolution → Tasks 6, 7, 8.
- ✅ Spec §5 schema (incl. sync seams) → Task 3.
- ✅ Spec §6 config + presentation files → Task 9.
- ✅ Spec §8 Flow A capture (CLI side) → Tasks 10, 13.
- ✅ Spec §8 Flow B `why review` → Task 14.
- ✅ Spec §11 forward-compat seams populated by bootstrap → Task 12.
- ✅ Spec §13 paranoid hook errors → Task 15.
- 🔁 Spec §7 `why init` wizard → deferred to Plan 3.
- 🔁 Spec §9 web UI → Plan 2.
- 🔁 Spec §4 hook shell scripts → Plan 3.

No placeholders. Type names consistent across tasks (`Install`, `InstallFilters`, `MatchResult`, `IgnoreContext`, `PromptResult`, `DispositionChoice`).
