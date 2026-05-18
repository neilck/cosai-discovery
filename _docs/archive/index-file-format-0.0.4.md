# COSAI Discovery — Index File Format

**Version:** 0.0.4
**Status:** Draft. Supersedes v0.0.3. Adds one schema field (`manifest.builds_on`); resolves one open question (notebook handling).

## What changed since v0.0.3

This is the first non-clarification release since v0.0.2. It adds **one schema field** based on evidence accumulated across walks of project-codeguard, codeguard-cli, ws3-ai-risk-governance, and ws4-secure-design-agentic-systems.

- **New field: `manifest.builds_on`** — an array of typed cross-project dependency declarations. Each entry has `project` (required), `relationship` (required, enumerated), and `uri` (optional, hint).
- **Resolves open question #2 (notebook handling):** Jupyter notebooks (`.ipynb`) under `examples/`, `cookbook/`, `recipes/`, or `practical-guides/examples/` are **snippet candidates** — one entry per notebook. Supporting files (`utils.py`, fixture JSON, `assets/`) go into `depends_on`, not separate entries. Indexer extracts code cells + leading markdown for the summary.
- **Candidate field renumbering:** R6 (`ingestibility`) was moved from C2 to Rejected in Phase 8 after a six-walk re-evaluation. C-numbering preserved (C3–C8 retain their original IDs) so prior walkthrough logs continue to make sense.

## Overview

Every project that participates in COSAI Discovery contains a `.cosai-index/` directory at its root. The contents of that directory are the project's **index** — a structured, embeddable description of what the project contains. The MCP server reads these files, embeds them, and serves them via vector search.

Index files are committed to each project's repository so they travel with the code.

## Working invariant: embed / filter / store

Every field in this schema must declare its purpose:

- **embed** — its value is included in the embedding input and contributes to semantic match. Use **free text**.
- **filter** — its value is used by the query side as a hard filter at the vector store. Use **enumerated strings** or simple scalars.
- **store** — its value is reference data, neither embedded nor filtered. Used by the model after retrieval (e.g. `path`, `lines`, `builds_on`).

When a field needs both semantic match *and* hard filterability (e.g. languages on a multi-language rule), the rule is: **filter values live in `tags`, semantic context lives in `summary` / `structure_description`.** Same source, two destinations.

## Granularity rule (load-bearing)

> Each entry in `packages.jsonl`, `snippets.jsonl`, and `references.jsonl` must be specific enough that filterable fields have a single, unambiguous answer. If a project mixes languages, kinds, or roles across folders, decompose into multiple entries — one per coherent unit.

A Go-backend / TypeScript-frontend project must produce **at least two** package entries (one Go, one TS). A query for "TypeScript frontend code" filters by `language: "typescript"` at the entry level and gets only the frontend entry — it never matches the Go backend just because the manifest also lists TypeScript.

**Consequences:**

- The manifest **summarizes** the project; entries are the **truth**.
- `search` filters always apply at the entry level.
- `list_projects` filters apply at the manifest level for **discovery only** (which projects are even relevant?), then `search` narrows precisely.
- The indexer's job is to decompose the project into entries fine-grained enough that this rule holds — not to inflate the manifest with multi-axis fields.

## Schema discipline (working principle)

Candidate fields stay deferred unless a real query — phrased in the user's voice — demonstrably fails or degrades without them. Project-shape alone is not evidence; a concrete prompt is. Candidate changes (deferred and rejected) are tracked in [`candidate-changes.md`](candidate-changes.md), not in this spec.

After seven project walks, only one candidate has met the promotion threshold: `builds_on` (now in this version, see below). Six others remain deferred; six have been rejected.

## Layout per project

```
<project-root>/
  .cosai-index/
    manifest.json           # singleton: project-wide metadata + derived summaries
    packages.jsonl          # zero or more entries (one per coherent package)
    snippets.jsonl          # zero or more entries (one per coherent code pattern)
    references.jsonl        # zero or more entries (one per coherent doc chunk / structured artifact)
```

**Files carry many entries.** JSONL is chosen specifically because a project routinely contains multiple packages (sub-`pyproject.toml`, separate `package.json` per workspace, etc.), many snippets, and many reference chunks. Decomposition is the norm, not the exception.

Each JSONL file is a stream of independent JSON objects, one per line, where every object can be filtered, retrieved, and embedded on its own merits. Empty corpora (e.g. a docs-only project with no packages) are represented as zero-line files, not by omitting the file.

## `manifest.json`

Singleton, project-wide. Used as coarse filter dimensions in `list_projects`. **Never** used by `search` for language / kind filtering — those go through the entries.

```json
{
  "schema_version": "0.0.4",
  "project": "<slug>",
  "path": "<rel-path-from-workspace>",
  "description": "<one-paragraph project description>",

  "languages": ["..."],
  "primary_kind": "library | cli | service | claude-plugin | ruleset | docs | whitepaper | working-group | dataset | template",
  "also": ["..."],

  "license": "<SPDX expression, optional — omit when no license declared>",
  "status": "active | archived | draft",
  "owners": ["..."],
  "tags": ["..."],

  "repo_url": "<url>",
  "default_branch": "main",

  "builds_on": [
    {"project": "<slug>", "relationship": "extends | implements | consumes | cites | donated_from", "uri": "<optional hint>"}
  ],

  "last_commit": { "sha": "...", "date": "<iso-8601>" },
  "last_indexed": "<iso-8601>",

  "counts": { "packages": 0, "snippets": 0, "references": 0 }
}
```

### Field notes

- `languages` is a **derived union** of the implementation languages of all entries in this project. Used only for coarse `list_projects` discovery filtering. **Never used for `search` filters** — `search` filters language at the entry level. Docs-only projects have `languages: []`.
- `primary_kind` is the consumer-facing answer to "what did I get?" (e.g. for project-codeguard, `ruleset` — the rules are the product). Single value. **Filter.**
- `also` lists additional kinds the project ships. **Filter** (multi-valued match: `primary_kind == X OR also contains X`).
- `description` is **embedded** and contributes to project-level semantic match.
- `status` is declared by the project (default `active`). Auto-derivation is not attempted.
- `license` is **optional**. Omit when absent. Accepts SPDX expressions (e.g. `"CC-BY-4.0 AND Apache-2.0"`).
- `builds_on` declares cross-project dependencies on other COSAI workspace projects. See dedicated section below.

### Constrained `primary_kind` / `also` enum

| Value | Meaning |
|---|---|
| `library` | importable code package |
| `cli` | command-line tool |
| `service` | runnable server (MCP, HTTP, daemon) |
| `claude-plugin` | Claude Code plugin / skill bundle |
| `ruleset` | structured guidance content (rules, prompts, policies) |
| `docs` | documentation site |
| `whitepaper` | single-document research output |
| `working-group` | meeting notes, charters, governance artifacts |
| `dataset` | structured non-code data |
| `template` | repo or content template |

The enum is closed for v0.0.4; extend it via a versioned schema bump if real projects don't fit.

### `builds_on` — cross-project dependencies

A project may **build on** another COSAI workspace project — by extending it, implementing its framework, consuming its content, citing it for context, or being donated from it. `builds_on` makes that relationship machine-readable, enabling reverse-traversal queries like *"what projects extend Project CodeGuard?"* and *"how does ws4 use the CoSAI Risk Map?"*

**Type:** array of objects. Empty array (or omitted) for self-contained projects.

**Each entry:**

```json
{
  "project": "<slug>",
  "relationship": "<enum>",
  "uri": "<optional hint>"
}
```

| Field | Required | Type | Notes |
|---|---|---|---|
| `project` | yes | string | Slug matching another project's `manifest.project`. Used for cross-traversal. |
| `relationship` | yes | enum | One of the values below. Declares *what kind* of dependency. |
| `uri` | no | string | **Hint, not a guarantee.** May point at the upstream's GitHub repo, a specific document URL, a deep-link into an upstream entry, or an internal reference. The indexer/MCP server does not validate format. Consumers treat it as a navigation aid. |

**`relationship` enum:**

| Value | Meaning | Example |
|---|---|---|
| `extends` | This project is a continuation or direct derivative of the other. | A v2 of an existing framework. |
| `implements` | This project provides an implementation of the other's framework, controls, or specification. | ws4's `mcp-secure-tool-design.md` implements controls from secure-ai-tooling's Risk Map. |
| `consumes` | This project uses the other as a runtime/build-time input. | codeguard-cli consumes project-codeguard's rule files. |
| `cites` | This project references the other for context but isn't derivative. | A whitepaper that references another for background. |
| `donated_from` | This project was founded on a donation/transfer from the other. | ws3-ai-risk-governance acknowledges Project CodeGuard as a donated foundation. |

**Embed / filter / store classification: `store`.** The field is read by the model *after* retrieval to traverse to related projects. It is **not embedded** in the manifest's embedding input. Whether `relationship` becomes a query-side filter (e.g. `list_projects.filters.builds_on_relationship`) is a tool-surface decision tracked separately.

**Authoring guidance:**
- A project may declare multiple `builds_on` entries (e.g. ws4 builds on both secure-ai-tooling and cosai-tsc).
- Each `builds_on` entry targets exactly one upstream project. Different relationships with the same upstream get separate entries.
- `uri` is optional but recommended when the upstream reference is deep — pointing at a specific document or section helps the model navigate without semantic search.
- The relationship type is the project's *honest* characterisation. Prefer narrower types (`cites`) when uncertain over broader (`extends`).

**Examples:**

```json
// codeguard-cli's manifest
"builds_on": [
  {"project": "project-codeguard", "relationship": "consumes", "uri": "https://github.com/cosai-oasis/project-codeguard"}
]

// ws3-ai-risk-governance's manifest
"builds_on": [
  {"project": "project-codeguard", "relationship": "donated_from", "uri": "https://github.com/cosai-oasis/project-codeguard"}
]

// ws4-secure-design-agentic-systems's manifest
"builds_on": [
  {"project": "secure-ai-tooling", "relationship": "implements", "uri": "https://github.com/cosai-oasis/secure-ai-tooling/tree/main/risk-map"},
  {"project": "cosai-tsc", "relationship": "cites", "uri": "https://github.com/cosai-oasis/cosai-tsc/blob/main/security-principles-for-agentic-systems.md"}
]
```

## `packages.jsonl`

One line per **importable / installable unit**. Answers **"can I depend on this?"**

A project with multiple packages (sub-manifests, monorepo workspaces, mixed-language stacks) produces multiple entries. Per the granularity rule, every entry has a single `language` and a single `ecosystem`.

### Nested-manifest rule

A nested package manifest produces its own entry **only if it declares an installable artifact**:

- `pyproject.toml` — requires `[project]` table with a `name`. A `pyproject.toml` containing only `[tool.pytest]`, `[tool.coverage]`, etc. is tool configuration, not a package.
- `package.json` — requires a `name` field. `"private": true` skips unless it's the only project manifest.
- `go.mod` — always qualifies.
- `Cargo.toml` — requires `[package]` table (a `[workspace]`-only manifest does not).
- `.claude-plugin/plugin.json` — always qualifies; produces `ecosystem: "claude-plugin"`.

```json
{
  "id": "pkg:<project>/<name>",
  "kind": "package",
  "name": "<name>",
  "language": "<implementation language>",
  "ecosystem": "pypi | npm | go | cargo | source | vendor | claude-plugin | mcp-server | none",
  "version": "<semver-or-null>",
  "entrypoints": ["..."],
  "public_api": ["..."],
  "path": "<rel-path>",
  "install": "<copy-pasteable install command>",
  "summary": "<llm-generated, 1-3 sentences, embedded>",
  "tags": ["..."],
  "content_hash": "sha256:..."
}
```

### `ecosystem` values

| Value | Meaning | Install hint |
|---|---|---|
| `pypi` | Published to PyPI | `pip install <name>` |
| `npm` | Published to npm | `npm install <name>` |
| `go` | Go module on proxy.golang.org | `go get <path>` |
| `cargo` | Published to crates.io | `cargo add <name>` |
| `source` | Installable from this repo by source build | `pip install .` / equivalent |
| `vendor` | Meant to be copied into the consumer's tree | "Copy file(s) X into your project at Y" |
| `claude-plugin` | Claude Code plugin / skill bundle | `/plugin install …` or via marketplace |
| `mcp-server` | Runnable MCP server | "Configure in `mcpServers` block" |
| `none` | Not meant for external consumption | n/a |

Single value per entry. Pick the **consumption-facing** answer — how does a downstream user actually get and use this? Install mechanics live in the free-text `install` field.

### Field notes

- **Filter:** `name`, `language`, `ecosystem`, `version`.
- **Embed:** `summary`, `install`.
- **Store:** `entrypoints`, `public_api`, `path`, `id`.
- `content_hash` covers the inputs that produced `summary`. Re-indexing skips entries whose hash is unchanged.

## `snippets.jsonl`

One line per notable code pattern. Answers **"is there code I can copy?"**

Each snippet has a single `language` — per the granularity rule, a multi-language example becomes multiple snippet entries.

### Snippet selection heuristics

A file is a snippet candidate if any of the following hold:

- It lives under `examples/`, `cookbook/`, `recipes/`, or `practical-guides/examples/` at any depth. One snippet entry per file is the default.
- It is a Jupyter notebook (`.ipynb`) in any of the above locations. The indexer extracts code cells + leading markdown for the summary. Supporting files in the same directory (`utils.py`, fixture JSON, `assets/`) go into `depends_on`, not separate entries.
- It contains a top-level function or class with a docstring of ≥ ~200 characters.
- It contains an explicit `cosai-index: snippet` comment marker (opts a non-default location in).

A file is excluded if it carries an explicit `cosai-index: ignore` marker, or if it's under a test path (`tests/`, `__tests__/`, `*_test.go`, `test_*.py`).

```json
{
  "id": "snip:<project>/<slug>",
  "kind": "snippet",
  "title": "<short title>",
  "path": "<rel-path>",
  "lines": "<start>-<end>",
  "language": "<implementation language>",
  "symbol": "<function-or-class-name>",
  "summary": "<llm-generated, embedded>",
  "tags": ["..."],
  "depends_on": ["..."],
  "content_hash": "sha256:..."
}
```

### Field notes

- **Filter:** `language`, `symbol`, `tags`.
- **Embed:** `title`, `summary`.
- **Store:** `path`, `lines`, `depends_on`, `id`.
- `depends_on` lists the imports the snippet uses (not the file's full import block), plus same-directory supporting files for notebook snippets.

## `references.jsonl`

One line per **doc chunk or structured content artifact**. Answers **"what context should I load?"**

This corpus carries everything that's read-for-context: README chunks, doc-site pages, whitepapers, rules, skills, prompts, checklists, structured data items. The same knowledge can come in different forms — a whitepaper section and a structured rule may both teach safe deserialization. We distinguish them by **form**, not by category.

```json
{
  "id": "ref:<project>/<doc>#<anchor>",
  "kind": "reference",
  "title": "<heading or artifact title>",
  "doc": "<rel-doc-path>",
  "section_path": ["H1", "H2", "..."],
  "path": "<rel-doc-path>",
  "lines": "<start>-<end>",

  "form": "prose | structured | mixed",
  "structure_description": "<free text describing the form; embedded>",

  "summary": "<llm-generated; embedded>",
  "tags": ["..."],
  "content_hash": "sha256:..."
}
```

### `form` values

| Value | Meaning |
|---|---|
| `prose` | Flowing text — whitepapers, README sections, blog posts. |
| `structured` | Schema'd content with directives, bullets, frontmatter — rules, checklists, controls, prompts, skill bundles, individual YAML data items. |
| `mixed` | Prose with structured fragments — a doc page that's mostly explanation with embedded rules or code blocks. |

### Reference chunking rules

- **Markdown documents are chunked per heading.** Default H2 boundaries; sub-split on H3/H4 when a section is very long (target ~1500-token chunks).
- **Minimum chunk size ~200 characters.** Tiny stub sections collapse into their parent.
- **Structured data files (YAML lists of items)** are decomposed into one entry per item, not one entry per file.
- **When markdown and PDF copies of the same document exist, index the markdown only.**
- **READMEs and docs-site sources coexist.** Both are indexed; ranking handles dedup.

### `structure_description`

A short prose description of how the content is structured, written for an LLM consumer. **Embedded** alongside `summary`. Empty / omitted for `form: "prose"`.

When the source has frontmatter or typed attributes (e.g. a rule's `languages` list), the indexer:

1. **Reflects their meaning in `structure_description`** so the embedding sees them.
2. **Lifts filter-worthy values into `tags`** so they remain hard-filterable.

### Field notes

- **Filter:** `form`, `tags`.
- **Embed:** `title`, `summary`, `structure_description`.
- **Store:** `doc`, `section_path`, `path`, `lines`, `id`.

## Embedding strategy

| Source | Model |
|---|---|
| `packages[].summary`, `packages[].install` | `voyage-code-3` |
| `snippets[].summary`, `snippets[].title` | `voyage-code-3` |
| `references[].summary`, `references[].structure_description` | `voyage-3` |
| `manifest.description` | `voyage-3` |

Each `content_hash` covers the inputs that produced its embedded fields. Re-indexing skips unchanged entries.

## Candidate changes

Deferred and rejected schema changes (with per-project evidence tables) are tracked in [`candidate-changes.md`](candidate-changes.md). That doc is the single source of truth — neither this spec nor the walkthrough log duplicates its content.

## Open questions (carried forward)

After seven walks, the remaining open questions are small:

1. **Maximum chunk size and sub-splitting rules** for very long sections. Tentative ~1500 tokens; not yet validated against retrieval results.
2. **`status` auto-derivation** — currently declared, default `active`. Revisit if a project needs `archived` and human declaration proves burdensome.
3. **Image/SVG content with meaningful text** (e.g. secure-ai-tooling's risk-map graph). Currently skipped; revisit if image embeddings come into scope.
4. **Tool-surface implications of `builds_on`** — should `list_projects` gain a `builds_on_project` filter? Should `search` surface entries from upstream projects when querying a downstream? These are tool-side decisions, tracked in the MCP tool surface doc when next revised.

Closed since v0.0.3: notebook handling (resolved as snippet candidates per `examples/`-style convention).
