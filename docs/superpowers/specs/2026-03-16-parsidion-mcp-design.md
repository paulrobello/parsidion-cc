# parsidion-mcp Design Spec

**Date:** 2026-03-16
**Status:** Approved

## Overview

`parsidion-mcp` is a FastMCP-based MCP server that exposes the Claude Vault knowledge management system to Claude Desktop (and any other MCP-capable client). It lives at `parsidion-cc/parsidion-mcp/` as an independent Python package.

## Package Structure

```
parsidion-cc/
└── parsidion-mcp/
    ├── pyproject.toml
    └── src/
        └── parsidion_mcp/
            ├── __init__.py
            ├── server.py        # FastMCP app + entry point
            └── tools/
                ├── __init__.py
                ├── search.py    # vault_search tool
                ├── notes.py     # vault_read, vault_write
                ├── context.py   # vault_context
                └── ops.py       # rebuild_index, vault_doctor
```

### Dependencies (`pyproject.toml`)

```toml
[project]
name = "parsidion-mcp"
requires-python = ">=3.13"
dependencies = [
    "fastmcp>=2.0",
    "parsidion-cc[search]",
]

[tool.uv.sources]
parsidion-cc = { path = "../", editable = true }

[project.scripts]
parsidion-mcp = "parsidion_mcp.server:main"
```

## Tools

### `vault_search`

Searches vault notes using semantic (vector) or metadata (filter) mode.

**Parameters:**
- `query: str | None` — natural language query (enables semantic mode)
- `tag: str | None` — filter by tag
- `folder: str | None` — filter by folder name
- `note_type: str | None` — filter by note type
- `project: str | None` — filter by project
- `recent_days: int | None` — only notes modified within N days
- `top_k: int = 10` — max results
- `min_score: float = 0.35` — minimum cosine similarity (semantic mode only)

**Behavior:** Semantic mode when `query` is provided; metadata mode otherwise. Mirrors `vault_search.py` exactly. Returns JSON array of note objects with `path`, `title`, `tags`, `score`.

### `vault_read`

Reads a vault note by path.

**Parameters:**
- `path: str` — path relative to vault root (e.g. `Patterns/my-note.md`) or absolute

**Returns:** Full note content (frontmatter + body) as a string.

**Safety:** Resolves path against `vault_common.VAULT_ROOT`; rejects any path that escapes the vault root.

### `vault_write`

Creates or overwrites a vault note.

**Parameters:**
- `path: str` — path relative to vault root
- `content: str` — full note content including YAML frontmatter

**Returns:** Success confirmation with resolved absolute path.

**Safety:** Same path containment check as `vault_read`.

### `vault_context`

Returns vault context in the same format as `session_start_hook` — compact one-line-per-note index by default, full summaries when `verbose=True`.

**Parameters:**
- `project: str | None` — project name to filter context for
- `recent_days: int = 3` — recency window for recent notes
- `verbose: bool = False` — full note summaries vs compact index

**Returns:** Context string ready for injection into a system prompt.

### `rebuild_index`

Rebuilds the vault index (`CLAUDE.md`, per-folder `MANIFEST.md` files, and `note_index` table in `embeddings.db`).

**Parameters:** None.

**Returns:** Script output (stdout + stderr). Timeout: 30s.

### `vault_doctor`

Scans vault notes for structural issues; optionally repairs them via Claude haiku.

**Parameters:**
- `fix: bool = False` — if False, scan and report only; if True, repair repairable issues
- `errors_only: bool = False` — only report errors, skip warnings
- `limit: int | None = None` — max notes to repair (only relevant when `fix=True`)

**Returns:** Scan/repair report. Timeout: 120s.

## Architecture

### Importing vault_common / vault_search

The `parsidion-cc[search]` path dependency makes `vault_common` and `vault_search` directly importable — no `sys.path` manipulation needed in the MCP server.

### Finding scripts for subprocess calls

```python
import vault_common
SCRIPTS_DIR = vault_common.TEMPLATES_DIR.parent / "scripts"
```

This derives the installed scripts path (`~/.claude/skills/parsidion-cc/scripts/`) from the already-imported `vault_common` module, without hardcoding.

### Subprocess calls

`rebuild_index` and `vault_doctor` invoke the existing scripts via subprocess:

```python
subprocess.run(
    ["uv", "run", "--no-project", str(SCRIPTS_DIR / "update_index.py")],
    capture_output=True, text=True, timeout=30,
)
```

```python
subprocess.run(
    ["uv", "run", "--no-project", str(SCRIPTS_DIR / "vault_doctor.py"), *flags],
    capture_output=True, text=True, timeout=120,
)
```

No `env -u CLAUDECODE` needed — Claude Desktop does not set that environment variable.

### Server entry point

```python
from fastmcp import FastMCP

mcp = FastMCP("parsidion-mcp")
# tools registered via imports

def main() -> None:
    mcp.run()
```

Transport: stdio (FastMCP default, required by Claude Desktop).

## Error Handling

Every tool returns a plain string. On failure:
```
ERROR: <message>
```
On success: the result content.

- Subprocess non-zero exit → stderr returned as error message
- Path escape attempt → `ERROR: path escapes vault root`
- Missing vault → `ERROR: vault root not found at <path>`
- Missing embeddings DB (semantic search) → `ERROR: embeddings DB not found — run rebuild_index first`

No exceptions propagate to the MCP transport layer.

## Testing

Location: `parsidion-mcp/tests/`

- **Unit tests** — each tool module tested with mocked `vault_common`, `vault_search`, and `subprocess.run`
- **Subprocess tests** — `rebuild_index` and `vault_doctor` tested with `unittest.mock.patch("subprocess.run")`
- **Integration smoke test** — reads one real note; skipped via `pytest.mark.skipif` when vault is absent

Tools: `pytest`, `ruff`, `pyright` (same stack as core package).

## Installation

```bash
cd parsidion-cc/parsidion-mcp/
uv tool install --editable .
```

## Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "parsidion": {
      "command": "parsidion-mcp"
    }
  }
}
```
