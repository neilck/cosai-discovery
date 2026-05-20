#!/usr/bin/env bash
#
# Test the chat application with predefined queries.
#
# Usage:
#   _scripts/test-chat.sh project-codeguard

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -x "$REPO_ROOT/.venv/bin/cdx-index" ]; then
  CDX="$REPO_ROOT/.venv/bin/cdx-index"
elif command -v cdx-index >/dev/null 2>&1; then
  CDX="$(command -v cdx-index)"
else
  echo "Error: cdx-index not found. Run 'pip install -e .' from $REPO_ROOT first." >&2
  exit 1
fi

target="${1:-}"

if [ -z "$target" ]; then
  echo "Usage: $0 <project-slug>"
  echo "Example: $0 project-codeguard"
  exit 1
fi

# Start chat and pipe in test questions
{
  echo "What is this project about?"
  echo "What are the main security rules?"
  echo "How do I use this project?"
  echo "quit"
} | "$CDX" chat "$target"
