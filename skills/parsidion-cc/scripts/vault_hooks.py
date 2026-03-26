"""Hook utilities, event logging, environment management, and transcript analysis.

Provides hook event logging, safe environment construction for child processes,
transcript text extraction, project name detection, process checking, and
transcript category detection/parsing shared by session_stop and subagent_stop hooks.

This module is part of the vault_common split (ARC-005).  All public symbols
are re-exported from ``vault_common`` for backward compatibility.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from vault_config import get_config
from vault_fs import flock_exclusive, funlock
from vault_path import resolve_vault

__all__: list[str] = [
    # Environment helpers
    "env_without_claudecode",
    "_SAFE_ENV_KEYS",
    # Hook event logging
    "write_hook_event",
    # Transcript helpers
    "extract_text_from_content",
    # Project detection
    "get_project_name",
    # Process utilities
    "is_process_running",
    # Transcript analysis (shared by session_stop and subagent_stop hooks)
    "TRANSCRIPT_CATEGORIES",
    "TRANSCRIPT_CATEGORY_LABELS",
    "parse_transcript_lines",
    "detect_categories",
]

# ---------------------------------------------------------------------------
# Hook execution event log
# ---------------------------------------------------------------------------

_HOOK_EVENTS_FILENAME = "hook_events.log"
_HOOK_EVENTS_MAX_LINES_DEFAULT = 10000


def write_hook_event(
    hook: str,
    project: str,
    duration_ms: float,
    vault: Path | None = None,
    **extra: object,
) -> None:
    """Append a structured JSON event line to ``vault/hook_events.log``.

    Best-effort -- never raises. Controlled by ``event_log.enabled`` config
    (default: ``true``). Rotates (keeps last *max_lines*) when the file
    exceeds ``event_log.max_lines`` (default: 10 000).

    Args:
        hook: Hook name, e.g. ``"SessionEnd"``.
        project: Project name.
        duration_ms: Hook wall-clock time in milliseconds.
        vault: Optional vault path. Defaults to resolve_vault().
        **extra: Additional key-value pairs to include in the event object.
    """
    vault = vault or resolve_vault()
    if not get_config("event_log", "enabled", True):
        return

    event: dict[str, object] = {
        "hook": hook,
        "ts": datetime.now().isoformat(timespec="seconds"),
        "project": project,
        "duration_ms": round(duration_ms, 1),
    }
    event.update(extra)

    log_path = vault / _HOOK_EVENTS_FILENAME
    max_lines: int = int(
        get_config("event_log", "max_lines", _HOOK_EVENTS_MAX_LINES_DEFAULT)
    )

    try:
        vault.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event) + "\n"

        # Atomic append with optional rotation
        with open(log_path, "a+", encoding="utf-8") as f:
            flock_exclusive(f)
            try:
                f.seek(0)
                existing_lines = f.readlines()
                if len(existing_lines) >= max_lines:
                    # Keep the second half of the file to avoid thrashing
                    keep = existing_lines[max_lines // 2 :]
                    f.seek(0)
                    f.truncate()
                    f.writelines(keep)
                f.seek(0, 2)
                f.write(line)
            finally:
                funlock(f)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

# Variables safe to pass through to child processes (avoids leaking secrets).
# SEC-006: ANTHROPIC_* vars are intentionally included so that non-default API
# configurations (proxy, org key, Bedrock, Vertex, corporate proxy) are
# forwarded to child ``claude -p`` processes for AI features to work.
#
# Included Anthropic vars and their purpose:
#   ANTHROPIC_API_KEY           -- API key (non-default / org / proxy setups)
#   ANTHROPIC_AUTH_TOKEN        -- Bearer token alternative to API key
#   ANTHROPIC_BASE_URL          -- Custom endpoint (proxy, gateway, Bedrock)
#   ANTHROPIC_CUSTOM_HEADERS    -- Extra HTTP headers (corp auth, tracing)
#   ANTHROPIC_DEFAULT_HAIKU_MODEL   -- Pinned haiku model ID
#   ANTHROPIC_DEFAULT_SONNET_MODEL  -- Pinned sonnet model ID
#   ANTHROPIC_DEFAULT_OPUS_MODEL    -- Pinned opus model ID
#   API_TIMEOUT_MS              -- API call timeout in milliseconds
#   HTTPS_PROXY / HTTP_PROXY    -- Corporate / network proxy
_SAFE_ENV_KEYS: frozenset[str] = frozenset(
    {
        # Shell / locale
        "PATH",
        "HOME",
        "USER",
        "SHELL",
        "TERM",
        "LANG",
        "LC_ALL",
        "TMPDIR",
        # Anthropic API auth & routing
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_CUSTOM_HEADERS",
        # Model pinning
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        # Timeout
        "API_TIMEOUT_MS",
        # Network proxy
        "HTTPS_PROXY",
        "HTTP_PROXY",
    }
)


def env_without_claudecode() -> dict[str, str]:
    """Return a filtered copy of the current environment for child processes.

    Only includes variables listed in ``_SAFE_ENV_KEYS``, which avoids leaking
    secrets or triggering the Claude nesting guard (``CLAUDECODE``).

    Always injects ``PARSIDION_INTERNAL=1`` so that hook scripts invoked by the
    resulting ``claude -p`` session can detect and skip internal sessions.

    Returns:
        A dict suitable for passing as ``env=`` to ``subprocess.run`` / ``Popen``.
    """
    env = {k: v for k, v in os.environ.items() if k in _SAFE_ENV_KEYS}
    env["PARSIDION_INTERNAL"] = "1"
    return env


# ---------------------------------------------------------------------------
# Transcript helpers
# ---------------------------------------------------------------------------


def extract_text_from_content(content: str | list[dict]) -> str:
    """Extract plain text from a transcript message content field.

    Content can be a plain string or an array of content blocks (each with
    a ``type`` and ``text`` field for text blocks).

    Args:
        content: The message content -- either a string or list of blocks.

    Returns:
        Concatenated text from all text blocks.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return ""


# ---------------------------------------------------------------------------
# Project detection
# ---------------------------------------------------------------------------


def get_project_name(cwd: str | None = None) -> str:
    """Extract a project name from *cwd* or the current directory.

    Uses the basename of the directory. If the directory is inside a git
    repository, uses the repository root basename instead.
    """
    if cwd is None:
        cwd = os.getcwd()

    path = Path(cwd).resolve()

    # Walk up to find a .git directory
    check = path
    while check != check.parent:
        if (check / ".git").exists():
            return check.name
        check = check.parent

    # Fallback: basename of the given directory
    return path.name


# ---------------------------------------------------------------------------
# Process utilities
# ---------------------------------------------------------------------------


def is_process_running(pid: int) -> bool:
    """Return True if a process with *pid* is currently running.

    Uses ``os.kill(pid, 0)`` which sends no signal but checks process existence.
    Returns True on PermissionError (process exists but we lack permission).

    QA-007: Canonical implementation shared by update_index.py and vault_doctor.py.

    Args:
        pid: Process ID to check.

    Returns:
        True if the process is running (or exists but we cannot signal it).
    """
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # process exists; we lack permission to signal it


# ---------------------------------------------------------------------------
# Transcript analysis helpers (shared by session_stop and subagent_stop hooks)
# ---------------------------------------------------------------------------

TRANSCRIPT_CATEGORIES: dict[str, list[str]] = {
    "error_fix": [
        "fixed",
        "the issue was",
        "root cause",
        "the error",
        "resolved by",
        "the fix",
        "bug was",
        "problem was",
        "workaround",
    ],
    "research": [
        "found that",
        "documentation says",
        "according to",
        "turns out",
        "discovered that",
        "learned that",
        "it appears",
        "the docs say",
        "the spec says",
    ],
    "pattern": [
        "pattern",
        "approach",
        "technique",
        "best practice",
        "convention",
        "idiom",
        "architecture",
        "design decision",
    ],
    "config_setup": [
        "configured",
        "installed",
        "set up",
        "added to",
        "created",
        "initialized",
        "migrated",
        "deployed",
    ],
}

TRANSCRIPT_CATEGORY_LABELS: dict[str, str] = {
    "error_fix": "Error Resolution",
    "research": "Research Findings",
    "pattern": "Pattern Discovery",
    "config_setup": "Config/Setup",
}


def parse_transcript_lines(lines: list[str]) -> list[str]:
    """Parse JSONL transcript lines and extract assistant message text.

    Args:
        lines: Raw JSONL lines from the transcript file.

    Returns:
        A list of text strings from assistant messages.
    """
    assistant_texts: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        if entry.get("type") != "assistant":
            continue

        message = entry.get("message", entry)
        content = message.get("content")
        if content is None:
            continue

        text = extract_text_from_content(content)
        if text.strip():
            assistant_texts.append(text)

    return assistant_texts


def detect_categories(texts: list[str]) -> dict[str, list[str]]:
    """Scan assistant texts for learnable content using keyword heuristics.

    Args:
        texts: List of assistant message texts.

    Returns:
        Dict mapping category keys to lists of matching text excerpts
        (each truncated to 500 chars).
    """
    found: dict[str, list[str]] = {}

    for text in texts:
        text_lower = text.lower()
        for category, keywords in TRANSCRIPT_CATEGORIES.items():
            for keyword in keywords:
                if keyword in text_lower:
                    if category not in found:
                        found[category] = []
                    excerpt = text[:500].strip()
                    if excerpt and excerpt not in found[category]:
                        found[category].append(excerpt)
                    break

    return found
