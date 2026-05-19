#!/usr/bin/env bash
#
# Clear the generated .cosai-indexes/ directory so the next build starts fresh.
#
# Usage:
#   _scripts/clear-indexes.sh              # clear all generated indexes
#   _scripts/clear-indexes.sh <project>    # clear one project's index
#
# Does NOT clear the LangGraph checkpoint database. Use clear-checkpoints.sh
# for that — clearing indexes alone keeps cached LLM responses, so a re-build
# will be fast but use the same Stage 1 / Stage 2a outputs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

INDEXES_DIR="$REPO_ROOT/.cosai-indexes"

if [ ! -d "$INDEXES_DIR" ]; then
  echo "No indexes directory at $INDEXES_DIR"
  exit 0
fi

if [ "$#" -eq 0 ]; then
  rm -rf "$INDEXES_DIR"
  echo "Cleared: $INDEXES_DIR"
else
  for project in "$@"; do
    target="$INDEXES_DIR/$project"
    if [ -d "$target" ]; then
      rm -rf "$target"
      echo "Cleared: $target"
    else
      echo "Not found: $target" >&2
    fi
  done
fi
