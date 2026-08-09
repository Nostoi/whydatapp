"""Render the Homebrew formula for a released why-cli version.

The tap (`Nostoi/homebrew-why`) is generated, never hand-edited. Homebrew vendors
every transitive dependency as a `resource` built from source, so the formula has
to be regenerated whenever the resolved dependency set moves — and nothing else
validates a tap: a stale resource surfaces at a user's `brew install`, never in
this repo's CI.

Two inputs, both derived from PyPI rather than from this checkout:

* the sdist URL + sha256 for `why-cli==<version>`
* the fully resolved dependency set for `why-cli[web]==<version>`, each with its
  own sdist URL + sha256

Resolving from PyPI rather than reading `uv.lock` is deliberate. `uv.lock` is the
*development* resolution; users get whatever the resolver picks from the ranges in
`pyproject.toml`. Those diverged far enough once to ship a release that crashed on
every command, so the formula is built from what a user would actually get.

Usage:
    python3 scripts/render_homebrew_formula.py 2.3.9 > Formula/why-cli.rb
    python3 scripts/render_homebrew_formula.py 2.3.9 --pins pins.txt   # offline
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

PYPI = "https://pypi.org/pypi"
PACKAGE = "why-cli"

FORMULA_TEMPLATE = '''\
class WhyCli < Formula
  include Language::Python::Virtualenv

  desc "Track why you installed every tool on your machine"
  homepage "https://github.com/Nostoi/whydatapp"
  url "{url}"
  sha256 "{sha256}"
  license "MIT"
  head "https://github.com/Nostoi/whydatapp.git", branch: "main"

  # pydantic-core (via fastapi) is the only dependency below without a pure-Python
  # build, hence the Rust build dependency. `uvicorn[standard]` was dropped upstream
  # in 2.3.7 precisely so uvloop, httptools, watchfiles, and websockets would not
  # each need a compiler here too.
  depends_on "rust" => :build
  depends_on "python@3.13"

{resources}
  # The web extra's dependencies are vendored as resources above, so the app's
  # optional `[web]` surface works even though the sdist is installed without
  # extras — the marker only gates dependency resolution, never any code, and
  # `why/web/` ships in the distribution unconditionally.
  def install
    virtualenv_install_with_resources
  end

  def caveats
    <<~EOS
      Capture is not active until you run:
        why init

      That installs a hook into your shell's rc file and asks before changing
      anything. Start a new shell afterwards, or run `exec $SHELL -l`.

      Upgrades take care of themselves: `brew upgrade why-cli` is enough. The
      shell hook in ~/.why/ refreshes itself on the next `why` command and tells
      you when to restart your shell.
    EOS
  end

  test do
    # Version reporting must work at all — this is the check that would have
    # caught the 2.2.1 release, where a missing transitive dependency made every
    # command exit non-zero.
    assert_match "why #{{version}}", shell_output("#{{bin}}/why --version")

    # A real command against an isolated home, so the test never touches ~/.why.
    ENV["WHY_HOME"] = testpath/"why"
    assert_match "No installs", shell_output("#{{bin}}/why list")

    # The web extra is the reason this formula vendors so many resources; prove
    # it imports rather than trusting the resource list.
    system libexec/"bin/python", "-c", "import why.web.app, uvicorn, fastapi"
  end
end
'''


class FormulaError(RuntimeError):
    """Anything that should stop the bump rather than publish a broken formula."""


def fetch_json(url: str, *, attempts: int = 30, delay: int = 20) -> dict:
    """GET JSON, retrying while PyPI's index catches up with a fresh release.

    A release is visible on the JSON API before the simple index serves it, and
    the sdist can 404 briefly after publish. Both were hit by hand on 2026-08-08,
    so the retry is load-bearing rather than defensive.
    """
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(url) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            last = exc
        except urllib.error.URLError as exc:
            last = exc
        if attempt < attempts - 1:
            print(f"  waiting for {url} ({attempt + 1}/{attempts})", file=sys.stderr)
            time.sleep(delay)
    raise FormulaError(f"gave up fetching {url}: {last}")


def sdist_for(name: str, version: str) -> tuple[str, str]:
    """(url, sha256) of a release's source distribution."""
    data = fetch_json(f"{PYPI}/{name}/{version}/json")
    sdists = [u for u in data["urls"] if u["packagetype"] == "sdist"]
    if not sdists:
        # Homebrew builds resources from source; a wheel-only dependency cannot be
        # vendored, and silently skipping it would produce a formula that fails at
        # a user's install rather than here.
        raise FormulaError(f"{name}=={version} publishes no sdist")
    return sdists[0]["url"], sdists[0]["digests"]["sha256"]


def resolve_pins(version: str, *, attempts: int = 30, delay: int = 20) -> list[tuple[str, str]]:
    """Resolve why-cli[web]==version the way a user's install would.

    Retried because PyPI's *simple index* — which uv reads — lags the JSON API
    that `sdist_for` uses. Immediately after a release, the JSON API happily
    reports the new version while resolution still fails with "no version of
    why-cli[web]==<version>". Both were observed by hand on 2026-08-08.
    """
    with tempfile.TemporaryDirectory() as tmp:
        env = Path(tmp) / "venv"
        subprocess.run(["uv", "venv", "-q", str(env)], check=True)
        python = env / "bin" / "python"
        for attempt in range(attempts):
            result = subprocess.run(
                ["uv", "pip", "install", "-q", "--refresh", "--no-cache",
                 "--python", str(python), f"{PACKAGE}[web]=={version}"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                break
            if attempt == attempts - 1:
                raise FormulaError(
                    f"could not resolve {PACKAGE}[web]=={version} after "
                    f"{attempts} attempts: {result.stderr.strip()[:400]}"
                )
            print(f"  waiting for the index to serve {version} "
                  f"({attempt + 1}/{attempts})", file=sys.stderr)
            time.sleep(delay)
        listing = subprocess.run(
            ["uv", "pip", "list", "--python", str(python), "--format", "json"],
            check=True, capture_output=True, text=True,
        )
    pins = [(p["name"], p["version"]) for p in json.loads(listing.stdout)]
    pins = [(n, v) for n, v in pins if n.lower().replace("_", "-") != PACKAGE]
    if not pins:
        raise FormulaError(
            "resolution produced no dependencies — refusing to write an empty formula"
        )
    return sorted(pins, key=lambda p: p[0].lower())


def read_pins(path: Path) -> list[tuple[str, str]]:
    pins = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, ver = line.partition("==")
        if name.lower().replace("_", "-") != PACKAGE:
            pins.append((name, ver))
    return sorted(pins, key=lambda p: p[0].lower())


def render_resources(pins: list[tuple[str, str]]) -> str:
    # Sorted here rather than only in the callers: the formula is committed to a
    # git repo, so an unstable order turns "nothing changed" into a diff, and a
    # real change into noise nobody reads.
    blocks = []
    for name, version in sorted(pins, key=lambda p: p[0].lower()):
        url, sha = sdist_for(name, version)
        # Homebrew audits that a resource's name matches the PyPI project name in
        # its normalised (hyphenated) form; `pydantic_core` fails that check.
        resource_name = name.lower().replace("_", "-")
        blocks.append(
            f'  resource "{resource_name}" do\n'
            f'    url "{url}"\n'
            f'    sha256 "{sha}"\n'
            f"  end\n"
        )
    return "\n".join(blocks)


def render(version: str, pins: list[tuple[str, str]]) -> str:
    url, sha = sdist_for(PACKAGE, version)
    return FORMULA_TEMPLATE.format(url=url, sha256=sha, resources=render_resources(pins))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="released why-cli version, e.g. 2.3.9")
    parser.add_argument(
        "--pins",
        type=Path,
        help="file of name==version lines to use instead of resolving (for tests)",
    )
    args = parser.parse_args()

    pins = read_pins(args.pins) if args.pins else resolve_pins(args.version)
    print(f"  {len(pins)} dependencies pinned", file=sys.stderr)
    sys.stdout.write(render(args.version, pins))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FormulaError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
