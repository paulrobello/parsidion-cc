"""ARC-003: Assert that install.py extracts VAULT_DIRS from vault_common.py at runtime.

After the ARC-003 fix, install.py no longer maintains a separate copy of
VAULT_DIRS.  Instead it parses vault_common.py source text via regex.  This
test verifies that the extracted list matches the canonical constant.
"""

import install
import vault_common


class TestVaultDirsSync:
    """Ensure VAULT_DIRS is identical in vault_common.py and install.py."""

    def test_vault_dirs_identical(self) -> None:
        """VAULT_DIRS in vault_common and install must be the same set."""
        assert set(vault_common.VAULT_DIRS) == set(install.VAULT_DIRS), (
            "VAULT_DIRS mismatch!\n"
            f"  vault_common: {sorted(vault_common.VAULT_DIRS)}\n"
            f"  install.py:   {sorted(install.VAULT_DIRS)}\n"
            "install.py should extract VAULT_DIRS from vault_common.py source."
        )

    def test_vault_dirs_same_length(self) -> None:
        """VAULT_DIRS in vault_common and install must have the same length (no duplicates)."""
        assert len(vault_common.VAULT_DIRS) == len(install.VAULT_DIRS), (
            f"VAULT_DIRS length mismatch: "
            f"vault_common has {len(vault_common.VAULT_DIRS)} entries, "
            f"install.py has {len(install.VAULT_DIRS)} entries."
        )

    def test_vault_dirs_preserves_order(self) -> None:
        """VAULT_DIRS extracted by install.py should preserve the order from vault_common.py."""
        assert vault_common.VAULT_DIRS == install.VAULT_DIRS, (
            "VAULT_DIRS order mismatch!\n"
            f"  vault_common: {vault_common.VAULT_DIRS}\n"
            f"  install.py:   {install.VAULT_DIRS}"
        )
