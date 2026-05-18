# COSAI Discovery — Index File Format

**Version:** 0.0.3
**Status:** Draft — clarifications-only release. Supersedes v0.0.2. No new schema fields.

## What changed since v0.0.2

This is a **clarifications-only release**. Schema fields are unchanged. The walks of project-codeguard, codeguard-cli, secure-ai-tooling, and ws2-defenders against v0.0.2, plus the prompt-driven re-evaluation under the methodology introduced in Phase 6, produced zero new fields and zero structural changes. What changed is the **resolution of open questions** that previously sat at the bottom of the spec:

- **Open Q#1 closed:** snippet selection heuristics formalised — files under `examples/`, `cookbook/`, `recipes/` are snippet candidates by default; otherwise functions/classes with substantial docstrings.
- **Open Q#3 closed:** when both markdown and PDF copies of a whitepaper exist, index the markdown only.
- **Open Q#4 closed:** when a project has both a `README.md` and a richer `docs/` site, both are indexed; ranking handles the dedup. No explicit "prefer docs" rule.
- **Open Q#6 closed:** cross-project links (`see_also` / `supersedes`) are not added as schema fields. Cross-project retrieval works via semantic match; complementary content surfaces from multiple projects without explicit linking.
- **License handling clarified:** `license` is optional (omit when absent) and accepts SPDX expressions (e.g. `"CC-BY-4.0 AND Apache-2.0"`) for dual-licensed repos.
- **Nested-manifest rule tightened:** a nested `pyproject.toml`/`package.json`/etc. produces its own package entry **only if it declares an installable artifact** — tool-config-only manifests (e.g. `pyproject.toml` with only `[tool.pytest]`) do not.
- **Candidate fields moved to a dedicated doc:** `_docs/candidate-changes.md` is now the single source of truth for deferred and rejected schema changes. This spec no longer carries a candidates section.

Open questions still on the table are listed at the end of this doc.

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

## Schema discipline (working principle)

Candidate fields stay deferred unless a real query — phrased in the user's voice — demonstrably fails or degrades without them. Project-shape alone is not evidence; a concrete prompt is. Candidate changes (deferred and rejected) are tracked in [`candidate-changes.md`](candidate-changes.md), not in this spec.

After four project walks against v0.0.2 — three of them re-evaluated against the ten prompts in [`evaluation-prompts.md`](evaluation-prompts.md) — zero candidate fields have met the promotion threshold. This release stays clean.

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
  "schema_version": "0.0.3",
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
- **`license` is optional.** Omit the field entirely when absent (e.g. no `LICENSE` file and no `license` field in package manifests). Do not write `"license": null`. Accepts **SPDX expressions** for dual-licensed projects: a plain SPDX ID (`"Apache-2.0"`) is the common case; an expression (`"CC-BY-4.0 AND Apache-2.0"`) handles dual-license repos. The indexer does not parse the expression; consumers may.

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

The enum is closed for v0.0.3; extend it via a versioned schema bump if real projects don't fit.

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
- **Embed:** `summary`, `install` (so retrieval can match install-method queries like "Claude plugin for security").
- **Store:** `entrypoints`, `public_api`, `path`, `id`.
- `content_hash` covers the inputs that produced `summary`. Re-indexing skips entries whose hash is unchanged.

## `snippets.jsonl`

One line per notable code pattern. Answers **"is there code I can copy?"**

Each snippet has a single `language` — per the granularity rule, a multi-language example becomes multiple snippet entries.

### Snippet selection heuristics

A file is a snippet candidate if any of the following hold:

- It lives under `examples/`, `cookbook/`, or `recipes/` at any depth. One snippet entry per file is the default.
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
- `depends_on` lists the imports the snippet uses (not the file's full import block), so queries can avoid pasting code that pulls in heavy deps.

## `references.jsonl`

One line per **doc chunk or structured content artifact**. Answers **"what context should I load?"**

This corpus carries everything that's read-for-context: README chunks, doc-site pages, whitepapers, rules, skills, prompts, checklists, structured data items (e.g. individual entries from a YAML data file). The same knowledge can come in different forms — a whitepaper section and a structured rule may both teach safe deserialization. We distinguish them by **form**, not by category.

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
- **Minimum chunk size ~200 characters.** Tiny stub sections (e.g. `## Installation\n\nSee below.`) collapse into their parent.
- **Structured data files (YAML lists of items)** are decomposed into one entry per item, not one entry per file. A `risks.yaml` with 28 items produces 28 reference entries.
- **When markdown and PDF copies of the same document exist, index the markdown only.** Detection: same basename, `.md` and `.pdf` adjacent. The PDF is skipped.
- **READMEs and docs-site sources coexist.** A project may have both `README.md` and a `docs/` site that overlap; both are indexed; ranking handles dedup. No explicit "prefer docs" rule.

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

After four walks, only a few open questions remain — all small, none blocking:

1. **Maximum chunk size and sub-splitting rules** for very long sections. Tentative ~1500 tokens; not yet validated against retrieval results.
2. **Notebook (`.ipynb`) handling** — treat as a snippet candidate? ws2-defenders has `aitf_colab_demo.ipynb`; not yet walked deeply.
3. **`status` auto-derivation** — currently declared, default `active`. Revisit if a project actually needs `archived` and human declaration proves burdensome.
4. **Image/SVG content with meaningful text** (e.g. secure-ai-tooling's risk-map graph). Currently skipped; revisit if image embeddings come into scope.

Closed since v0.0.2: snippet heuristics (resolved via `examples/` convention); whitepaper PDFs (resolved via markdown-only rule); README vs docs (resolved as "both, let ranking handle it"); cross-project links (resolved as not needed — semantic match works).
