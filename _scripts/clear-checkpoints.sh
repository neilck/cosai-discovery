#!/usr/bin/env bash
#
# Clear the LangGraph checkpoint database, forcing the next `cdx-index build`
# to make fresh LLM calls (no cached Stage 1 / Stage 2a results).
#
# Usage:
#   _scripts/clear-checkpoints.sh
#
# When to use:
#   - After editing a prompt file (so cached LLM responses get regenerated).
#   - When verifying changes to the schema (e.g. new fields in Package).
#   - When debugging LLM output and you want a clean run.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DB="$REPO_ROOT/.data/checkpoints.db"

if [ -f "$DB" ]; then
  rm -f "$DB" "$DB-journal" "$DB-shm" "$DB-wal"
  echo "Cleared: $DB"
else
  echo "No checkpoint database found at $DB"
fi

# Also clean up the stray DB if it was created by running from _scripts/.
STRAY_DB="$SCRIPT_DIR/.data/checkpoints.db"
if [ -f "$STRAY_DB" ]; then
  rm -f "$STRAY_DB" "$STRAY_DB-journal" "$STRAY_DB-shm" "$STRAY_DB-wal"
  echo "Also cleared stray DB: $STRAY_DB"
fi
