"""
redact.py — strip secrets from shell commands before storing.

Conservative: only redacts patterns that are clearly sensitive.
Preserves command structure so the history remains useful.
"""
from __future__ import annotations

import re

# Patterns that look like secret values in common flag styles:
#   --password=secret   --token=abc123   --api-key=xyz
#   -p secret           PASSWORD=secret  (env-var prefix)
_FLAG_PATTERN = re.compile(
    r"""
    (?:
        # --flag=value or --flag value where flag name is sensitive
        (?P<flag>
            --(?:password|passwd|token|secret|api[-_]?key|auth[-_]?token|
                 private[-_]?key|access[-_]?key|client[-_]?secret)
            (?:=|\s+)
        )
        (?P<flag_val>\S+)
    |
        # -p value  (short flag for password, common in mysql/psql/ssh)
        (?P<short>-p\s+)(?P<short_val>\S+)
    |
        # ENV=value prefix where name contains sensitive word
        (?P<env>
            \b[A-Z][A-Z0-9_]*
            (?:PASSWORD|PASSWD|TOKEN|SECRET|API_KEY|AUTH_TOKEN|
               PRIVATE_KEY|ACCESS_KEY|CLIENT_SECRET)
            [A-Z0-9_]*=
        )
        (?P<env_val>\S+)
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

_REDACTED = "[REDACTED]"


def redact(command: str) -> str:
    """Return *command* with secret values replaced by [REDACTED]."""

    def _replace(m: re.Match[str]) -> str:
        if m.group("flag") is not None:
            sep = "=" if "=" in m.group("flag") else " "
            name = m.group("flag").rstrip("= ").rstrip()
            return f"{name}{sep}{_REDACTED}"
        if m.group("short") is not None:
            return f"{m.group('short')}{_REDACTED}"
        if m.group("env") is not None:
            return f"{m.group('env')}{_REDACTED}"
        return m.group(0)  # fallback — shouldn't happen

    return _FLAG_PATTERN.sub(_replace, command)
