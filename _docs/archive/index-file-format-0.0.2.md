# COSAI Discovery — Index File Format

**Version:** 0.0.2
**Status:** Draft — still iterating against the workspace project walk-through. Supersedes v0.0.1.

## What changed since v0.0.1

- **Granularity rule (new, load-bearing):** entries are the unit of truth; the manifest summarises. A project mixing languages, kinds, or roles must decompose into multiple entries — one per coherent unit.
- **`manifest.project_kind`** replaced by `primary_kind` + `also`.
- **`manifest.languages`** clarified as a derived union, used only for coarse `list_projects` filtering — never for `search` filtering.
- **`references.jsonl`** entries gain `form` (enum: filter) and `structure_description` (free text: embedded).
- **`packages.ecosystem`** enum extended: adds `source`, `vendor`, `claude-plugin`, `mcp-server`.
- **Embed / filter / store invariant** documented as a working rule for all field additions.
- **Deferred candidate fields** listed at the end (`ingestibility`, `executable`, `equivalents`, `role`).

## Overview

Every project that participates in COSAI Discovery contains a `.cosai-index/` directory at its root. The contents of that directory are the project's **index** — a structured, embeddable description of what the project contains. The MCP server reads these files, embeds them, and serves them via vector search.

Index files are committed to each project's repository so they travel with the code.

## Working invariant: embed / filter / store

Every field in this schema must declare its purpose:

- **embed** — its value is included in the embedding input and contributes to semantic match. Use **free text**.
- **filter** — its value is used by the query side as a hard filter at the vector store. Use **enumerated strings** or simple scalars.
- **store** — its value is reference data, neither embedded nor filtered. Used by the model after retrieval (e.g. `path`, `lines`).

When a field needs both semantic match *and* hard filterability (e.g. languages on a multi-language rule), the rule is: **filter values live in `tags`, semantic context lives in `summary` / `structure_description`.** Same source, two destinations.

## Granularity rule (load-bearing)

> Each entry in `packages.jsonl`, `snippets.jsonl`, and `references.jsonl` must be specific enough that filterable fields have a single, unambiguous answer. If a project mixes languages, kinds, or roles across folders, decompose into multiple entries — one per coherent unit.

A Go-backend / TypeScript-frontend project must produce **at least two** package entries (one Go, one TS). A query for "TypeScript frontend code" filters by `language: "typescript"` at the entry level and gets only the frontend entry — it never matches the Go backend just because the manifest also lists TypeScript.

**Consequences:**

- The manifest **summarizes** the project; entries are the **truth**.
- `search` filters always apply at the entry level.
- `list_projects` filters apply at the manifest level for **discovery only** (which projects are even relevant?), then `search` narrows precisely.
- The indexer's job is to decompose the project into entries fine-grained enough that this rule holds — not to inflate the manifest with multi-axis fields.

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
  "schema_version": "0.0.2",
  "project": "<slug>",
  "path": "<rel-path-from-workspace>",
  "description": "<one-paragraph project description>",

  "languages": ["..."],
  "primary_kind": "library | cli | service | claude-plugin | ruleset | docs | whitepaper | working-group | dataset | template",
  "also": ["..."],

  "license": "<spdx-id>",
  "status": "active | archived | draft",
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

- `languages` is a **derived union** of the implementation languages of all entries in this project. Used only for coarse `list_projects` discovery filtering. **Never used for `search` filters** — `search` filters language at the entry level. Docs-only projects have `languages: []`.
- `primary_kind` is the consumer-facing answer to "what did I get?" (e.g. for project-codeguard, `ruleset` — the rules are the product). Single value. **Filter.**
- `also` lists additional kinds the project ships. **Filter** (multi-valued match: `primary_kind == X OR also contains X`). Example: `primary_kind: "ruleset"`, `also: ["library", "cli", "service", "claude-plugin", "docs"]`.
- `description` is **embedded** and contributes to project-level semantic match.
- `status` is declared by the project (default `active`). Auto-derivation is not attempted.

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

The enum is closed for v0.0.2; extend it via a versioned schema bump if real projects don't fit.

## `packages.jsonl`

One line per **importable / installable unit**. Answers **"can I depend on this?"**

A project with multiple packages (sub-manifests, monorepo workspaces, mixed-language stacks) produces multiple entries. Per the granularity rule, every entry has a single `language` and a single `ecosystem`.

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
- **Embed:** `summary`, `install` (so retrieval can match install-method queries like "Claude plugin for security").
- **Store:** `entrypoints`, `public_api`, `path`, `id`.
- A nested package manifest (`pyproject.toml`, `package.json`, `go.mod`, `Cargo.toml`, `.claude-plugin/plugin.json`, etc.) always produces its own entry — regardless of depth in the directory tree.
- `content_hash` covers the inputs that produced `summary`. Re-indexing skips entries whose hash is unchanged.

## `snippets.jsonl`

One line per notable code pattern. Answers **"is there code I can copy?"**

Each snippet has a single `language` — per the granularity rule, a multi-language example becomes multiple snippet entries.

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
- `depends_on` lists the imports the snippet uses, so queries can avoid pasting code that pulls in heavy deps.
- Snippet selection heuristics (still TBD as we walk projects):
  - Functions with docstrings ≥ N chars
  - Files under `examples/`, `recipes/`, `cookbook/`
  - Explicit marker comment, e.g. `# cosai-index: snippet`

## `references.jsonl`

One line per **doc chunk or structured content artifact**. Answers **"what context should I load?"**

This corpus carries everything that's read-for-context: README chunks, doc-site pages, whitepapers, rules, skills, prompts, checklists. The same knowledge can come in different forms — a whitepaper section and a structured rule may both teach safe deserialization. We distinguish them by **form**, not by category.

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
| `structured` | Schema'd content with directives, bullets, frontmatter — rules, checklists, controls, prompts, skill bundles. |
| `mixed` | Prose with structured fragments — a doc page that's mostly explanation with embedded rules or code blocks. |

### `structure_description`

A short prose description of how the content is structured, written for an LLM consumer. **Embedded** alongside `summary`. Empty / omitted for `form: "prose"`.

Example for a project-codeguard rule:

> "A Project CodeGuard unified rule. Frontmatter declares applicable languages (c, java, javascript, php, python, xml, yaml) and an alwaysApply flag. Body is organized into Requirements (bulleted directives), Security Impact (rationale), and Examples (avoid/prefer pairs). Convertible into Cursor, Copilot, Claude, Codex, and Windsurf agent rule formats."

When the source has frontmatter or typed attributes (e.g. a rule's `languages` list), the indexer:

1. **Reflects their meaning in `structure_description`** so the embedding sees them.
2. **Lifts filter-worthy values into `tags`** so they remain hard-filterable.

This is the embed/filter/store split in action: the same source feeds both an embedded prose description and a filterable tag set.

### Field notes

- **Filter:** `form`, `tags`.
- **Embed:** `title`, `summary`, `structure_description`.
- **Store:** `doc`, `section_path`, `path`, `lines`, `id`.
- One entry per heading-bounded chunk for prose. Long sections are sub-split.
- For structured artifacts (rules, skills), one entry per artifact file is the default. Re-evaluate if vector counts grow unwieldy.
- Whitepapers/PDFs: index the rendered markdown, not the PDF, when both exist.

## Embedding strategy

| Source | Model |
|---|---|
| `packages[].summary`, `packages[].install` | `voyage-code-3` |
| `snippets[].summary`, `snippets[].title` | `voyage-code-3` |
| `references[].summary`, `references[].structure_description` | `voyage-3` |
| `manifest.description` | `voyage-3` |

Each `content_hash` covers the inputs that produced its embedded fields. Re-indexing skips unchanged entries.

## Candidate fields — deferred until evidence demands them

These were considered in v0.0.2 design and remain plausible. They are **not** in the v0.0.2 schema. Promote when ≥2 projects produce evidence that the filter or link is actually needed.

| Field | Where | Type | Why deferred |
|---|---|---|---|
| `ingestibility` | references | filter enum: `high \| medium \| low` | Could be derived from token count; no query yet demands it as a hard filter. |
| `executable` | references | filter bool | No project in the queue has yet needed to filter "give me only runnable artifacts." |
| `equivalents` | any entry | store, array of IDs | Cross-form linking is intuitive but unproven; semantic search may surface alternates without explicit links. |
| `role` | packages | filter string (or loose enum) | The granularity rule already decomposes multi-role projects into multiple entries with distinct `name` + `language`. `role` adds expressiveness, not capability. |

## Open questions (carried forward)

1. **Snippet selection heuristics** — marker comment vs. pure heuristics, in practice. No project has yet produced enough snippets to validate.
2. **Short READMEs** — chunk-per-heading vs. whole-doc as a single entry. Tentative rule: chunk-per-heading with a ~200-character minimum, but unconfirmed.
3. **Whitepaper PDFs** — index rendered markdown only, or fall back to PDF when markdown is absent? No PDF-only project hit yet.
4. **README vs. MkDocs dedup** — prefer `docs/`, skip `README.md` when both exist? Tentative default, unconfirmed.
5. **`status` auto-derivation** — declared, default `active`. Revisit if a project actually needs `archived` / `draft` and human declaration proves too burdensome.
6. **`see_also` / `supersedes` cross-project links** — folded into the deferred `equivalents` candidate. Reopen if a non-equivalence link emerges (e.g. one rule strictly supersedes another).
