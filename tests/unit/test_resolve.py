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
