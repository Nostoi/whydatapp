from __future__ import annotations

import pytest

from why.redact import redact


@pytest.mark.parametrize("cmd,expected", [
    # Passthrough — nothing sensitive
    ("brew install ripgrep", "brew install ripgrep"),
    ("git clone https://github.com/foo/bar", "git clone https://github.com/foo/bar"),
    ("ls -la /tmp", "ls -la /tmp"),
    # --flag=value
    ("curl --token=abc123 https://api.example.com", "curl --token=[REDACTED] https://api.example.com"),
    ("curl --password=hunter2 https://host", "curl --password=[REDACTED] https://host"),
    ("cmd --api-key=xyz789", "cmd --api-key=[REDACTED]"),
    ("cmd --api_key=xyz789", "cmd --api_key=[REDACTED]"),
    ("cmd --secret=shh", "cmd --secret=[REDACTED]"),
    ("cmd --client-secret=abc", "cmd --client-secret=[REDACTED]"),
    # --flag value (space-separated)
    ("mysql --password hunter2 -u root", "mysql --password [REDACTED] -u root"),
    ("cmd --token abc123 --other val", "cmd --token [REDACTED] --other val"),
    # -p value (short password flag)
    ("mysql -p mypass -u root", "mysql -p [REDACTED] -u root"),
    # ENV=value prefix
    ("GITHUB_TOKEN=ghp_xxx git push", "GITHUB_TOKEN=[REDACTED] git push"),
    ("MY_API_KEY=secret123 curl https://host", "MY_API_KEY=[REDACTED] curl https://host"),
    ("DATABASE_PASSWORD=abc123 rails db:migrate", "DATABASE_PASSWORD=[REDACTED] rails db:migrate"),
    # Multiple secrets in one command
    (
        "curl --token=t1 --password=p1 https://host",
        "curl --token=[REDACTED] --password=[REDACTED] https://host",
    ),
])
def test_redact(cmd: str, expected: str) -> None:
    assert redact(cmd) == expected


def test_redact_preserves_non_secret_flags() -> None:
    cmd = "docker run --name myapp --port 8080 myimage"
    assert redact(cmd) == cmd


def test_redact_idempotent() -> None:
    cmd = "curl --token=abc https://host"
    assert redact(redact(cmd)) == redact(cmd)
