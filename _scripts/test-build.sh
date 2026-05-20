#!/usr/bin/env bash
#
# Run `cdx-index build` against one or all walked CoSAI projects, with the
# workspace-root pre-set and the venv activated.
#
# Usage:
#   _scripts/test-build.sh codeguard-cli                # one project
#   _scripts/test-build.sh codeguard-cli -v             # extra flags pass through
#   _scripts/test-build.sh codeguard-cli --no-llm
#   _scripts/test-build.sh --all                        # run against all 10
#   _scripts/test-build.sh --all --no-llm               # all, no LLM calls
#
# Optional environment variables:
#   CDX_EMBED=1    appends --embed to every invocation (Phase 6).
#                  Requires VOYAGE_API_KEY in env or .env.
#   CDX_MODEL=...  overrides Stage 1+ model (e.g. claude-sonnet-4-6).
#
# Output for each project goes to:
#   <repo>/.cosai-indexes/<project>/
# Vector store (when --embed is on) lives at:
#   <repo>/.cosai-indexes/.data/index.db
#
# Re-run after editing prompt or code; existing output is overwritten.

set -euo pipefail

# Resolve repo root regardless of where the script is invoked from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE_ROOT="$(cd "$REPO_ROOT/.." && pwd)"

# Projects walked during the design phase, in queue order.
ALL_PROJECTS=(
  project-codeguard
  codeguard-cli
  secure-ai-tooling
  ws2-defenders
  ws1-supply-chain
  ws3-ai-risk-governance
  ws4-secure-design-agentic-systems
  cosai-tsc
  cosai-whitepaper-converter
  oasis-open-project
)

if [ "$#" -eq 0 ]; then
  echo "Usage:"
  echo "  $0 <project-slug> [extra flags]"
  echo "  $0 --all [extra flags]"
  echo ""
  echo "Known projects:"
  for p in "${ALL_PROJECTS[@]}"; do
    echo "  - $p"
  done
  exit 1
fi

# Resolve the cdx-index binary. Prefer the project's venv; fall back to PATH.
if [ -x "$REPO_ROOT/.venv/bin/cdx-index" ]; then
  CDX="$REPO_ROOT/.venv/bin/cdx-index"
elif command -v cdx-index >/dev/null 2>&1; then
  CDX="$(command -v cdx-index)"
else
  echo "Error: cdx-index not found. Run 'pip install -e .' from $REPO_ROOT first." >&2
  exit 1
fi

# Pull arguments.
target="$1"
shift
extra_args=("$@")

run_one() {
  local project="$1"
  local project_path="$WORKSPACE_ROOT/$project"

  if [ ! -d "$project_path" ]; then
    echo "Error: project not found at $project_path" >&2
    return 1
  fi

  echo "============================================================"
  echo "$project"
  echo "============================================================"

  local embed_flag=()
  if [ "${CDX_EMBED:-0}" = "1" ]; then
    embed_flag=(--embed)
  fi

  local rc=0
  "$CDX" build "$project_path" \
    --sidecar \
    --workspace-root "$REPO_ROOT" \
    ${embed_flag[@]+"${embed_flag[@]}"} \
    ${extra_args[@]+"${extra_args[@]}"} || rc=$?
  echo ""
  return "$rc"
}

if [ "$target" = "--all" ]; then
  failed=()
  for project in "${ALL_PROJECTS[@]}"; do
    if ! run_one "$project"; then
      failed+=("$project")
      echo "(continuing after failure on $project)" >&2
    fi
  done
  echo ""
  echo "============================================================"
  if [ "${#failed[@]}" -eq 0 ]; then
    echo "All ${#ALL_PROJECTS[@]} projects completed."
  else
    echo "Completed with ${#failed[@]} failure(s):"
    for p in "${failed[@]}"; do
      echo "  - $p"
    done
    echo "Re-run with: ./_scripts/test-build.sh <project>"
    exit 1
  fi
else
  run_one "$target"
fi
