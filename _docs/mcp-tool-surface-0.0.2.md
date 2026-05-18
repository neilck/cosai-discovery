# COSAI Discovery — MCP Tool Surface

**Version:** 0.0.2

## Purpose

The COSAI Discovery MCP server exposes a workspace's project indexes (per the [`index-file-format`](index-file-format-0.1.0.md) spec) to AI coding agents. Agents working in one project use these tools to discover what exists in sibling projects: importable packages, copyable snippets, reference material, and cross-project relationships.

This document specifies the tools the server exposes. It is the contract between:

- **The MCP server**, which reads per-project `.cosai-index/` files and embeds them into a vector store.
- **AI agents** (Claude Code or any MCP client), which issue queries to discover and retrieve workspace content.

## Tool groups

Eight tools across three groups:

- **Write side (3)** — build and maintain the index.
- **Read side (4)** — what agents actually query.
- **Introspection (1)** — health checks across the workspace.

The hot path for a typical session:

```
list_projects  →  search  →  get_entry
```

Specialised side-tools (`traverse_builds_on`, `index_status`) serve specific use cases. Write-side tools are admin operations.

## Design rules

Two rules govern the tool surface, mirroring the rules in the index-file-format spec.

### Rule 1 — Filter vs. return

Not every "filter" field in the index schema is exposed as a query-param filter. The decision rule:

- **Filter (query param)** — when the field is a **coarse scoping dimension** across many projects/entries. Avoids over-fetching when the agent wants to narrow before retrieving.
- **Return (in response)** — when the field is **descriptive metadata the caller compares against their own state**. The agent reads the response and post-filters client-side.

Examples:
- `language`, `ecosystem`, `tags`, `status`, `license`, `form`, `kind` → **filter**. Coarse scoping.
- `primary_kind`, `also`, `version`, `symbol` → **return**. Descriptive; caller decides.

### Rule 2 — Cheap discovery before expensive retrieval

`list_projects` is intentionally cheap — manifest-only, no embedding lookup. Agents should call it first when the question is "what projects are even relevant?" `search` is heavier (vector lookup + optional reranking) and answers "what content within a project (or across projects) matches my query?"

## Goals → tool mapping

| Original goal | Primary call(s) |
|---|---|
| 1. Decide: write new code vs. import existing | `search(kind="package")` → `get_entry` |
| 2. Decide: cut-and-paste an existing pattern | `search(kind="snippet")` → `get_entry(include=["source"])` |
| 3. Load reference material in planning mode | `search(kind="reference")` → `get_entry(include=["full_document"])` |
| 4. Answer user questions about projects | `list_projects` (post-filter on `primary_kind` / `also`) |
| 5. Traverse cross-project dependencies | `traverse_builds_on` |

---

## Write side

### `build_index`

Run inside a project. Scans the repo, writes `.cosai-index/*`, embeds, upserts to the vector store.

```
Args:
  project_path: string                         # defaults to cwd
  kinds: ["packages","snippets","references","manifest"]  # default: all
  force: boolean                               # ignore content_hash, re-embed everything
  dry_run: boolean                             # write files but skip embedding/upsert

Returns:
  {
    project, files_written, counts,
    embeddings_added, embeddings_skipped, duration_ms
  }
```

### `reindex_all`

Walks the workspace and runs `build_index` for every project with a `.cosai-index/` directory.

```
Args:
  workspace_path: string                       # defaults to parent of cosai-discovery
  kinds: [...]
  force: boolean

Returns:
  {
    projects: [{ project, status, counts, error? }],
    total_duration_ms
  }
```

### `drop_project`

Removes a project's vectors from the store. For archives or accidental indexing.

```
Args:
  project: string

Returns:
  { project, vectors_removed }
```

---

## Read side

### `list_projects`

Manifest-only discovery. No embedding lookup. Returns every project the MCP server knows about, with enough descriptive metadata that the caller can choose which to look at more deeply.

```
Args:
  filters: {
    project?: string | string[],
    language?: string | string[],              # implementation language; manifest.languages
    license?: string,                          # SPDX expression matching
    status?: "active" | "archived" | "draft",
    tag?: string | string[],
    updated_after?: ISO-date,
    builds_on_contains?: string                # projects whose builds_on includes this slug
  }

Returns:
  [{
    project,
    description,
    languages,           # array
    primary_kind,        # see Rule 1 — returned, not filtered
    also,                # see Rule 1 — returned, not filtered
    status,
    license,
    tags,
    counts,              # { packages, snippets, references }
    last_indexed,
    builds_on            # array — full builds_on declarations
  }]
```

**Per Rule 1:** `primary_kind` and `also` are not query-param filters. The caller reads them in the response and decides client-side ("show me only the projects whose `primary_kind` or `also` includes `library`"). This avoids the awkward `primary_kind OR also_contains` query semantics and keeps full project context visible to the agent.

**`builds_on_contains` filter:** narrows to projects that declare a `builds_on` entry pointing at the named project. Cheap server-side filter for the common "what downstream projects depend on X?" question. For richer traversal (with relationship-type filtering), use `traverse_builds_on`.

### `search`

The main retrieval tool. Issues a vector lookup against the indexed corpora, optionally narrowed by filters.

```
Args:
  query: string                                # natural language

  kind: "package" | "snippet" | "reference" | "any"   # default "any"
                                                       # entry-level filter — picks which corpus

  filters: {
    project?: string | string[],
    language?: string | string[],              # entry-level: package/snippet language
    ecosystem?: string | string[],             # package only
    form?: "prose" | "structured" | "mixed",   # reference only
    status?: "active" | "archived" | "draft",  # filters by entry's owning project's status
    license?: string,                          # filters by entry's owning project's license
    tag?: string | string[],
    updated_after?: ISO-date,
    excludes?: { project?, tag? }
  }

  limit: number                                # default 10
  rerank: boolean                              # default true; uses Voyage rerank-2 on top-K
  group_by: "project" | null                   # default null — see note below

Returns (group_by=null):
  [{
    id,
    kind,
    project,
    project_primary_kind,    # see Rule 1 — returned, not filtered
    project_also,            # see Rule 1 — returned, not filtered
    title,
    path,
    lines?,                  # for snippets and references that chunk from a doc
    summary,
    score,
    tags,
    # corpus-specific descriptive fields:
    language?,               # package/snippet
    ecosystem?,              # package
    version?,                # package — descriptive, not filterable
    symbol?,                 # snippet — descriptive, not filterable
    form?,                   # reference
    structure_description?   # reference; truncated to ~200 chars
  }]

Returns (group_by="project"):
  [{ project, aggregate_score, top_hits: [<entry-as-above>, ...] }]
```

**Per Rule 1:** `project_primary_kind` and `project_also` accompany each hit so the agent can post-filter results by project class without a second `list_projects` call. `version` and `symbol` are returned but not filterable — they're descriptive metadata, not coarse scoping dimensions.

**`status` and `license` as `search` filters:** these are manifest-level fields, but the agent often wants to exclude (e.g.) draft projects from a content query. The server resolves the entry-to-project link and applies the filter.

**`group_by="project"` is advanced.** For the common "what projects are even relevant?" question, use `list_projects`. `group_by` is for queries where the agent specifically wants per-project aggregation of content hits.

### `get_entry`

Fetch a single entry by ID. Supports several levels of detail.

```
Args:
  id: string                                   # e.g. "snip:ws1-supply-chain/sbom-validator"
  include: ["source", "summary", "metadata", "full_document"]   # default: ["summary", "metadata"]

Returns:
  {
    id, kind, project,
    summary, metadata,
    source?:        { path, lines, content },
    full_document?: { path, content }
  }
```

| `include` value | What it returns |
|---|---|
| `summary` | The entry's embedded summary string. Default. |
| `metadata` | All descriptive fields (`language`, `ecosystem`, `tags`, etc.). Default. |
| `source` | The actual content at `path` + `lines`. For snippets, the code block. For references, the chunk. For packages, the README section behind the package's summary. |
| `full_document` | The whole containing document. **Meaningful only for `form: "prose"` references** — expands a chunk to its parent doc. For `form: "structured"` references (rules, YAML items, agent definitions), the entry's `source` is already the whole artifact, so `full_document` is redundant. For packages and snippets, returns the same as `source`. |

### `traverse_builds_on`

Traverse the cross-project `builds_on` graph in either direction.

```
Args:
  project: string                              # the pivot project
  direction: "upstream" | "downstream"
                                               # upstream: "what does X build on?"
                                               # downstream: "what builds on X?"
  relationship?: string | string[]             # optional — filter to specific relationship types
                                               # one of: extends, implements, consumes, cites, donated_from, governed_by

Returns:
  [{
    project,                                   # the related project
    relationship,                              # the type of relationship
    uri?,                                      # hint from the builds_on entry
    project_description,                       # short — from the related project's manifest
    project_primary_kind,
    project_also
  }]
```

**Use cases this tool serves cleanly:**
- "What does ws4 build on?" → `traverse_builds_on(project="ws4-...", direction="upstream")`
- "What CoSAI projects extend Project CodeGuard?" → `traverse_builds_on(project="project-codeguard", direction="downstream")`
- "What projects are governed by the OASIS umbrella?" → `traverse_builds_on(project="oasis-open-project", direction="downstream", relationship="governed_by")`

Semantic search across project descriptions handles loose versions of these queries, but the relationship-type signal (`governed_by` vs. `consumes` vs. `cites`) is what makes structured traversal worth a dedicated tool.

---

## Introspection

### `index_status`

Health check across the workspace's indexed projects.

```
Args:
  workspace_path?: string

Returns:
  [{
    project,
    schema_version,         # the spec version this project's manifest declares
    last_indexed,
    days_stale,
    counts,                 # { packages, snippets, references } — from manifest
    vector_count,           # how many vectors the store actually holds for this project
    in_sync                 # vector_count matches sum(counts)
  }]
```

`schema_version` is useful when the workspace mixes projects indexed against different format versions — the server can flag stale schemas.

`in_sync: false` indicates a mismatch between the on-disk index files and the vector store. Catches "I committed an index file but forgot to push to the store."

---

## Removed since v0.0.1

### `find_similar`

Removed. Was intended for "I have code in hand, has anyone written this?" but no real prompt across 11 evaluation queries × 10 projects exercised it. `search` with semantic match handles the same use case via a natural-language query. If a future prompt motivates code-pivot retrieval, the tool can be re-added.

---

## Tools considered and dropped (historical, no longer relevant)

- **`summarize_project`** — equivalent to `list_projects` + `search(kind="reference", project=X)`. Don't add a tool for a two-step the model can already do.
- **`explain_choice`** — "why did you recommend X over Y?" belongs in the prompt, not as a tool.
- **`watch`** — auto-reindex on file change. Out of scope; on-demand `build_index` is enough.
- **`search.dedup`**, **`get_entry.include="siblings"`** — were considered alongside the rejected `semantic_id` schema candidate. The duplicate-hit case (codeguard-cli vs. project-codeguard) was found to be handleable by the model without server-side dedup.

---

## Open questions

1. **`group_by="project"` payoff** — does this earn its keep when `list_projects` exists? After the first real indexer run, evaluate whether agents actually call `search(group_by="project")` or always go via `list_projects → search`. If the latter, cut `group_by` in v0.0.3.
2. **`get_entry.include` defaults** — should `source` be in the default `include`? Cheaper to include by default for snippets and structured references (which are small); expensive for prose references (large chunks). Possible solution: default-include source for `form: "structured"` references and all snippets, but require explicit `include` for prose references. Decide after real-query traffic.
3. **`traverse_builds_on` reranking** — should the tool order results by some signal (count of incoming relationships, recency of upstream commit)? For workspaces with sparse `builds_on` declarations this doesn't matter; for dense ones it might.
4. **`search.filters.status` semantics** — "exclude entries whose owning project is draft" is one interpretation. Another is "filter by an entry-level status if such a field existed." Currently we have no per-entry status (R7 rejected); the manifest-level interpretation is the only viable one. Document explicitly that this filters entries by their project's status.
5. **Pagination** — none of the tools currently support pagination. For workspaces with >100 hits on a broad query, consider adding `offset` + `next_token`. Defer until real traffic shows the need.

## Related documents

- [`index-file-format-0.1.0.md`](index-file-format-0.1.0.md) — the file-format contract this tool surface consumes.
- [`evaluation-prompts.md`](evaluation-prompts.md) — the 11 prompts these tools must serve.
- [`indexer-notes.md`](indexer-notes.md) — implementation hints for indexer authors.
- [`candidate-changes.md`](candidate-changes.md) — schema changes considered but not adopted.
