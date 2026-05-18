# COSAI Discovery — MCP Tool Surface

**Version:** 0.0.1
**Status:** Draft — to be iterated against real workspace projects

## Overview

The COSAI Discovery MCP server exposes 8 tools split across three groups:

- **Write side (3)** — build and maintain the index
- **Read side (4)** — what Claude Code (or any MCP client) actually queries
- **Introspection (1)** — health checks

The hot path for a typical Claude Code session is:

```
list_projects  →  search  →  get_entry
```

Everything else is admin or specialized.

## Goals → tool mapping

| Original goal | Primary call(s) |
|---|---|
| 1. Decide: write new code vs. import existing | `search(kind=packages)` → `get_entry` |
| 2. Decide: cut-and-paste an existing pattern | `search(kind=snippets)` *or* `find_similar(code=...)` → `get_entry(include=source)` |
| 3. Load reference material in planning mode | `search(kind=references)` → `get_entry(include=full_document)` |
| 4. Answer user questions about the projects | `list_projects` + `search(group_by=project)` |

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

Walks the workspace and runs `build_index` for every project that already has a `.cosai-index/` directory. Convenience for "I pulled new commits everywhere."

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

Removes a project's vectors from the store. For archives, or when something was indexed by mistake.

```
Args:
  project: string

Returns:
  { project, vectors_removed }
```

---

## Read side

### `list_projects`

Cheap manifest-only discovery. No embedding, no vector search.

```
Args:
  filters: {
    language?: string | string[],
    status?: "active" | "archived" | "draft",
    project_kind?: string | string[],
    tag?: string | string[],
    updated_after?: ISO-date
  }

Returns:
  [{
    project, description, primary_language,
    project_kind, status, counts, last_indexed
  }]
```

This is the tool Claude Code should call **first** in most flows — answers "what's even available?"

### `search`

The main retrieval tool.

```
Args:
  query: string                                # natural language
  kind: "packages" | "snippets" | "references" | "any"   # default "any"
  filters: {
    project?: string | string[],
    language?: string | string[],
    tag?: string | string[],
    updated_after?: ISO-date,
    ecosystem?: string,                        # pypi/npm/go/...
    excludes?: { project?, tag? }
  }
  limit: number                                # default 10
  rerank: boolean                              # default true; uses Voyage rerank-2 on top-K
  group_by: "project" | null                   # default null

Returns (group_by=null):
  [{ id, kind, project, title, path, lines?, summary, score, tags }]

Returns (group_by="project"):
  [{ project, aggregate_score, top_hits: [<entry-as-above>, ...] }]
```

Returns hits, not file contents — keeps results compact. Use `get_entry` to fetch source.

### `get_entry`

Fetch by ID.

```
Args:
  id: string                                   # e.g. "snip:ws1-supply-chain/sbom-validator"
  include: ["source", "summary", "metadata", "full_document"]   # default: summary, metadata

Returns:
  {
    id, kind, project,
    summary, metadata,
    source?:        { path, lines, content },
    full_document?: { path, content }          # whole containing doc, expanded from chunk
  }
```

`full_document` is the planning-mode case: "give me the whole architecture doc, not just the heading that matched."

### `find_similar`

Pivot on either an existing entry's ID *or* a raw code blob. Same return shape as `search`.

```
Args:
  id?: string                                  # pivot on an indexed entry
  code?: string                                # or pivot on a raw code snippet
  kind: "packages" | "snippets" | "references" | "any"
  limit: number

Returns: same as search (group_by=null)
```

Primary use case: Claude Code has the user's code in hand and wants to ask "has anyone written this?" — the natural input is the code itself, not a query string.

---

## Introspection

### `index_status`

Health check across the workspace.

```
Args:
  workspace_path?: string

Returns:
  [{
    project, last_indexed, days_stale,
    counts, vector_count, in_sync: boolean
  }]
```

`in_sync` is `false` when index files exist on disk but aren't in the vector store (or vice versa). Catches "I committed an index file but forgot to push to the store."

---

## Tools considered and dropped

- **`summarize_project`** — equivalent to `list_projects` + `search(kind=references, project=X)`. Don't add a tool for a two-step the model can already do.
- **`explain_choice`** — "why did you recommend X over Y?" belongs in the prompt, not as a tool.
- **`watch`** — auto-reindex on file change. Out of scope for v0; on-demand `build_index` is enough.

---

## Open questions (to resolve while walking projects)

1. Does `search.filters.ecosystem` need to infer from the caller's cwd, or is explicit-only sufficient?
2. Should `find_similar` survive past v0, or collapse into `search` once we've seen real usage?
3. For `group_by="project"`, what's the right default `top_hits` count per group?
4. Does `index_status` need to detect *file-level* staleness (index file older than source files), not just "exists in store"?
