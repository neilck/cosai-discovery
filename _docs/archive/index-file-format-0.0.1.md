# COSAI Discovery — Index File Format

**Version:** 0.0.1
**Status:** Draft — to be iterated against real workspace projects

## Overview

Every project that participates in COSAI Discovery contains a `.cosai-index/` directory at its root. The contents of that directory are the project's **index** — a structured, embeddable description of what the project contains. The MCP server reads these files, embeds them, and serves them via vector search.

Index files are committed to each project's repository so they travel with the code.

## Layout per project

```
<project-root>/
  .cosai-index/
    manifest.json       # singleton, project metadata
    packages.jsonl      # importable units
    snippets.jsonl      # copy-pasteable code
    references.jsonl    # doc chunks
```

- **JSONL** for the three corpora — append-friendly, diff-friendly, streamable.
- **JSON** for the singleton manifest.
- All four files are committed to the repo.

## `manifest.json`

Project-level metadata. Used as filter dimensions in queries, not as retrieval targets.

```json
{
  "schema_version": "0.0.1",
  "project": "<slug>",
  "path": "<rel-path-from-workspace>",
  "description": "<one-paragraph description>",
  "languages": ["..."],
  "primary_language": "<lang>",
  "license": "<spdx-id>",
  "status": "active|archived|draft",
  "project_kind": "library|cli|docs|whitepaper|working-group|mixed",
  "owners": ["..."],
  "tags": ["..."],
  "repo_url": "<url>",
  "default_branch": "main",
  "last_commit": { "sha": "...", "date": "<iso-8601>" },
  "last_indexed": "<iso-8601>",
  "counts": { "packages": 0, "snippets": 0, "references": 0 }
}
```

### Field notes

- `project_kind` exists because several COSAI projects are docs-only. It lets `list_projects` filter cleanly (e.g. "only return libraries").
- `status` is project-declared, not derived. Auto-derivation rules TBD.
- `description` is embedded and used in project-level search.

## `packages.jsonl`

One line per importable / installable unit. Answers **"can I depend on this?"**

```json
{
  "id": "pkg:<project>/<name>",
  "kind": "package",
  "name": "<name>",
  "ecosystem": "pypi|npm|go|cargo|none",
  "version": "<semver-or-null>",
  "entrypoints": ["..."],
  "public_api": ["..."],
  "path": "<rel-path>",
  "install": "<copy-pasteable install command>",
  "summary": "<llm-generated, 1-3 sentences, this is what gets embedded>",
  "tags": ["..."],
  "content_hash": "sha256:..."
}
```

### Field notes

- `ecosystem: "none"` is for vendor-able code that isn't published to a package registry.
- `entrypoints` covers CLI commands and main functions.
- `public_api` lists exported symbols worth knowing about (not exhaustive).
- `content_hash` covers the inputs that produced `summary` (manifest file + README). Re-indexing skips entries whose hash is unchanged.

## `snippets.jsonl`

One line per notable code pattern. Answers **"is there code I can copy?"**

```json
{
  "id": "snip:<project>/<slug>",
  "kind": "snippet",
  "title": "<short title>",
  "path": "<rel-path>",
  "lines": "<start>-<end>",
  "language": "<lang>",
  "symbol": "<function-or-class-name>",
  "summary": "<llm-generated, embedded>",
  "tags": ["..."],
  "depends_on": ["..."],
  "content_hash": "sha256:..."
}
```

### Field notes

- `depends_on` lists imports the snippet uses. Lets queries avoid pasting code that pulls in heavy deps.
- Snippet selection heuristics (TBD as we walk projects):
  - Functions with docstrings ≥ N chars
  - Files under `examples/`, `recipes/`, `cookbook/`
  - Explicit marker comment, e.g. `# cosai-index: snippet`

## `references.jsonl`

One line per doc chunk. Answers **"what context should I load?"**

```json
{
  "id": "ref:<project>/<doc>#<anchor>",
  "kind": "reference",
  "title": "<heading text>",
  "doc": "<rel-doc-path>",
  "section_path": ["H1", "H2", "..."],
  "path": "<rel-doc-path>",
  "lines": "<start>-<end>",
  "summary": "<llm-generated, embedded>",
  "tags": ["..."],
  "content_hash": "sha256:..."
}
```

### Field notes

- One entry per heading-bounded chunk. Long sections are sub-split.
- `section_path` is the heading breadcrumb.
- Whitepapers/PDFs: index the rendered markdown, not the PDF, when both exist.

## Embedding strategy

| Source | Model |
|---|---|
| `packages[].summary` | `voyage-code-3` |
| `snippets[].summary` | `voyage-code-3` |
| `references[].summary` | `voyage-3` |
| `manifest.description` | `voyage-3` |

Each `content_hash` covers the inputs that produced its `summary`. Re-indexing skips unchanged entries.

## Why separate files per kind

1. **Filters become table/collection switches** rather than metadata predicates — cheaper at query time.
2. **Re-indexing one kind doesn't churn the others.**
3. **Hand-editing is safe** — particularly for `references.jsonl` where curated summaries may beat auto-generated ones.

## Open questions (to resolve while walking projects)

1. Is the `project_kind` enum (`library/cli/docs/whitepaper/working-group/mixed`) sufficient?
2. Can `status` be auto-derived, or must it always be declared?
3. Snippet selection: explicit marker comments vs. pure heuristics — which wins in practice?
4. For doc-only projects: stay empty in `packages.jsonl`, or treat the whitepaper as a "package"?
5. Whitepaper PDFs: index rendered markdown only, or fall back to PDF when markdown is absent?
6. Monorepo packages: flat list, or hierarchical?
7. Short READMEs: chunk-per-heading vs. whole-doc as a single entry?
8. Cross-project links: should an entry declare `supersedes` / `see_also` pointing at another project's entry?

---

## Pending changes for v0.0.2

Decisions made while walking projects, to be folded into the next version of this spec. v0.0.1 remains frozen as a snapshot; this section accumulates resolved direction until we cut a new version.

### Working invariant: embed / filter / store

Every field in this schema must declare its purpose:

- **embed** — its value is included in the embedding input and contributes to semantic match. Use **free text**.
- **filter** — its value is used by the query side as a hard filter at the vector store. Use **enumerated strings** or simple scalars.
- **store** — its value is reference data, neither embedded nor filtered. Used by the model after retrieval (e.g. `path`, `lines`, `equivalents`).

Drives the choice between free-text and enum types as the schema grows. *(Resolved Q-A1.1, adopted.)*

### Resolved changes

**Q-A3 — `manifest.project_kind` reshape**
Replace single `project_kind` value with `primary_kind` (single value, the consumer-facing answer to "what did I get?") plus `also` (array of additional kinds). Constrained enum:
- `library` — importable code package
- `cli` — command-line tool
- `service` — runnable server (MCP, HTTP, daemon)
- `claude-plugin` — Claude Code plugin / skill bundle
- `ruleset` — structured guidance content (rules, prompts, policies)
- `docs` — documentation site
- `whitepaper` — single-document research output
- `working-group` — meeting notes, charters, governance artifacts
- `dataset` — structured non-code data
- `template` — repo or content template

Example for project-codeguard: `"primary_kind": "ruleset"`, `"also": ["library", "cli", "service", "claude-plugin", "docs"]`.

**Q-A4 — `language` means implementation language only**
`manifest.languages`, `packages[].language`, and `snippets[].language` all carry the **implementation language** of the project / package / snippet. They do **not** carry subject-matter languages — those are captured in free-text fields (`summary`, `structure_description`) where the embedding sees them. `tags` may opportunistically include languages but no field requires it. Docs-only projects have `manifest.languages: []`.

**Q-A1 — `references.jsonl` gains form + structure description**
Same knowledge can come in different forms (a whitepaper and a structured rule both teach safe deserialization). Distinguish by form, not by category:
- Add `form` (enum, **filter**): `"prose" | "structured" | "mixed"`.
- Add `structure_description` (free text, **embed**): a short prose description of how the content is structured. Empty / omitted for `form: "prose"`. Included in the embedding input alongside `summary` so retrieval naturally matches queries like "show me bulleted security rules I can apply quickly."

When the source has frontmatter or other typed attributes (e.g. a rule's `languages` list), the indexer must:
1. Reflect their meaning in `structure_description` (so the embedding sees them).
2. Lift filter-worthy values into `tags` (so they remain hard-filterable).

Decision: do **not** add a fourth corpus (`assets.jsonl`). Stay in `references.jsonl`.

### Candidate fields — deferred until ≥2 projects produce evidence

These were considered during Q-A1 / Q-A6 and remain plausible additions, but are not in v0.0.2:

- `ingestibility` (filter): `"high" | "medium" | "low"`. Coarse signal of how cheap a reference is to load into context. Could be inferred from token count.
- `executable` (filter, boolean): flags runnable references (Claude Code skills, agent definitions, runnable prompts).
- `equivalents` (store, array of IDs): cross-reference to entries carrying the same knowledge in a different form, so Claude Code can pick by context budget.

Promote when concrete query patterns demand them — not before.
