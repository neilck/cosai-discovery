# Indexer Build Plan

Working planning doc for the CLI indexer that produces per-project `.cosai-index/` files from the [index-file-format-0.1.0.md](index-file-format-0.1.0.md) spec.

Not a spec. A working planning doc — the decisions made, the build order, what each phase produces. Updated as the implementation progresses.

## What we're building

`cdx-index` — a CLI tool that:

1. Scans a project directory.
2. Produces the four files in `.cosai-index/`: `manifest.json`, `packages.jsonl`, `snippets.jsonl`, `references.jsonl`.
3. Writes those files either in-repo (when writable) or to a sidecar location.
4. Optionally embeds entries and upserts them to a local vector store.

**The CLI is the *indexer*.** The MCP server that queries the indexed data is a separate piece, built after.

Reference implementation to learn from: [codeguard-cli](../../codeguard-cli/). Same general shape — Python click-based CLI, multi-provider LLM dispatch, file-hash skip pattern, cached versioned content, JSON output schema.

## Architecture

```
cosai-discovery/
  src/
    cdx_indexer/
      __init__.py
      cli.py                     # click entry point
      commands/
        build.py                 # build_index for one project
        scan.py                  # workspace-wide
        status.py                # index_status
        drop.py                  # drop_project
      manifest.py                # manifest discovery
      discovery/
        packages.py              # nested-manifest rule
        snippets.py              # examples/, docstrings, markers
        references.py            # markdown chunking, YAML decomposition
      summarize.py               # LLM call per entry; deterministic fallback
      embed.py                   # Voyage embedding wrapper
      vectorstore.py             # SQLite + sqlite-vec abstraction
      hashing.py                 # content_hash logic
      ignore.py                  # baseline + project-declared ignore
      config.py                  # .cdx-config.yaml loading
      writer.py                  # atomic JSONL/JSON writers, sidecar resolution
      types.py                   # dataclasses
    pyproject.toml               # console script: cdx-index = "cdx_indexer.cli:cli"
```

Mirrors codeguard-cli's layout. Small enough to keep in a single Python package.

## Decisions locked in

| Decision | Choice | Reason |
|---|---|---|
| Language | Python | Parity with codeguard-cli; Voyage + Anthropic SDKs are strongest in Python |
| Python version | 3.12+ | Newer baseline than codeguard-cli; modern tooling |
| Package layout | `src/cdx_indexer/` | Supports `pip install -e .` and clean import paths |
| CLI framework | click | codeguard-cli uses it; familiar |
| LLM for summaries | Anthropic Haiku, with `--no-llm` deterministic fallback | Cost-sensitive; deterministic mode allows iteration without API calls |
| Embedding provider | Voyage (`voyage-3` + `voyage-code-3`) | Per spec |
| Vector store | SQLite + sqlite-vec | Local-first, single file, no daemon |
| Auth / config | env vars for API keys, `.cdx-config.yaml` for everything else | Env: `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY` |
| Distribution | Install from source (`pip install -e .`) | Per codeguard-cli's pattern; PyPI later if needed |
| Streaming output | Deferred | Files only for now; `--stdout` and pipe semantics can be added later if a real need emerges |
| Testing approach | Eyeball against `_expected/*.md` | No validator script yet; revisit if/when reference-entry volume exceeds eyeballing |

## CLI surface

### `cdx-index build`

The primary command. Indexes one project.

```
cdx-index build [PROJECT_PATH] [OPTIONS]

Arguments:
  PROJECT_PATH                   The project to index. Defaults to cwd.

Options:
  --output PATH                  Where to write the four index files.
                                 Defaults to PROJECT_PATH/.cosai-index/ if writable,
                                 else <workspace-root>/.cosai-indexes/<slug>/.
  --sidecar                      Force sidecar location even when project is writable.
  --workspace-root PATH          Override inferred workspace root.
                                 Default: dirname(PROJECT_PATH).
  --kinds K1,K2,...              Which corpora to (re)build.
                                 Choices: manifest, packages, snippets, references.
                                 Default: all.
  --force                        Ignore content_hash; re-process all entries.
  --no-llm                       Skip LLM-generated summaries; use deterministic fallback.
  --no-embed                     Skip embedding and vector-store upsert.
  --dry-run                      Plan but don't write files or call APIs.
```

### Default output location resolution

When `--output` is omitted:

1. Try `PROJECT_PATH/.cosai-index/`. Use if writable (i.e. creating the directory succeeds).
2. If (1) fails or `--sidecar` is set, use `<workspace-root>/.cosai-indexes/<project-slug>/`.

Where:
- `<workspace-root>` is `dirname(PROJECT_PATH)` by default; overridable via `--workspace-root`.
- `<project-slug>` is the project's directory basename.

When `--output PATH` is supplied: files go directly into `PATH/` (no `.cosai-index/` subdirectory added). User gets exactly what they asked for.

### Other commands (later phases)

```
cdx-index scan [WORKSPACE_PATH] [OPTIONS]
  Walks the workspace and runs build on every project with a recognised manifest
  or an existing .cosai-index/. Same flags as build, applied per-project.

cdx-index status [WORKSPACE_PATH]
  Returns per-project: schema_version, last_indexed, days_stale, counts,
  vector_count, in_sync.

cdx-index drop PROJECT_SLUG
  Removes a project's vectors from the store. Files on disk untouched.
```

## Build order

Six phases. Each phase produces a working CLI capable of more than the last. Each phase ends with an eyeball pass against `_expected/*.md` for the corpora it produces.

### Phase 1 — Manifest only

`cdx-index build` produces only `manifest.json`. No packages, snippets, references, or embedding.

**Tests:** walk all 10 projects, confirm manifest filter-side fields against `_expected/<project>.md` manifest sections.

**Stopping point:** 10/10 manifests correct.

**Why this is the right starting point:**
- Smallest unit that produces useful output.
- Tests the hardest non-LLM logic (nested-manifest detection, `also` inference, license parsing, `status` declaration, `builds_on` inference).
- Validates the sidecar mechanism before any LLM cost.

### Phase 2 — Packages

Add `packages.jsonl`. Implements the nested-manifest rule from the spec:
- Recognise `pyproject.toml` with `[project]`, `package.json` with `name`, `go.mod`, `Cargo.toml` with `[package]`, `.claude-plugin/plugin.json`, `devcontainer-feature.json`.
- Skip tool-config-only manifests.
- Generate `name`, `language`, `ecosystem`, `version`, `entrypoints`, `public_api`, `install`, `path`.
- Generate deterministic `summary` from README first paragraph + entrypoint docstring (no LLM yet).

**Tests:** codeguard-cli should produce exactly 1 package entry; project-codeguard exactly 2; ws2-defenders exactly 3; ws1/ws3/ws4/cosai-tsc/oasis exactly 0; cosai-whitepaper-converter exactly 1 (the devcontainer feature).

**Stopping point:** correct package counts and filter-side fields across all 10 projects.

### Phase 3 — Snippets

Add `snippets.jsonl`. Implements snippet heuristics:
- Walk `examples/`, `cookbook/`, `recipes/`, `practical-guides/examples/`.
- Detect notebook files; extract code cells + leading markdown.
- For other files, parse with AST and find functions/classes with docstrings ≥ 200 chars.
- Honor `cosai-index: snippet` / `cosai-index: ignore` markers.
- Compute `depends_on` from import analysis (or notebook-directory contents).

**Tests:** ws2-defenders should produce 12–20 snippet entries; ws4 5–8 notebooks; codeguard-cli 2–4.

**Stopping point:** correct snippet discovery across all 10 projects.

### Phase 4 — References

Add `references.jsonl`. The largest piece, because it handles:
- Markdown chunking per heading, with 200-char minimum and ~1500-token max (sub-split on H3/H4).
- YAML structured-data decomposition (one entry per item with an `id` field).
- Markdown-over-PDF detection (skip PDF when adjacent `.md` exists).
- Frontmatter parsing — lift `status: "Approved"` into `tags`.
- Workspace-terminology preservation in summaries.

**Tests:** secure-ai-tooling produces 150–250 reference entries; ws1 40–70; oasis-open-project 60–120.

**Stopping point:** correct chunking and structured decomposition across all 10 projects. This is where eyeballing gets expensive; revisit the validator decision if reference-entry volume becomes unmanageable.

### Phase 5 — LLM summary generation

Replace deterministic summaries with Haiku-generated ones. Cache by `content_hash` so re-runs are free for unchanged content. Keep `--no-llm` flag for deterministic mode.

**Tests:** spot-check summaries on 3–4 entries per project. Confirm `MUST_CONTAIN` expectations from `_expected/*.md` hold. Watch API cost.

**Stopping point:** summaries that pass the embedding-side concept checks.

### Phase 6 — Embedding and vector store

Add `--embed` flag (or make embedding the default once stable). Embed `summary`, `install`, `title`, `structure_description`, `description` per the spec's embedding strategy. Upsert to SQLite + sqlite-vec at `cosai-discovery/.data/index.db`.

Add `cdx-index status` and `cdx-index drop`.

**Tests:** vector store contains the right number of vectors per project. `in_sync: true` after a fresh build.

**Stopping point:** end-to-end pipeline complete. Output is what the MCP server will consume.

## Testing approach

**Eyeball against `_expected/*.md` for now.** The expectation files are written for human reading; the iteration loop is:

1. Run the indexer on a project.
2. Open the resulting `.cosai-index/*` files in one pane.
3. Open `_expected/<project>.md` in another pane.
4. Walk down the test file, checking each expectation against actual output.
5. Fix either the indexer or the test as needed.

**No validator script yet.** A markdown-parsing validator would cost ~half a day to build and pays off when reference-entry volume exceeds eyeballing capacity. Phase 4 may trigger that — revisit then.

### Test corrections log

As the indexer matures, expectations in `_expected/*.md` will turn out to be wrong (they were written before the indexer existed, from walkthrough analysis). Each correction is worth not losing.

**Convention:** maintain a short "Test corrections" log per expectation file, at the bottom of the file. When an expectation is updated, note what was wrong and why.

**Convention:** maintain a short "Test corrections" log per test file, at the bottom of the file. When an expectation is updated, note what was wrong and why.

Example entry:
```
## Test corrections log

2026-05-20 — adjusted snippet count from 2–4 to 1–3.
  The docstring-length heuristic is stricter than expected; checker.py has
  no top-level docstring, so the file-hash-skip snippet doesn't auto-surface.
  Could add it via `cosai-index: snippet` marker; deferring that decision.
```

Small. Cheap. Paper trail for the future.

## Where I'd start

Phase 1 with project-codeguard as the first target. Concrete steps:

1. Set up `src/cdx_indexer/` skeleton with click entry point. Single `build` command stub that prints args.
2. Implement `manifest.py`: detect license (from `LICENSE.md` + `pyproject.toml`), infer `primary_kind` and `also` from filesystem signals, populate `languages`, declare `status`, read git metadata, declare `builds_on` (from a project-supplied config or detected via cross-project README links — Phase 1 can leave empty and fill manually for now).
3. Implement `writer.py`: atomic write to `.cosai-index/` or sidecar, sidecar resolution rules.
4. Run `cdx-index build /Users/neil/Dev/cosai-oasis/project-codeguard --sidecar`.
5. Eyeball the resulting `manifest.json` against `_expected/project-codeguard.md`'s manifest section.
6. Fix divergences (in either direction) until 1/1.
7. Repeat for the other 9 projects.

Done when 10/10 manifests match. Then Phase 2.

## Open implementation questions

These are deferred until they become concrete blockers. Each is fine to leave unanswered now.

1. **How does the indexer detect `builds_on`?** Three approaches:
   - Project declares via `.cdx-config.yaml`.
   - Indexer infers from README cross-project links.
   - Both — config file overrides inference.

   Recommendation: declared, not inferred. Inference is brittle (the codeguard-cli walk's `builds_on: project-codeguard, relationship: consumes` is obvious to a human but hard to detect mechanically). A small config file is honest.

2. **How does the indexer handle `governed_by: oasis-open-project`?** Same question. Probably a workspace-level default ("all CoSAI projects are governed_by oasis-open-project unless declared otherwise") rather than per-project repetition.

3. **How does the indexer decide on `primary_kind`?** First pass: heuristic based on filesystem signals (presence of `pyproject.toml` with `[project]` → consider `library`/`cli`; presence of `risk-map/yaml/*.yaml` → `dataset`; etc.). Override via `.cdx-config.yaml`. Decision deferred until Phase 1 inputs reveal what's reliably detectable.

4. **Where does the workspace-level config live?** Suggestion: `<workspace-root>/.cdx-workspace.yaml`. Single file declaring workspace-wide defaults (governance project, baseline ignore additions). Per-project `.cdx-config.yaml` overrides.

5. **What's the iteration loop for embedding cost?** Phase 6 is when this matters. Voyage charges per-token; a re-embed of all entries is expensive. The `content_hash` design means re-runs are mostly free; the question is the first run. Estimate budget once we know corpus size.

## Related documents

- [`index-file-format-0.1.0.md`](index-file-format-0.1.0.md) — the spec the indexer produces.
- [`mcp-tool-surface-0.0.2.md`](mcp-tool-surface-0.0.2.md) — the consumer of the indexed data.
- [`indexer-notes.md`](indexer-notes.md) — implementation hints accumulated during walkthroughs.
- [`evaluation-prompts.md`](evaluation-prompts.md) — prompts the indexed data must serve.
- [`../_expected/`](../_expected/) — per-project expectations for indexer output.
- [`candidate-changes.md`](candidate-changes.md) — schema changes considered but not adopted (so we don't relitigate).
