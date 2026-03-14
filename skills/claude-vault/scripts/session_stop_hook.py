#!/usr/bin/env python3
"""Claude Code SessionEnd hook that captures learnings from the session transcript.

Registered under the SessionEnd hook — fires once when the session terminates,
not on every turn. Reads JSON from stdin with session info, analyzes the last
200 lines of the transcript JSONL file to detect learnable content (error fixes,
research findings, patterns, config/setup), and queues session transcripts for
AI-powered summarization.

Optional --ai flag uses claude haiku to intelligently classify session content
and decide whether it is worth queuing, replacing the keyword heuristics with
semantic understanding. Falls back to keyword detection on failure.
Note: when --ai is used, increase the hook timeout in settings.json to at
least 30000ms to allow time for the AI call to complete.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path

# These scripts are not a proper package — sys.path.insert is intentional so
# each script can run standalone via ``uv run`` or ``python`` without requiring
# pip install or editable installs.  See ARC-009 in AUDIT.md.
sys.path.insert(0, str(Path(__file__).parent))

import vault_common  # noqa: E402

_DEFAULT_AI_MODEL = "claude-haiku-4-5-20251001"
_DEFAULT_AI_TIMEOUT = 25  # seconds; hook timeout in settings.json should be >= 30000ms

# File locking imported from vault_common (canonical implementation)
_flock_exclusive = vault_common.flock_exclusive
_funlock = vault_common.funlock


# Heuristic keyword sets for detecting learnable content categories
_CATEGORIES: dict[str, list[str]] = {
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

# Map category keys to human-readable labels
_CATEGORY_LABELS: dict[str, str] = {
    "error_fix": "Error Resolution",
    "research": "Research Findings",
    "pattern": "Pattern Discovery",
    "config_setup": "Config/Setup",
}


def _classify_session_with_ai(
    assistant_texts: list[str],
    project: str,
    model: str,
) -> dict[str, object] | None:
    """Use claude haiku to classify session content and decide if it's worth queuing.

    Runs ``claude -p`` with CLAUDECODE unset to avoid the nesting guard.
    Falls back to keyword heuristics (returns None) on any failure.

    Args:
        assistant_texts: List of assistant message texts from the transcript.
        project: The current project name.
        model: The claude model ID to use.

    Returns:
        Dict with keys ``should_queue`` (bool), ``categories`` (list[str]),
        and ``summary`` (str), or None on failure.
    """
    # Build a condensed sample — up to 300 chars from each of the first 10 messages
    sample_parts: list[str] = []
    char_budget = 1500
    for text in assistant_texts[:10]:
        chunk = text[:300].strip()
        if not chunk:
            continue
        remaining = char_budget - sum(len(p) for p in sample_parts)
        if remaining <= 0:
            break
        sample_parts.append(chunk[:remaining])

    if not sample_parts:
        return None

    content = "\n---\n".join(sample_parts)

    prompt = (
        f"Analyze this Claude Code session transcript for project '{project}'.\n\n"
        "Session assistant messages (condensed):\n"
        f"<content>\n{content}\n</content>\n\n"
        "Determine if this session contains knowledge worth archiving.\n\n"
        "Return ONLY valid JSON (no markdown, no explanation):\n"
        '{"should_queue": true, "categories": ["error_fix"], "summary": "..."}\n\n'
        "Categories (include only those that apply): error_fix, research, pattern, config_setup\n\n"
        "Set should_queue=true ONLY if the session contains:\n"
        "- A non-trivial bug fix with an identifiable root cause\n"
        "- Research findings or documentation discoveries\n"
        "- A reusable pattern or architectural insight\n"
        "- Non-obvious configuration or setup knowledge\n\n"
        "Set should_queue=false for:\n"
        "- Routine code edits with no transferable insight\n"
        "- Simple feature additions using obvious approaches\n"
        "- Back-and-forth without clear resolution\n\n"
        "summary: one sentence (max 200 chars) of the key learning, or empty string if should_queue=false."
    )

    try:
        result = subprocess.run(
            [
                "claude",
                "-p",
                prompt,
                "--model",
                model,
                "--no-session-persistence",
            ],
            capture_output=True,
            text=True,
            timeout=vault_common.get_config(
                "session_stop_hook", "ai_timeout", _DEFAULT_AI_TIMEOUT
            ),
            env=vault_common.env_without_claudecode(),
        )
        if result.returncode != 0:
            return None
        output = result.stdout.strip()
        if not output:
            return None

        # Strip markdown code fences if present
        if output.startswith("```"):
            lines = output.splitlines()
            output = "\n".join(
                line for line in lines if not line.startswith("```")
            ).strip()

        parsed = json.loads(output)
        should_queue = bool(parsed.get("should_queue", False))
        categories_raw = parsed.get("categories", [])
        valid_categories = {"error_fix", "research", "pattern", "config_setup"}
        categories = [c for c in categories_raw if c in valid_categories]
        summary = str(parsed.get("summary", ""))[:200]

        return {
            "should_queue": should_queue,
            "categories": categories,
            "summary": summary,
        }
    except (
        subprocess.TimeoutExpired,
        FileNotFoundError,
        OSError,
        json.JSONDecodeError,
        ValueError,
    ):
        return None


# Utility functions imported from vault_common (canonical implementation)
extract_text_from_content = vault_common.extract_text_from_content
read_last_n_lines = vault_common.read_last_n_lines


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

        # Content can be at entry["message"]["content"] or entry["content"]
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
        for category, keywords in _CATEGORIES.items():
            for keyword in keywords:
                if keyword in text_lower:
                    if category not in found:
                        found[category] = []
                    # Only keep first 500 chars as a brief excerpt
                    excerpt = text[:500].strip()
                    if excerpt and excerpt not in found[category]:
                        found[category].append(excerpt)
                    break  # One match per category per text is enough

    return found


def append_session_to_daily(
    project: str,
    categories: dict[str, list[str]],
    first_summary: str,
) -> None:
    """Append a session summary section to today's daily note.

    Args:
        project: The project name.
        categories: Detected category keys mapped to excerpts.
        first_summary: The first significant assistant message summary.
    """
    daily_path = vault_common.create_daily_note_if_missing()
    now_time = datetime.now().strftime("%H:%M")

    topic_labels = [_CATEGORY_LABELS.get(cat, cat) for cat in categories]
    topics_str = ", ".join(topic_labels) if topic_labels else "General"

    # Truncate the summary for the daily note
    summary_text = first_summary[:300].replace("\n", " ").strip()
    if not summary_text:
        summary_text = "Session completed"

    section = (
        f"\n### Session: {project} ({now_time})\n"
        f"- **Topics**: {topics_str}\n"
        f"- **Summary**: {summary_text}\n"
    )

    try:
        existing = daily_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        existing = ""

    # Append under the ## Sessions heading if it exists, else append at end
    if "## Sessions" in existing:
        # Find the end of the Sessions section (next ## heading or end of file)
        sessions_idx = existing.index("## Sessions")
        rest = existing[sessions_idx + len("## Sessions") :]

        # Find the next ## heading after Sessions
        next_heading_match = re.search(r"\n## ", rest)
        if next_heading_match:
            insert_pos = sessions_idx + len("## Sessions") + next_heading_match.start()
            updated = existing[:insert_pos] + section + existing[insert_pos:]
        else:
            updated = existing + section
    else:
        updated = existing + "\n## Sessions\n" + section

    daily_path.write_text(updated, encoding="utf-8")


def append_to_pending(
    transcript_path: Path,
    project: str,
    categories: dict[str, list[str]],
    force: bool = False,
) -> None:
    """Append a session entry to the pending summaries queue.

    Only appends when at least one significant category is detected,
    unless *force* is True (used when the AI gate has already decided).
    Guards against duplicates by session ID (transcript filename stem).

    Args:
        transcript_path: Path to the session transcript JSONL file.
        project: The project name.
        categories: Detected categories mapping keys to excerpt lists.
        force: Skip the significance filter; queue unconditionally.
    """
    all_keys = set(categories.keys())
    if not force:
        significant = {"error_fix", "research", "pattern"}
        if not (significant & all_keys):
            return

    pending_path = vault_common.VAULT_ROOT / "pending_summaries.jsonl"
    session_id = transcript_path.stem

    entry = {
        "session_id": session_id,
        "transcript_path": str(transcript_path),
        "project": project,
        "categories": sorted(all_keys),
        "timestamp": datetime.now().isoformat(),
    }

    try:
        # Open in a+ so the file is created if absent; flock gives us an
        # exclusive lock across processes so the duplicate-check + append
        # is atomic even when multiple Claude instances stop simultaneously.
        with open(pending_path, "a+", encoding="utf-8") as f:
            _flock_exclusive(f)
            try:
                f.seek(0)
                for raw_line in f:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        existing = json.loads(line)
                        # Match by session_id (new format) or transcript path stem (old format)
                        existing_id = (
                            existing.get("session_id")
                            or Path(existing.get("transcript_path", "")).stem
                        )
                        if existing_id == session_id:
                            return  # Already queued
                    except (json.JSONDecodeError, ValueError):
                        continue
                # Seek to end before appending (a+ mode keeps write position
                # at end on most platforms, but be explicit)
                f.seek(0, 2)
                f.write(json.dumps(entry) + "\n")
            finally:
                _funlock(f)
    except OSError:
        pass


def _launch_summarizer_if_pending() -> None:
    """Launch summarize_sessions.py as a detached background process if there are pending entries.

    Checks the pending summaries file for at least one non-empty line before
    spawning. The process is fully detached (new session, devnull stdio) so the
    hook exits immediately without waiting. CLAUDECODE is unset so the summarizer
    can invoke ``claude`` internally without hitting the nesting guard.

    Respects ``session_stop_hook.auto_summarize`` in config (default: ``true``).
    """
    if not vault_common.get_config("session_stop_hook", "auto_summarize", True):
        return

    pending_path = vault_common.VAULT_ROOT / "pending_summaries.jsonl"
    if not pending_path.exists():
        return

    try:
        with open(pending_path, "r", encoding="utf-8") as f:
            has_pending = any(line.strip() for line in f)
    except OSError:
        return

    if not has_pending:
        return

    summarizer = Path(__file__).parent / "summarize_sessions.py"
    if not summarizer.exists():
        return

    try:
        subprocess.Popen(
            ["uv", "run", "--no-project", str(summarizer)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=vault_common.env_without_claudecode(),
        )
    except (OSError, ValueError):
        pass


def main() -> None:
    """Entry point: read session JSON from stdin, analyze transcript, save learnings."""
    parser = argparse.ArgumentParser(
        description="Claude Code SessionEnd hook — captures learnings from the session transcript.",
    )
    parser.add_argument(
        "--ai",
        metavar="MODEL",
        nargs="?",
        const=_DEFAULT_AI_MODEL,
        default=None,
        help=(
            "Use the specified claude model to intelligently classify session content "
            f"(default model: {_DEFAULT_AI_MODEL}). Falls back to keyword heuristics on failure. "
            "Requires increasing the hook timeout in settings.json to >= 30000ms."
        ),
    )
    args = parser.parse_args()

    try:
        raw_stdin = sys.stdin.read()
        input_data: dict[str, object] = json.loads(raw_stdin)
    except (json.JSONDecodeError, ValueError):
        print("[session_stop_hook] ERROR: failed to parse stdin JSON", file=sys.stderr)
        sys.stdout.write("{}")
        return

    try:
        # Prevent recursive hook invocation
        if os.environ.get("CLAUDE_VAULT_STOP_ACTIVE"):
            print("[session_stop_hook] skipping: recursive invocation detected", file=sys.stderr)
            sys.stdout.write("{}")
            return
        os.environ["CLAUDE_VAULT_STOP_ACTIVE"] = "1"

        transcript_path_str = str(input_data.get("transcript_path", ""))
        cwd = str(input_data.get("cwd", ""))

        if not transcript_path_str:
            print("[session_stop_hook] skipping: no transcript_path in input", file=sys.stderr)
            sys.stdout.write("{}")
            return

        transcript_path = Path(transcript_path_str)
        if not transcript_path.is_file():
            print(f"[session_stop_hook] skipping: transcript not found: {transcript_path}", file=sys.stderr)
            sys.stdout.write("{}")
            return

        # Ensure vault directories exist
        vault_common.ensure_vault_dirs()

        project: str = vault_common.get_project_name(cwd) if cwd else "unknown"
        print(f"[session_stop_hook] project={project} transcript={transcript_path.name}", file=sys.stderr)

        # Read and parse the last 200 lines of the transcript
        raw_lines: list[str] = read_last_n_lines(transcript_path, 200)
        assistant_texts: list[str] = parse_transcript_lines(raw_lines)

        if not assistant_texts:
            print("[session_stop_hook] skipping: no assistant messages found in transcript tail", file=sys.stderr)
            sys.stdout.write("{}")
            return

        print(f"[session_stop_hook] parsed {len(assistant_texts)} assistant message(s)", file=sys.stderr)

        # Resolve AI model: CLI → config → None (disabled)
        ai_model: str | None = args.ai
        if ai_model is None:
            ai_model = vault_common.get_config("session_stop_hook", "ai_model")

        # --- AI classification path ---
        if ai_model:
            print(f"[session_stop_hook] classifying with AI model: {ai_model}", file=sys.stderr)
            ai_result = _classify_session_with_ai(assistant_texts, project, ai_model)
            if ai_result is not None:
                raw_cats = ai_result.get("categories") or []
                ai_categories: dict[str, list[str]] = {
                    str(cat): [] for cat in (raw_cats if isinstance(raw_cats, list) else [])
                }
                ai_summary = str(ai_result.get("summary", ""))
                should_queue = bool(ai_result.get("should_queue", False))
                cats_str = ", ".join(ai_categories.keys()) or "none"
                print(
                    f"[session_stop_hook] AI result: should_queue={should_queue} "
                    f"categories=[{cats_str}] summary={ai_summary[:100]!r}",
                    file=sys.stderr,
                )
                first_summary_ai: str = ai_summary or (
                    assistant_texts[0][:500] if assistant_texts else ""
                )
                append_session_to_daily(project, ai_categories, first_summary_ai)
                print("[session_stop_hook] daily note updated", file=sys.stderr)
                if should_queue and ai_categories:
                    append_to_pending(
                        transcript_path, project, ai_categories, force=True
                    )
                    print("[session_stop_hook] session queued for summarization", file=sys.stderr)
                else:
                    print("[session_stop_hook] session not queued (no significant categories or should_queue=false)", file=sys.stderr)
                vault_common.git_commit_vault(
                    f"chore(vault): session notes [{project}]"
                )
                _launch_summarizer_if_pending()
                sys.stdout.write("{}")
                return
            print("[session_stop_hook] AI classification failed, falling back to keyword heuristics", file=sys.stderr)
            # AI failed — fall through to keyword detection

        # --- Keyword heuristic path (default or AI fallback) ---
        categories: dict[str, list[str]] = detect_categories(assistant_texts)
        cats_str = ", ".join(categories.keys()) or "none"
        print(f"[session_stop_hook] keyword detection: categories=[{cats_str}]", file=sys.stderr)

        first_summary: str = ""
        for text in assistant_texts:
            if len(text.strip()) > 50:
                first_summary = text[:500]
                break
        if not first_summary and assistant_texts:
            first_summary = assistant_texts[0][:500]

        append_session_to_daily(project, categories, first_summary)
        print("[session_stop_hook] daily note updated", file=sys.stderr)
        append_to_pending(transcript_path, project, categories)
        significant = {"error_fix", "research", "pattern"}
        if significant & set(categories.keys()):
            print("[session_stop_hook] session queued for summarization", file=sys.stderr)
        else:
            print("[session_stop_hook] session not queued (no significant categories)", file=sys.stderr)
        vault_common.git_commit_vault(f"chore(vault): session notes [{project}]")
        _launch_summarizer_if_pending()

        sys.stdout.write("{}")

    except Exception:
        traceback.print_exc(file=sys.stderr)
        # On any error, output empty JSON and exit cleanly
        sys.stdout.write("{}")


if __name__ == "__main__":
    main()
