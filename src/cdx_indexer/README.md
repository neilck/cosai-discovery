# cdx_indexer

The COSAI Discovery indexer. Walks a workspace of related projects, classifies each one with an LLM, and produces structured index files that an MCP server can embed and query.

## How it fits into the pipeline

```
cdx-index build          →   .cosai-indexes/<project>/    →   MCP server   →   AI agent
(this package)               manifest.json                    embeds &          queries
                             packages.jsonl                   queries
                             snippets.jsonl
                             references.jsonl
```

The indexer's job is to describe what exists. Chunking for vector retrieval is the MCP server's job. The indexer produces one entry per file (or one entry per YAML item for structured data); it does not split documents by heading.

---

## Configuration

All workspace layout is declared in `cdx-config.yaml` at the repo root. The CLI auto-discovers this file by walking up from the current directory.

```yaml
# cdx-config.yaml
workspace:
  root: ..                          # parent of all project dirs
  indexes_dir: .cosai-indexes       # where per-project JSONL files are written
  sidecar: true                     # write alongside indexes_dir, not in-project

data:
  checkpoints_db: .cdx/checkpoints.db   # LangGraph build cache (ephemeral)
  vectors_db: .cdx/vectors.db           # Voyage vector store (durable output)

models:
  default: claude-haiku-4-5        # Stage 1, 2a, 2b, 2c
  strong: claude-sonnet-4-6        # used when --model strong is passed

embed:
  enabled: false                   # set true to embed after every build
```

**Resolution order** (later wins):
1. Built-in code defaults
2. `cdx-config.yaml`
3. Environment variables (`CDX_MODEL`, `CDX_EMBED`, `VOYAGE_API_KEY`, `ANTHROPIC_API_KEY`)
4. CLI flags (`--model`, `--embed`, `--db-path`, etc.)

Secrets never go in the config file. Use `.env` or environment variables for `ANTHROPIC_API_KEY` and `VOYAGE_API_KEY`.

---

## Runtime data

```
cosai-discovery/
  .cdx/
    checkpoints.db    ← LangGraph checkpoint cache (build-time only; safe to delete)
    vectors.db        ← Voyage vector store (durable; delete only to force re-embed)
  .cosai-indexes/
    project-codeguard/
      manifest.json
      packages.jsonl
      snippets.jsonl
      references.jsonl
      _stage1.json    ← human-readable Stage 1 state for debugging
    secure-ai-tooling/
    ...
  cdx-config.yaml
```

`.cdx/` is gitignored. `.cosai-indexes/` is gitignored during development; production projects commit their index files directly to their own repos under `.cosai-index/`.

---

## CLI

```
cdx-index [--config PATH] COMMAND [OPTIONS]
```

`--config` overrides auto-discovery of `cdx-config.yaml`.

### `cdx-index build [PROJECT_PATH]`

Index one project. Runs all four stages in sequence.

```
cdx-index build                          # indexes the current directory
cdx-index build ../project-codeguard
cdx-index build --embed                  # also embed via Voyage after writing files
cdx-index build --force                  # ignore Stage 1 checkpoint; re-call LLM
cdx-index build --model strong           # use models.strong from config
cdx-index build -v                       # verbose: show LLM responses + embed trace
```

### `cdx-index status [WORKSPACE_PATH]`

Show per-project index and vector store state. Reads both DBs.

```
cdx-index status                         # all projects in workspace
cdx-index status --project codeguard-cli
cdx-index status --json                  # machine-readable
```

Output columns: `project`, `schema`, `last_indexed`, `stale`, entry counts (`M P S R`), `vec` (vector count), `chk` (checkpoint count), `in_sync`.

### `cdx-index drop PROJECT_SLUG`

Remove a project's vectors from `vectors.db`. Index files on disk are untouched.

```
cdx-index drop codeguard-cli
cdx-index drop codeguard-cli --dry-run
```

### `cdx-index reset [PROJECT_SLUG]`

Delete LangGraph checkpoints for one project (or all). Forces fresh LLM calls on next build. Does not touch index files or vectors.

```
cdx-index reset codeguard-cli            # one project's checkpoints
cdx-index reset --all                    # wipe checkpoints.db entirely
cdx-index reset codeguard-cli --dry-run
```

### `cdx-index purge [PROJECT_SLUG]`

Remove index files from `.cosai-indexes/`. Does not touch checkpoints or vectors.

```
cdx-index purge codeguard-cli            # one project's JSONL files
cdx-index purge --all                    # all projects
cdx-index purge codeguard-cli --dry-run
```

---

## Build pipeline

Each `cdx-index build` run executes five stages in order.

### Stage 0 — Scan (`scan.py`)

Deterministic. No LLM. Walks the project directory and collects:
- File tree (counts, notable paths)
- Manifest files: `pyproject.toml`, `package.json`, `go.mod`, `Cargo.toml`, `claude-plugin`, `devcontainer-feature.json`
- README content
- Git metadata (default branch, last commit)
- Workspace peer project slugs

Output: `ProjectScan` dataclass. Input to Stage 1.

### Stage 1 — Plan (`planner.py`)

LLM call (Claude). Given the `ProjectScan`, produces:
- Manifest fields: `description`, `primary_kind`, `also`, `status`, `owners`, `tags`, `languages`, `license`, `related_urls`
- Entry plan: which files Stages 2a/2b/2c should process

Implemented as a LangGraph graph with a single node. Checkpointed to `checkpoints.db` by thread ID `<project>@<content_hash[:8]>`. Re-runs reuse the cached output unless `--force` is passed or the checkpoint is reset.

Prompt files: `prompts/stage1_system.md`, `prompts/stage1_user.md.tmpl`.

### Stage 2a — Packages (`packages.py`)

One LLM call per package manifest the planner identified. Produces `packages.jsonl`.

Each entry: `id`, `name`, `language`, `ecosystem`, `version`, `entrypoints`, `public_api`, `path`, `install`, `summary`, `tags`, `content_hash`.

Embedded fields (sent to Voyage): `summary` + `install` → `voyage-code-3`.

Prompt files: `prompts/stage2a_system.md`, `prompts/stage2a_user.md.tmpl`.

### Stage 2b — Snippets (`snippets.py`)

One LLM call per snippet file the planner identified. Produces `snippets.jsonl`.

Each entry: `id`, `kind`, `title`, `path`, `language`, `summary`, `tags`, `depends_on`, `content_hash`.

Embedded fields: `title` + `summary` → `voyage-code-3`.

Prompt files: `prompts/stage2b_system.md`, `prompts/stage2b_user.md.tmpl`.

### Stage 2c — References (`references.py`)

One LLM call per reference file (or per YAML item for structured data). Produces `references.jsonl`.

Each entry: `id`, `kind`, `title`, `doc`, `path`, `form`, `summary`, `tags`, `content_hash`, `structure_description` (when non-prose).

YAML decomposition: files with a list of dicts each having an `id` field produce one entry per item. Multiple list-of-items keys in one file are merged.

Embedded fields: `title` + `summary` + `structure_description` → `voyage-3`.

Prompt files: `prompts/stage2c_system.md`, `prompts/stage2c_user.md.tmpl`.

### Stage 3 — Embed (`embed.py`)

Runs only when `--embed` is passed or `embed.enabled: true` in config. Requires `VOYAGE_API_KEY`.

Reads the JSONL files just written, diffs against `vectors.db` by `content_hash`, calls Voyage only for new or changed entries, upserts vectors, deletes stale rows.

Two Voyage models:
- `voyage-3` — manifest description, reference entries
- `voyage-code-3` — package entries, snippet entries

Vector store: SQLite + sqlite-vec at `.cdx/vectors.db`. One 1024-dim vector per entry. KNN search via `vec0` virtual table.

---

## Checkpointing and caching

**Two independent caches:**

| Cache | File | What it stores | When to clear |
|---|---|---|---|
| LangGraph checkpoints | `.cdx/checkpoints.db` | Claude API responses, keyed by `<project>:<kind>:<slug>@<hash[:8]>` | When a prompt file changes; `cdx-index reset` |
| Voyage vectors | `.cdx/vectors.db` | Embedding vectors, keyed by `(project, kind, entry_id)` + `content_hash` | When entry content changes (auto-diffed); `cdx-index drop` |

Re-running `cdx-index build` without changes: Stage 1 hits the checkpoint cache (no Claude call); Stage 3 hits the vector cache (no Voyage call). Incremental by design.

---

## Module reference

| Module | Responsibility |
|---|---|
| `cli.py` | Click command group: `build`, `status`, `drop`, `reset`, `purge` |
| `config.py` | Load `cdx-config.yaml`; resolve paths; merge env vars; `CdxConfig` dataclass |
| `scan.py` | Stage 0: deterministic project scan → `ProjectScan` |
| `manifest.py` | Build the `Manifest` skeleton from scan facts |
| `planner.py` | Stage 1: LLM classification + entry plan via LangGraph |
| `packages.py` | Stage 2a: per-package LLM summarisation |
| `snippets.py` | Stage 2b: per-snippet LLM summarisation |
| `references.py` | Stage 2c: per-reference LLM summarisation; YAML decomposition |
| `embed.py` | Stage 3: Voyage embedding orchestration; hash-diff; batch retry |
| `vectorstore.py` | SQLite + sqlite-vec wrapper: upsert, search, drop, status |
| `writer.py` | Atomic JSONL/JSON writers; sidecar path resolution |
| `types.py` | `Manifest`, `Package`, `Snippet`, `Reference` dataclasses |
| `prompts/` | System + user prompt templates for each LLM stage |

---

## Development scripts

Scripts in `_scripts/` are thin wrappers around CLI commands. They exist only to loop over multiple projects or chain commands; all logic lives in the CLI.

| Script | Purpose |
|---|---|
| `test-build.sh [project\|--all]` | Run `cdx-index build` for one or all projects |
| `test-embed.sh [project]` | Build → embed → verify status → drop → verify status |

**Common workflows:**

```bash
# Iterate after changing a prompt
cdx-index reset codeguard-cli
cdx-index build codeguard-cli -v

# Full clean rebuild of one project
cdx-index reset codeguard-cli
cdx-index purge codeguard-cli
cdx-index drop codeguard-cli
cdx-index build codeguard-cli --embed

# Build and embed all projects
CDX_EMBED=true ./_scripts/test-build.sh --all

# Check workspace state
cdx-index status
```

---

## Output format

Defined in `_docs/index-file-format-0.1.0.md`. Each JSONL file has one JSON object per line. Fields are tagged `embed` (sent to Voyage), `filter` (hard filter in vector queries), or `store` (returned after retrieval, not embedded).

Key spec rules:
- One entry per file for references (no heading-level splits — that's the MCP server's job)
- One entry per YAML item when the file decomposes (items must have an `id` field)
- `content_hash` is `sha256:` over the inputs that produced the entry's embedded fields
- Empty corpora are zero-line files, not missing files
