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
