#!/usr/bin/env bash
#
# Smoke test for the Phase 6 embed pipeline.
#
# 1. Build project-codeguard with --embed.
# 2. Run `cdx-index status` and confirm in_sync.
# 3. Re-run --embed; confirm 0 new embeddings (everything cached).
# 4. Drop the project; confirm vector count drops to 0; status drops to no.
#
# Requires VOYAGE_API_KEY (in .env or env). Run after a successful build of
# project-codeguard (or any other project) — embedding uses the JSONLs that
# build already wrote.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PROJECT="${1:-project-codeguard}"

if [ -x "$REPO_ROOT/.venv/bin/cdx-index" ]; then
  CDX="$REPO_ROOT/.venv/bin/cdx-index"
else
  CDX="$(command -v cdx-index)"
fi

cd "$REPO_ROOT"

echo "=== Step 1: build --embed for $PROJECT ==="
CDX_EMBED=1 "$SCRIPT_DIR/test-build.sh" "$PROJECT"

echo ""
echo "=== Step 2: status (expect in_sync=yes for $PROJECT) ==="
"$CDX" status --project "$PROJECT"

echo ""
echo "=== Step 3: re-embed (expect cached >0, embedded=0) ==="
CDX_EMBED=1 "$SCRIPT_DIR/test-build.sh" "$PROJECT" 2>&1 | grep -E "embedded:|cached:"

echo ""
echo "=== Step 4: drop --dry-run, then drop ==="
"$CDX" drop "$PROJECT" --dry-run
"$CDX" drop "$PROJECT"

echo ""
echo "=== Step 5: status after drop (expect in_sync=no, vec=0) ==="
"$CDX" status --project "$PROJECT"

echo ""
echo "=== Done ==="
