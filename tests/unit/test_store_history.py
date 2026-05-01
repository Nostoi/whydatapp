from __future__ import annotations

from pathlib import Path

from why import store
from why.bootstrap import ensure_ready


def _make_install(db: Path, command: str = "brew install ripgrep") -> store.Install:
    user = store.get_solo_user(db)
    device = store.get_solo_device(db)
    return store.create_install(
        db, user_id=user.id, device_id=device.id,
        command=command, package_name=None, manager="brew",
        install_dir="/tmp", resolved_path=None, exit_code=0,
    )


def test_save_and_get_command_history(why_home: Path) -> None:
    db = ensure_ready()
    inst = _make_install(db)
    cmds = ["ls", "cd /tmp", "brew search ripgrep"]
    store.save_command_history(db, inst.id, cmds)
    assert store.get_command_history(db, inst.id) == cmds


def test_get_command_history_empty(why_home: Path) -> None:
    db = ensure_ready()
    inst = _make_install(db, "brew install fd")
    assert store.get_command_history(db, inst.id) == []


def test_save_command_history_noop_on_empty(why_home: Path) -> None:
    db = ensure_ready()
    inst = _make_install(db, "brew install bat")
    store.save_command_history(db, inst.id, [])
    assert store.get_command_history(db, inst.id) == []


def test_save_command_history_trims_to_limit(why_home: Path) -> None:
    db = ensure_ready()
    inst = _make_install(db, "brew install fzf")
    cmds = [f"cmd{i}" for i in range(20)]  # 20 commands, limit is 10
    store.save_command_history(db, inst.id, cmds)
    result = store.get_command_history(db, inst.id)
    assert len(result) == 10
    assert result == cmds[10:]  # last 10 (most recent)


def test_save_command_history_preserves_order(why_home: Path) -> None:
    db = ensure_ready()
    inst = _make_install(db, "brew install eza")
    cmds = ["a", "b", "c", "d", "e"]
    store.save_command_history(db, inst.id, cmds)
    assert store.get_command_history(db, inst.id) == cmds


def test_command_history_survives_soft_delete(why_home: Path) -> None:
    """History rows persist through a soft delete (the install row isn't physically removed)."""
    db = ensure_ready()
    inst = _make_install(db, "brew install jq")
    store.save_command_history(db, inst.id, ["a", "b"])
    store.soft_delete_install(db, inst.id)
    # History is still retrievable — soft delete doesn't remove rows
    assert store.get_command_history(db, inst.id) == ["a", "b"]

