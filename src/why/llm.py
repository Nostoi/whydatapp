from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

from why import store

PROMPT_VERSION = 1

SYSTEM_PROMPT_V1 = """You are helping a developer turn a terminal command transcript \
into a practical task recap.

Use only the transcript and metadata provided. Do not invent commands, files, \
output, errors, or motivations that are not supported by the data. If you infer \
intent, phrase it as an inference.

Write concise Markdown for a technical user. Prefer concrete steps and gotchas \
over general advice. Preserve command names exactly when referencing them. Do \
not include secrets. If a command appears redacted, keep the redacted marker.

If the transcript is too sparse to support a section, say so briefly in that \
section instead of guessing."""

USER_PROMPT_TEMPLATE = """Create a task recap from this whydatApp terminal session.

Return Markdown with exactly these top-level sections:

# <short task title>

## What happened
Summarize the actual sequence of work in chronological order.

## Clean steps
Give the clean command sequence someone should follow next time. Include only \
commands supported by the transcript. If setup depends on local context, mention that.

## Why these steps
Explain the likely purpose of the key steps. Mark uncertain explanations with "Likely:".

## Mistakes or detours
List failed commands, repeated attempts, changed direction, or confusing steps. \
If none are visible, say "No clear mistakes or detours are visible in the transcript."

## Gotchas
List practical warnings, prerequisites, path assumptions, version issues, \
services that may need restarting, or places where the transcript is ambiguous.

## Commands worth keeping
List the final useful commands as fenced shell blocks. Do not include commands \
that only failed unless they are useful diagnostics.

Session JSON:
```json
{payload_json}
```
"""


def requires_confirmation(policy: str, base_url: str) -> bool:
    """Whether sending a transcript to `base_url` needs explicit user confirmation.

    Shared by the CLI and the web UI so the two surfaces cannot drift: the web
    route previously had no gate at all, so one click could send a transcript to
    a remote endpoint the user had configured to always confirm.
    """
    if policy == "always":
        return True
    if policy == "never":
        return False
    host = (urlparse(base_url).hostname or "").lower()
    return host not in {"localhost", "127.0.0.1", "::1"}


def build_task_payload(
    session: store.TaskSession,
    commands: list[store.TaskSessionCommand],
    installs: list[store.Install],
    *,
    max_commands: int,
    llm_ignore_patterns: tuple[str, ...],
) -> dict[str, object]:
    ignored = 0
    kept: list[store.TaskSessionCommand] = []
    compiled = []
    for pattern in llm_ignore_patterns:
        try:
            compiled.append(re.compile(pattern))
        except re.error as e:
            # User-authored file: a typo must not surface as a raw re.error
            # (traceback in the CLI, HTTP 500 in the web UI).
            raise ValueError(f"Invalid pattern {pattern!r} in llm-ignore.toml: {e}") from e
    for command in commands:
        if any(pattern.search(command.command) for pattern in compiled):
            ignored += 1
        else:
            kept.append(command)

    # Clamp: a 0 or negative value would otherwise send an empty list, or - via
    # kept[:-n] - silently behead the newest commands.
    limit = max(1, max_commands)
    truncated = max(0, len(kept) - limit)
    # Keep the MOST RECENT commands: the prompt asks for "the final useful
    # commands", which is exactly what oldest-first truncation would delete.
    kept = kept[-limit:]

    return {
        "app": "whydatApp",
        "task_session": {
            "id": session.id,
            "title": session.title,
            "project": session.project,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
            "cwd_start": session.cwd_start,
            "cwd_end": session.cwd_end,
            "shell": session.shell,
            "source": session.source,
        },
        "commands": [
            {
                "position": command.position,
                "command": command.command,
                "cwd": command.cwd,
                "exit_code": command.exit_code,
                "started_at": command.started_at,
                "ended_at": command.ended_at,
                "matched_install_id": command.matched_install_id,
            }
            for command in kept
        ],
        "known_installs": [
            {
                "id": install.id,
                "manager": install.manager,
                "package_name": install.package_name,
                "resolved_path": install.resolved_path,
            }
            for install in installs
        ],
        "omissions": {
            "truncated_commands": truncated,
            "truncated_from": "oldest",
            "llm_ignored_commands": ignored,
        },
    }


def normalized_payload_hash(payload: dict[str, object]) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_user_prompt(payload: dict[str, object]) -> str:
    payload_json = json.dumps(payload, indent=2, sort_keys=True)
    return USER_PROMPT_TEMPLATE.format(payload_json=payload_json)


def summarize_openai_compatible(
    *,
    base_url: str,
    api_key: str | None,
    model: str,
    system_prompt: str,
    user_prompt: str,
    timeout_seconds: int,
) -> str:
    url = f"{base_url.rstrip('/')}/chat/completions"
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    # Only the configured api_key_env is honoured. A hardcoded WHY_LLM_API_KEY
    # fallback would ship a stale credential to whatever endpoint is configured.
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        raise RuntimeError(f"LLM request failed: {e}") from e
    except TimeoutError as e:
        # Not a URLError subclass: a slow endpoint (e.g. Ollama loading a model)
        # would otherwise surface as a bare traceback.
        raise RuntimeError(f"LLM request timed out after {timeout_seconds}s") from e
    except OSError as e:
        raise RuntimeError(f"LLM request failed: {e}") from e

    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError as e:
        # A proxy or gateway can return an HTML error/login page with status 200.
        raise RuntimeError("LLM returned a non-JSON response") from e

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError("LLM response did not include choices[0].message.content") from e
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("LLM response was empty")
    return content
