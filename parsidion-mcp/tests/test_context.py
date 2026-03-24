"""Tests for vault_context tool."""

from pathlib import Path
from unittest.mock import patch

from parsidion_mcp.tools.context import vault_context


# ---------------------------------------------------------------------------
# vault_context
# ---------------------------------------------------------------------------


def test_vault_context_with_project(tmp_path: Path) -> None:
    note = tmp_path / "proj.md"
    note.write_text("---\ntags: []\n---\n# Proj\n", encoding="utf-8")

    with patch("parsidion_mcp.tools.context.vault_common") as mock_vc:
        mock_vc.VAULT_ROOT = tmp_path
        mock_vc.find_notes_by_project.return_value = [note]
        mock_vc.find_recent_notes.return_value = []
        mock_vc.build_compact_index.return_value = "COMPACT INDEX"

        vault_context(project="myproject", recent_days=3)

    mock_vc.find_notes_by_project.assert_called_once_with("myproject")
    mock_vc.find_recent_notes.assert_called_once_with(3)
    mock_vc.build_compact_index.assert_called_once()


def test_vault_context_deduplicates_notes(tmp_path: Path) -> None:
    note = tmp_path / "dup.md"
    note.write_text("---\ntags: []\n---\n# Dup\n", encoding="utf-8")

    with patch("parsidion_mcp.tools.context.vault_common") as mock_vc:
        mock_vc.VAULT_ROOT = tmp_path
        mock_vc.find_notes_by_project.return_value = [note]
        mock_vc.find_recent_notes.return_value = [note]  # same note
        mock_vc.build_compact_index.return_value = "INDEX"

        vault_context(project="x")

    # Deduplicated list passed to build_compact_index
    args = mock_vc.build_compact_index.call_args[0]
    assert len(args[0]) == 1  # only one note, not two


def test_vault_context_verbose_calls_build_context_block(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text("---\ntags: []\n---\n# Note\n", encoding="utf-8")

    with patch("parsidion_mcp.tools.context.vault_common") as mock_vc:
        mock_vc.VAULT_ROOT = tmp_path
        mock_vc.find_notes_by_project.return_value = []
        mock_vc.find_recent_notes.return_value = [note]
        mock_vc.build_context_block.return_value = "VERBOSE CONTEXT"

        result = vault_context(verbose=True)

    assert result == "VERBOSE CONTEXT"
    mock_vc.build_context_block.assert_called_once()


def test_vault_context_no_notes_returns_message() -> None:
    with patch("parsidion_mcp.tools.context.vault_common") as mock_vc:
        mock_vc.find_recent_notes.return_value = []
        result = vault_context()

    assert "No relevant" in result
