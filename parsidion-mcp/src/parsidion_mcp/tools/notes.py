"""vault_read and vault_write MCP tools."""

from pathlib import Path

import vault_common


def _resolve_vault_path(path: str) -> Path:
    """Resolve *path* against vault root; raise ValueError if it escapes.

    Args:
        path: Path string, relative to vault root or absolute.

    Returns:
        Resolved absolute Path inside vault root.

    Raises:
        ValueError: If the resolved path escapes the vault root.
    """
    vault_root = vault_common.VAULT_ROOT.resolve()
    raw = Path(path)
    candidate = (raw if raw.is_absolute() else vault_root / raw).resolve()
    if not candidate.is_relative_to(vault_root):
        raise ValueError("path escapes vault root")
    return candidate


def vault_read(path: str) -> str:
    """Read a vault note by path.

    Args:
        path: Path relative to vault root (e.g. ``Patterns/my-note.md``) or absolute.

    Returns:
        Full note content (frontmatter + body), or an ERROR string on failure.
    """
    vault_root = vault_common.VAULT_ROOT
    if not vault_root.exists():
        return f"ERROR: vault root not found at {vault_root}"
    try:
        resolved = _resolve_vault_path(path)
        return resolved.read_text(encoding="utf-8")
    except ValueError as exc:
        return f"ERROR: {exc}"
    except FileNotFoundError:
        return f"ERROR: note not found at {path}"
    except OSError as exc:
        return f"ERROR: {exc}"


def vault_write(path: str, content: str) -> str:
    """Create or overwrite a vault note.

    Args:
        path: Path relative to vault root.
        content: Full note content including YAML frontmatter.

    Returns:
        Success message with absolute path, or an ERROR string on failure.
    """
    try:
        resolved = _resolve_vault_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return f"Written: {resolved}"
    except ValueError as exc:
        return f"ERROR: {exc}"
    except OSError as exc:
        return f"ERROR: {exc}"
