#!/usr/bin/env bash
# Run the parsidion-cc trigger eval from a SEPARATE terminal.
#
# Usage:
#   bash ~/.claude/skills/parsidion-cc/scripts/run_trigger_eval.sh
#
# Results written to:
#   ~/.claude/skills/parsidion-cc/eval_results.json
#
# After it finishes, go back to Claude Code and say:
#   "read the eval results"

set -euo pipefail
unset CLAUDECODE 2>/dev/null || true
exec python3 ~/.claude/skills/parsidion-cc/scripts/run_trigger_eval.py "$@"
