"""vault_read and vault_write MCP tools."""

from pathlib import Path

import vault_common


class VaultToolError(Exception):
    """Raised when a vault MCP tool encounters an error."""


def _resolve_vault_path(path: str) -> Path:
    """Resolve *path* against vault root; raise VaultToolError if it escapes.

    Args:
        path: Path string, relative to vault root or absolute.

    Returns:
        Resolved absolute Path inside vault root.

    Raises:
        VaultToolError: If the resolved path escapes the vault root.
    """
    # ARC-004: Use resolve_vault() instead of the module-level VAULT_ROOT
    # constant so that CLAUDE_VAULT env var, project-local vault files,
    # and named vaults are all respected.
    vault_root = vault_common.resolve_vault().resolve()
    raw = Path(path)
    candidate = (raw if raw.is_absolute() else vault_root / raw).resolve()
    if not candidate.is_relative_to(vault_root):
        raise VaultToolError("path escapes vault root")
    return candidate


def vault_read(path: str) -> str:
    """Read a vault note by path.

    Args:
        path: Path relative to vault root (e.g. ``Patterns/my-note.md``) or absolute.

    Returns:
        Full note content (frontmatter + body).

    Raises:
        VaultToolError: On any read failure (missing vault, path escape,
            file not found, OS error).
    """
    vault_root = vault_common.resolve_vault()
    if not vault_root.exists():
        raise VaultToolError(f"vault root not found at {vault_root}")
    try:
        resolved = _resolve_vault_path(path)
        return resolved.read_text(encoding="utf-8")
    except VaultToolError:
        raise
    except FileNotFoundError:
        raise VaultToolError(f"note not found at {path}")
    except OSError as exc:
        raise VaultToolError(str(exc)) from exc


_MAX_CONTENT_BYTES: int = 10 * 1024 * 1024  # 10 MB


def vault_write(path: str, content: str) -> str:
    """Create or overwrite a vault note.

    Args:
        path: Path relative to vault root.
        content: Full note content including YAML frontmatter.

    Returns:
        Success message with absolute path.

    Raises:
        VaultToolError: On any write failure (path escape, OS error, oversized
            content, or non-.md extension).
    """
    try:
        # SEC-006: Reject oversized content before writing.
        if len(content.encode("utf-8")) > _MAX_CONTENT_BYTES:
            raise VaultToolError("Content exceeds 10 MB limit")
        resolved = _resolve_vault_path(path)
        # SEC-009: Only allow .md file extensions.
        if resolved.suffix.lower() != ".md":
            raise VaultToolError("Only .md files are allowed")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return f"Written: {resolved}"
    except VaultToolError:
        raise
    except OSError as exc:
        raise VaultToolError(str(exc)) from exc
