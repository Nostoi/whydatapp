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
