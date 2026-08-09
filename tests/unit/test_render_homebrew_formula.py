"""The Homebrew formula generator.

The tap is generated and nothing else validates it: a malformed formula surfaces
at a user's `brew install`, never in this repo's CI. These cover the failure modes
that would produce a *plausible-looking* formula rather than a crash.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "render_homebrew_formula",
    Path(__file__).resolve().parents[2] / "scripts" / "render_homebrew_formula.py",
)
assert _SPEC and _SPEC.loader
rhf = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rhf)


@pytest.fixture
def fake_sdists(monkeypatch):
    """Answer sdist lookups locally so the tests never touch PyPI."""
    seen: list[tuple[str, str]] = []

    def _sdist_for(name: str, version: str, **_kwargs: object) -> tuple[str, str]:
        seen.append((name, version))
        return (
            f"https://files.pythonhosted.org/packages/ab/cd/{name}-{version}.tar.gz",
            f"sha-{name}-{version}",
        )

    monkeypatch.setattr(rhf, "sdist_for", _sdist_for)
    return seen


def test_resource_names_are_normalised(fake_sdists):
    """`brew audit` rejects `pydantic_core`; it must be `pydantic-core`.

    This shipped as a real audit failure on the first formula, because the
    generator used PyPI's display name rather than the normalised one.
    """
    out = rhf.render_resources([("pydantic_core", "2.46.4")])
    assert 'resource "pydantic-core" do' in out
    assert "pydantic_core" not in out.split("url")[0]


def test_render_emits_one_resource_per_pin(fake_sdists):
    pins = [("rich", "15.0.0"), ("typer", "0.27.1"), ("tomli-w", "1.2.0")]
    out = rhf.render(  # noqa: SLF001 - exercising the public render path
        "2.3.9", pins
    )
    assert out.count("  resource ") == len(pins)
    for name, version in pins:
        assert f'resource "{name}" do' in out
        assert f"sha-{name}-{version}" in out


def test_rendered_formula_keeps_ruby_interpolation_intact(fake_sdists):
    """`#{version}` and `#{bin}` are Ruby, not Python format fields.

    The template is written with doubled braces; a regression here yields a
    formula whose test block references a literal `#{{version}}` and fails only
    under `brew test`.
    """
    out = rhf.render("2.3.9", [("rich", "15.0.0")])
    assert 'assert_match "why #{version}"' in out
    assert '#{bin}/why --version' in out
    assert "{{" not in out


def test_render_is_deterministic(fake_sdists):
    pins = [("typer", "0.27.1"), ("rich", "15.0.0")]
    assert rhf.render("2.3.9", pins) == rhf.render("2.3.9", list(reversed(pins)))


def test_missing_sdist_is_fatal(monkeypatch):
    """A wheel-only dependency cannot be vendored as a Homebrew resource.

    Skipping it would produce a formula that looks fine and fails at install.
    """
    def _no_sdist(url, **kwargs):
        return {"urls": [{"packagetype": "bdist_wheel", "digests": {"sha256": "x"}}]}

    monkeypatch.setattr(rhf, "fetch_json", _no_sdist)
    with pytest.raises(rhf.FormulaError, match="no sdist"):
        rhf.sdist_for("somepkg", "1.0")


def test_tls_failure_fails_fast_instead_of_retrying(monkeypatch):
    """A cert problem is a broken environment, not a slow index.

    Retrying it burned 30 attempts x 20s per URL and then blamed the index —
    ~10 minutes per package, which reads as a hang. Observed for real against a
    venv with no usable cert store.
    """
    import ssl
    import urllib.error

    calls = {"n": 0}

    def _urlopen(url, *a, **k):
        calls["n"] += 1
        raise urllib.error.URLError(ssl.SSLError("CERTIFICATE_VERIFY_FAILED"))

    monkeypatch.setattr(rhf.urllib.request, "urlopen", _urlopen)
    monkeypatch.setattr(rhf.time, "sleep", lambda _s: pytest.fail("slept on a TLS error"))

    with pytest.raises(rhf.FormulaError, match="certificate-store problem"):
        rhf.fetch_json("https://pypi.org/pypi/rich/15.0.0/json", attempts=30, delay=20)
    assert calls["n"] == 1, "must not retry a permanent failure"


def test_transient_404_is_retried(monkeypatch):
    """The index genuinely lags a fresh publish; that one must keep trying."""
    import urllib.error

    calls = {"n": 0}

    def _urlopen(url, *a, **k):
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        raise SystemExit("reached the success path")

    monkeypatch.setattr(rhf.urllib.request, "urlopen", _urlopen)
    monkeypatch.setattr(rhf.time, "sleep", lambda _s: None)

    with pytest.raises(SystemExit):
        rhf.fetch_json("https://pypi.org/pypi/why-cli/9.9.9/json", attempts=5, delay=0)
    assert calls["n"] == 3


def test_dependency_lookups_use_a_small_retry_budget(monkeypatch):
    """Dependency versions were published long ago; only the release can lag.

    A generous budget here turns one bad pin into a multi-hour job.
    """
    seen = {}

    def _fetch(url, *, attempts=30):
        seen[url] = attempts
        return {"urls": [{"packagetype": "sdist", "url": "u",
                          "digests": {"sha256": "s"}}]}

    monkeypatch.setattr(rhf, "fetch_json", _fetch)
    rhf.sdist_for("rich", "15.0.0")
    assert seen["https://pypi.org/pypi/rich/15.0.0/json"] == 3
    rhf.sdist_for("why-cli", "2.3.9", attempts=30)
    assert seen["https://pypi.org/pypi/why-cli/2.3.9/json"] == 30


def test_read_pins_drops_the_package_itself(tmp_path: Path):
    """why-cli is the formula's `url`, not one of its resources."""
    f = tmp_path / "pins.txt"
    f.write_text("# comment\nrich==15.0.0\nwhy-cli==2.3.9\n\ntyper==0.27.1\n")
    assert rhf.read_pins(f) == [("rich", "15.0.0"), ("typer", "0.27.1")]


def test_read_pins_is_sorted_case_insensitively(tmp_path: Path):
    f = tmp_path / "pins.txt"
    f.write_text("Pygments==2.20.0\nanyio==4.14.2\n")
    assert [n for n, _ in rhf.read_pins(f)] == ["anyio", "Pygments"]


def test_empty_resolution_is_refused(monkeypatch):
    """An empty dependency set means resolution broke, not that there are none.

    Writing that formula would silently strip every resource and ship a tool that
    cannot import anything.
    """
    monkeypatch.setattr(rhf.subprocess, "run", lambda *a, **k: _Completed("[]"))
    with pytest.raises(rhf.FormulaError, match="empty formula"):
        rhf.resolve_pins("2.3.9")


def test_resolution_retries_while_the_index_lags(monkeypatch):
    """PyPI's simple index lags the JSON API right after a release.

    Without the retry the bump job fails on exactly the releases it exists for.
    """
    calls = {"n": 0}

    def _run(cmd, **kwargs):
        if "install" in cmd:
            calls["n"] += 1
            if calls["n"] < 3:
                return _Completed("", returncode=1, stderr="no version of why-cli[web]")
            return _Completed("", returncode=0)
        return _Completed('[{"name": "rich", "version": "15.0.0"}]')

    monkeypatch.setattr(rhf.subprocess, "run", _run)
    monkeypatch.setattr(rhf.time, "sleep", lambda _s: None)

    assert rhf.resolve_pins("2.3.9", attempts=5, delay=0) == [("rich", "15.0.0")]
    assert calls["n"] == 3


def test_resolution_gives_up_with_a_clear_error(monkeypatch):
    def _run(cmd, **kwargs):
        if "install" in cmd:
            return _Completed("", returncode=1, stderr="no version of why-cli[web]")
        return _Completed("[]")

    monkeypatch.setattr(rhf.subprocess, "run", _run)
    monkeypatch.setattr(rhf.time, "sleep", lambda _s: None)
    with pytest.raises(rhf.FormulaError, match="could not resolve"):
        rhf.resolve_pins("2.3.9", attempts=2, delay=0)


class _Completed:
    def __init__(self, stdout: str, *, returncode: int = 0, stderr: str = "") -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
