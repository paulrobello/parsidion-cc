#!/usr/bin/env python3
"""Claude Code PreCompact hook that snapshots working state before compaction.

Reads JSON from stdin with session info, analyzes the last N lines of the
transcript to identify the current task and files being worked on, then
writes a pre-compact snapshot section to today's daily note.
"""

import argparse
import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

# These scripts are not a proper package — sys.path.insert is intentional so
# each script can run standalone via ``uv run`` or ``python`` without requiring
# pip install or editable installs.  See ARC-009 in AUDIT.md.
sys.path.insert(0, str(Path(__file__).parent))

import vault_common  # noqa: E402

# Tool names and the input fields that contain file paths
_FILE_TOOLS: dict[str, list[str]] = {
    "Read": ["file_path"],
    "Write": ["file_path"],
    "Edit": ["file_path"],
    "NotebookEdit": ["notebook_path"],
    "Grep": ["path"],
}


# Utility functions imported from vault_common (canonical implementation)
extract_text_from_content = vault_common.extract_text_from_content
read_last_n_lines = vault_common.read_last_n_lines


def extract_user_task(lines: list[str]) -> str:
    """Extract the current task from the most recent user text message.

    Scans lines in reverse to find the latest ``type: "user"`` entry that
    contains a plain text block (not a tool_result). In active sessions the
    tail of a transcript is dominated by tool_result/tool_use pairs; the
    actual typed user message is further back.

    Args:
        lines: Raw JSONL lines from the transcript.

    Returns:
        First line of the most recent user text message (max 200 chars),
        or ``"Unknown task"`` if none is found.
    """
    for raw_line in reversed(lines):
        line = raw_line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        if entry.get("type") != "user":
            continue

        message = entry.get("message", entry)
        content = message.get("content")

        # Plain string content
        if isinstance(content, str):
            text = content.strip()
            if len(text) > 10:
                return text.split("\n")[0][:200].strip()
            continue

        # List of content blocks — look for text blocks, skip tool_result
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    text = block.get("text", "")
                    if isinstance(text, str) and len(text.strip()) > 10:
                        return text.strip().split("\n")[0][:200].strip()

    return "Unknown task"


def extract_file_paths(lines: list[str]) -> list[str]:
    """Extract file paths from tool_use blocks in recent assistant messages.

    Parses assistant message content for tool_use blocks from known file
    tools (Read, Write, Edit, etc.) and extracts their path inputs directly,
    avoiding false positives from regex matching over raw JSON.

    Args:
        lines: Raw JSONL lines from the transcript.

    Returns:
        A deduplicated list of file paths found (max 15).
    """
    seen: set[str] = set()
    paths: list[str] = []

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
        if not isinstance(content, list):
            continue

        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            tool_name = block.get("name", "")
            input_data = block.get("input", {})
            if not isinstance(input_data, dict):
                continue
            for field in _FILE_TOOLS.get(tool_name, []):
                path_val = input_data.get(field, "")
                if isinstance(path_val, str) and os.path.isabs(path_val):
                    if path_val not in seen:
                        seen.add(path_val)
                        paths.append(path_val)
                        if len(paths) >= 15:
                            return paths

    return paths


def append_snapshot_to_daily(
    project: str,
    task_summary: str,
    recent_files: list[str],
) -> None:
    """Append a pre-compact snapshot section to today's daily note.

    Args:
        project: The project name.
        task_summary: Brief description of the current task.
        recent_files: List of file paths being worked on.
    """
    daily_path = vault_common.create_daily_note_if_missing()
    now_time = datetime.now().strftime("%H:%M")

    files_str = ", ".join(recent_files[:10]) if recent_files else "None detected"

    section = (
        f"\n## Pre-Compact Snapshot ({now_time})\n"
        f"- **Project**: {project}\n"
        f"- **Working on**: {task_summary}\n"
        f"- **Recent files**: {files_str}\n"
    )

    try:
        existing = daily_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        existing = ""

    updated = existing + section
    daily_path.write_text(updated, encoding="utf-8")


_DEFAULT_LINES = 200


def main() -> None:
    """Entry point: read session JSON from stdin, snapshot state to daily note."""
    parser = argparse.ArgumentParser(
        description="Claude Code PreCompact hook — snapshots working state to daily note.",
    )
    parser.add_argument(
        "--lines",
        type=int,
        default=None,
        metavar="N",
        help=f"Number of transcript lines to analyse (default: {_DEFAULT_LINES})",
    )
    args = parser.parse_args()

    try:
        input_data: dict = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        sys.stdout.write("{}")
        return

    try:
        cwd: str = input_data.get("cwd", "")
        transcript_path_str: str = input_data.get("transcript_path", "")

        # Ensure vault directories exist
        vault_common.ensure_vault_dirs()

        project: str = vault_common.get_project_name(cwd) if cwd else "unknown"

        # Resolve options: defaults → config → CLI args
        lines: int = (
            args.lines
            if args.lines is not None
            else vault_common.get_config("pre_compact_hook", "lines", _DEFAULT_LINES)
        )

        task_summary: str = "Unknown task"
        recent_files: list[str] = []

        if transcript_path_str:
            transcript_path = Path(transcript_path_str)
            if transcript_path.is_file():
                raw_lines: list[str] = read_last_n_lines(transcript_path, lines)
                task_summary = extract_user_task(raw_lines)
                recent_files = extract_file_paths(raw_lines)

        append_snapshot_to_daily(project, task_summary, recent_files)
        vault_common.git_commit_vault(f"chore(vault): pre-compact snapshot [{project}]")

        sys.stdout.write("{}")

    except Exception:
        traceback.print_exc(file=sys.stderr)
        # On any error, output empty JSON and exit cleanly
        sys.stdout.write("{}")


if __name__ == "__main__":
    main()
