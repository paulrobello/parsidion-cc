"""rebuild_index and vault_doctor MCP tools."""

import subprocess
from pathlib import Path

import vault_common

# TEMPLATES_DIR is always <skill_root>/templates/.
# Scripts are one level up: <skill_root>/scripts/.
# This invariant holds because the installer only patches VAULT_ROOT and
# TEMPLATES_DIR always points into ~/.claude/skills/parsidion-cc/.
SCRIPTS_DIR: Path = vault_common.TEMPLATES_DIR.parent / "scripts"


def rebuild_index() -> str:
    """Rebuild the vault index (CLAUDE.md, MANIFEST.md files, note_index table).

    Returns:
        Script output on success, or an ERROR string on failure.
    """
    script = SCRIPTS_DIR / "update_index.py"
    try:
        result = subprocess.run(
            ["uv", "run", "--no-project", str(script)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = (result.stdout + result.stderr).strip()
        if result.returncode != 0:
            return f"ERROR: {output}"
        return output or "Index rebuilt successfully."
    except subprocess.TimeoutExpired:
        return "ERROR: command timed out after 30s"
    except (FileNotFoundError, OSError) as exc:
        return f"ERROR: {exc}"


def vault_doctor(
    fix: bool = False,
    errors_only: bool = False,
    limit: int | None = None,
) -> str:
    """Scan vault notes for structural issues; optionally repair them.

    Args:
        fix: When True, repair repairable issues via Claude haiku.
             When False, scan and report only (--fix flag is omitted).
        errors_only: When True, skip warnings and report errors only.
        limit: Maximum number of notes to repair (only relevant when fix=True).

    Returns:
        Scan/repair report, or an ERROR string on failure.
    """
    script = SCRIPTS_DIR / "vault_doctor.py"
    args: list[str] = ["uv", "run", "--no-project", str(script)]
    if fix:
        args.append("--fix")
    if errors_only:
        args.append("--errors-only")
    if limit is not None:
        args.extend(["--limit", str(limit)])

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = (result.stdout + result.stderr).strip()
        if result.returncode != 0:
            return f"ERROR: {output}"
        return output or "Doctor scan complete."
    except subprocess.TimeoutExpired:
        return "ERROR: command timed out after 120s"
    except (FileNotFoundError, OSError) as exc:
        return f"ERROR: {exc}"
