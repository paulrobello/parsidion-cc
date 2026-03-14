#!/usr/bin/env bash
# SessionEnd hook wrapper — reads stdin, acknowledges immediately, then runs
# the real session_stop_hook.py detached so Claude Code's exit sequence
# cannot cancel it before it completes.
#
# Claude Code fires SessionEnd and waits for the hook to output JSON and exit.
# If the hook is slow to start (e.g. uv startup overhead) Claude Code may
# cancel it during its own shutdown.  This wrapper solves that by:
#   1. Saving stdin to a temp file before outputting anything.
#   2. Writing {} to stdout immediately so Claude Code sees a clean exit.
#   3. Spawning the real Python hook in a detached background process.

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
REAL_HOOK="$SCRIPTS_DIR/session_stop_hook.py"

# Save stdin to a temp file (stdin closes once we output and exit)
TMPFILE=$(mktemp /tmp/session_stop_hook_XXXXXX.json)
cat > "$TMPFILE"

# Acknowledge to Claude Code immediately
printf '{}'

# Run the real hook detached — immune to SIGHUP and process-group exit
# stdout/stderr go to a log file for debugging; temp file is cleaned up after.
(
  unset CLAUDECODE
  nohup uv run --no-project "$REAL_HOOK" < "$TMPFILE" \
    >> /tmp/session_stop_hook.log 2>&1
  rm -f "$TMPFILE"
) &
