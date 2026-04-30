from pathlib import Path

from why import store
from why.bootstrap import ensure_ready
from why.markdown import to_markdown


def test_markdown_includes_command_and_why(why_home: Path) -> None:
    db = ensure_ready()
    user = store.get_solo_user(db); device = store.get_solo_device(db)
    inst = store.create_install(
        db, user_id=user.id, device_id=device.id,
        command="brew install ripgrep", package_name="ripgrep", manager="brew",
        install_dir="/tmp", resolved_path=None, exit_code=0,
    )
    inst = store.update_install(db, inst.id, display_name="ripgrep",
                                what_it_does="fast grep", why="speed",
                                disposition="doc", metadata_complete=1)
    md = to_markdown(inst)
    assert "**ripgrep**" in md
    assert "`brew install ripgrep`" in md
    assert "speed" in md
