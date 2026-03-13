#!/usr/bin/env bash
# Run the claude-vault trigger eval from a SEPARATE terminal.
#
# Usage:
#   bash ~/.claude/skills/claude-vault/scripts/run_trigger_eval.sh
#
# Results written to:
#   ~/.claude/skills/claude-vault/eval_results.json
#
# After it finishes, go back to Claude Code and say:
#   "read the eval results"

set -euo pipefail
unset CLAUDECODE 2>/dev/null || true
exec python3 ~/.claude/skills/claude-vault/scripts/run_trigger_eval.py "$@"
