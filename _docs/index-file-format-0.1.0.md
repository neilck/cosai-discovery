# COSAI Discovery — Index File Format

**Version:** 0.1.0

## Purpose

COSAI Discovery makes a workspace of related projects discoverable to AI coding agents. Each project commits an **index** — a structured, embeddable description of what it contains — to its own repository. The MCP server reads these indexes across the workspace, embeds them, and answers queries from agents working in any one project about what exists in the others.

This document specifies the file format of that per-project index. It is the contract between:

- **Indexer tools** that scan a project and produce the files.
- **The MCP server** that consumes the files, embeds them, and serves queries.
- **AI agents** that issue queries (via the MCP server) and read the results.

The index is designed to serve four agent goals:

1. Decide whether to write new code or import an existing package.
2. Decide whether to copy an existing pattern instead of writing new code.
3. Load reference material into planning-mode context.
4. Answer user questions about other projects in the workspace.

## Structure

Every project contains a `.cosai-index/` directory at its root with four files:

```
<project-root>/
  .cosai-index/
    manifest.json           # project-wide metadata
    packages.jsonl          # one line per installable package
    snippets.jsonl          # one line per copyable code pattern
    references.jsonl        # one line per doc chunk or structured artifact
```

**The manifest** describes the project as a whole. The MCP server uses it for project-level discovery (`list_projects`) and filtering.

**The three JSONL files** describe the project's contents at the granularity an agent would consume them. Each line is a self-contained JSON object that can be filtered, retrieved, and embedded on its own merits. Empty corpora are zero-line files, not missing files — a docs-only project still has `packages.jsonl` and `snippets.jsonl` as empty files.

### Why three corpora

The three files answer three different agent questions:

- **`packages.jsonl` — "Can I depend on this?"** Importable units the agent could install or run.
- **`snippets.jsonl` — "Is there code I can copy?"** Notable patterns the agent could adapt.
- **`references.jsonl` — "What context should I load?"** Doc chunks, rules, frameworks, structured items the agent should read.

Separate files mean the MCP server can scope a query to one of these intents cheaply. Filter values map directly to per-file behaviour; the three intents don't share search semantics.

## Design rules

Two rules govern every field in this spec. They apply to indexer authors deciding *what* to write, and to schema extensions deciding *what to add*.

### Rule 1 — Embed / filter / store

Every field declares its purpose by how it's used:

- **embed** — included in the embedding input; contributes to semantic match. Free text.
- **filter** — used as a hard filter at the vector store. Enumerated strings or simple scalars.
- **store** — reference data the model reads after retrieval. Not embedded, not filtered. Used for navigation (`path`, `lines`, IDs).

When a value needs *both* semantic match and hard filterability — e.g. languages on a multi-language rule — split it: filter values go in `tags`, semantic context goes in `summary` or `structure_description`. The same source feeds both destinations.

### Rule 2 — Granularity at the entry, summary at the manifest

Each entry in `packages.jsonl`, `snippets.jsonl`, and `references.jsonl` must be specific enough that filterable fields have a single, unambiguous answer. A Go-backend / TypeScript-frontend project produces **two** package entries, not one with `languages: ["go", "typescript"]`. A YAML file with 28 risk items produces 28 reference entries, not one entry pointing at the file.

The manifest **summarises** the project. The entries are the **truth**. `search` filters always apply at the entry level; `list_projects` filters apply at the manifest level for coarse discovery only.

## `manifest.json`

Singleton, project-wide. Used by `list_projects` for discovery and by manifest-level filters.

```json
{
  "schema_version": "0.1.0",
  "project": "<slug>",
  "path": "<rel-path-from-workspace>",
  "description": "<one-paragraph project description>",

  "languages": ["..."],
  "primary_kind": "library | cli | service | claude-plugin | ruleset | docs | whitepaper | working-group | dataset | template | other",
  "primary_kind_other": "<free-text label, required when primary_kind == 'other'>",
  "also": ["..."],

  "license": "<SPDX expression, optional>",
  "status": "active | archived | draft",
  "owners": ["..."],
  "tags": ["..."],

  "repo_url": "<url>",
  "default_branch": "main",

  "related_urls": ["..."],

  "last_commit": { "sha": "...", "date": "<iso-8601>" },
  "last_indexed": "<iso-8601>",

  "counts": { "packages": 0, "snippets": 0, "references": 0 }
}
```

### Field reference

| Field | Purpose | Notes |
|---|---|---|
| `schema_version` | store | Version of this spec the index conforms to. |
| `project` | filter | Slug. Must be unique within the workspace. |
| `path` | store | Path relative to the workspace root. |
| `description` | embed | One paragraph. Names what the project is and what it produces. |
| `languages` | filter | **Derived union** of implementation languages from all entries. Used only by `list_projects` for coarse discovery. Empty array for docs-only projects. |
| `primary_kind` | filter | Single value. The consumer-facing answer to "what did I get?" |
| `primary_kind_other` | store | Required when `primary_kind == "other"`, forbidden otherwise. Free-text label. |
| `also` | filter | Array of additional kinds the project ships. Matches as `primary_kind == X OR also contains X`. |
| `license` | filter | Optional. Accepts SPDX expressions (e.g. `"CC-BY-4.0 AND Apache-2.0"`). Omit the field if absent — do not write `null`. |
| `status` | filter | Declared by the project, default `active`. Not auto-derived. |
| `owners` | store | Free-form list of maintainers or workstream leads. |
| `tags` | filter | Free-form. Lifted from project-level conventions and workspace-specific terminology. |
| `repo_url` | store | Source repository URL. |
| `default_branch` | store | Typically `main`. |
| `related_urls` | store | Repository URLs referenced from this project's README. Free-form; no structural relationship implied. See [`related_urls`](#related_urls). |
| `last_commit` | store | SHA + ISO-8601 date of most recent commit at index time. |
| `last_indexed` | store | ISO-8601 timestamp when the index was last written. |
| `counts` | store | Entry counts per corpus. Derived. |

### `primary_kind` and `also` enum

| Value | Meaning |
|---|---|
| `library` | Importable code package. |
| `cli` | Command-line tool. |
| `service` | Runnable server (MCP server, HTTP service, daemon). |
| `claude-plugin` | Claude Code plugin or skill bundle. |
| `devcontainer-feature` | VS Code devcontainer feature (installed into a build environment to provide tools). |
| `ruleset` | Structured guidance content (rules, prompts, policies). |
| `docs` | Documentation site. |
| `whitepaper` | Single-document research output. |
| `working-group` | Meeting notes, charters, governance artifacts. |
| `dataset` | Structured non-code data. |
| `template` | Repo or content template for downstream use. |
| `other` | Project genuinely doesn't fit any value above. Requires `primary_kind_other`. |

Prefer a defined value over `other` whenever one fits honestly. Use `other` as the escape hatch for genuine long-tail cases (e.g. a VS Code extension, a Terraform module, a non-software artifact); inventing a value via `other` is cheaper than expanding the enum each time a niche shape appears.

### `primary_kind_other`

Required when `primary_kind == "other"`, forbidden otherwise. A short free-text label naming the project's kind in the author's own words. Examples: `"vs-code-extension"`, `"terraform-module"`, `"jupyter-tutorial-collection"`.

The MCP server doesn't validate or enumerate these values; they're descriptive metadata for the model to read. Recurring values across multiple projects are evidence that a new enum value may be worth adopting in a future schema bump.

### `related_urls`

A free-form array of repository URLs referenced from this project's `README.md`. The intent is to preserve **structural connection signals** without claiming a relationship type:

- A workstream README that links to its umbrella governance repo.
- A CLI that links to the upstream whose rules it consumes.
- A whitepaper that cites another paper's repo for context.
- An external dependency mentioned in the README.

The array is populated by the indexer from `README.md` content. Each entry is a full URL exactly as it appeared in the README (the indexer does not normalise paths). External repos are allowed; the field is not workspace-scoped.

This field replaces an earlier `builds_on` field that attempted to encode a typed relationship enum. Across ten projects, the typed form proved unreliable to populate consistently. URLs in a README are a more honest signal: they're either present in the source or they aren't.

#### Example

```json
"related_urls": [
  "https://github.com/cosai-oasis/project-codeguard",
  "https://github.com/cosai-oasis/secure-ai-tooling/tree/main/risk-map",
  "https://github.com/cosai-oasis/oasis-open-project"
]
```

## `packages.jsonl`

One line per **importable or installable unit**. A project with multiple installables produces multiple entries — sub-`pyproject.toml`, separate `package.json` per workspace, mixed-language stacks all decompose.

### What counts as a package

A nested manifest produces its own entry **only if it declares an installable artifact**:

| Manifest | Counts when |
|---|---|
| `pyproject.toml` | Contains `[project]` table with a `name`. Tool-config-only files (just `[tool.pytest]`, `[tool.coverage]`) do not. |
| `package.json` | Contains a `name` field. `"private": true` skips unless it's the only project manifest. |
| `go.mod` | Always. |
| `Cargo.toml` | Contains `[package]` table. `[workspace]`-only manifests recurse into members. |
| `.claude-plugin/plugin.json` | Always. Produces `ecosystem: "claude-plugin"`. |
| `devcontainer-feature.json` | Always. Produces `ecosystem: "devcontainer-feature"`. |

### Entry shape

```json
{
  "id": "pkg:<project>/<name>",
  "category": "package",
  "kind": "library | cli | service | claude-plugin | devcontainer-feature | other",
  "name": "<name>",
  "language": "<implementation language>",
  "ecosystem": "pypi | npm | go | cargo | source | vendor | claude-plugin | mcp-server | devcontainer-feature | none",
  "version": "<semver or null>",
  "entrypoints": ["..."],
  "public_api": ["..."],
  "path": "<rel-path>",
  "install": "<copy-pasteable install command>",
  "summary": "<embedded prose>",
  "tags": ["..."],
  "content_hash": "sha256:..."
}
```

### Field reference

| Field | Purpose | Notes |
|---|---|---|
| `id` | store | Stable identifier: `pkg:<project>/<name>`. |
| `category` | filter | Always `"package"`. Shared across all JSONL files; see [`category` values](#category-values). |
| `kind` | filter | What the package is (library, cli, service, etc.). Uses the same enum as manifest `primary_kind`. See [`kind` values](#kind-values). |
| `name` | filter | Package name as it would be installed or imported. |
| `language` | filter | Implementation language. Single value per entry — Rule 2. |
| `ecosystem` | filter | Where and how the package is installed. See enum below. |
| `version` | filter | Semver if declared; `null` otherwise. |
| `entrypoints` | store | CLI commands, main functions, console scripts. |
| `public_api` | store | Exported symbols worth knowing about. Not exhaustive. |
| `path` | store | Repo-relative path to the package's root. |
| `install` | embed | Copy-pasteable install command. Embedded so retrieval can match install-method queries. |
| `summary` | embed | 1–3 sentences. What the package does, who would use it. |
| `tags` | filter | Free-form. |
| `content_hash` | store | SHA-256 of the inputs that produced `summary`. Re-indexing skips entries whose hash is unchanged. |

### `ecosystem` enum

| Value | Meaning | Install hint |
|---|---|---|
| `pypi` | Published to PyPI. | `pip install <name>` |
| `npm` | Published to npm. | `npm install <name>` |
| `go` | Go module on proxy.golang.org. | `go get <path>` |
| `cargo` | Published to crates.io. | `cargo add <name>` |
| `source` | Installable from this repo by source build. | `pip install .` or equivalent. |
| `vendor` | Meant to be copied into the consumer's tree. | "Copy file(s) X into your project at Y." |
| `claude-plugin` | Claude Code plugin or skill bundle. | `/plugin install …` or via marketplace. |
| `mcp-server` | Runnable MCP server. | "Configure in `mcpServers` block." |
| `devcontainer-feature` | VS Code devcontainer feature published to a container registry. | "Add to `devcontainer.json` features: `ghcr.io/.../feature-id:version`." |
| `none` | Not meant for external consumption. | n/a |

Single value per entry — pick the consumption-facing answer (how does a downstream user get and use this?). Install mechanics live in the free-text `install` field.

### `kind` values

| Value | Meaning |
|---|---|
| `library` | Importable code package. |
| `cli` | Command-line tool. |
| `service` | Runnable server (MCP server, HTTP service, daemon). |
| `claude-plugin` | Claude Code plugin or skill bundle. |
| `devcontainer-feature` | VS Code devcontainer feature (installed into a build environment to provide tools). |
| `ruleset` | Structured guidance content (rules, prompts, policies). |
| `docs` | Documentation. |
| `whitepaper` | Research output. |
| `working-group` | Meeting notes, governance artifacts. |
| `dataset` | Structured non-code data. |
| `template` | Template for downstream use. |
| `other` | Doesn't fit the above. Use sparingly. |

### `category` values

| Value | Meaning | File |
|---|---|---|
| `"package"` | Importable or installable unit. | `packages.jsonl` |
| `"snippet"` | Notable code pattern. | `snippets.jsonl` |
| `"reference"` | Doc chunk or structured artifact. | `references.jsonl` |

## `snippets.jsonl`

One line per notable code pattern. Each snippet has a single `language` — multi-language examples become multiple entries.

### What counts as a snippet

A file is a snippet candidate if any of these hold:

- It lives under `examples/`, `cookbook/`, `recipes/`, or `practical-guides/examples/` at any depth. One snippet entry per file.
- It is a Jupyter notebook (`.ipynb`) in any of those locations. The indexer extracts code cells + leading markdown for the summary. Supporting files (`utils.py`, fixture JSON, `assets/`) go into `depends_on`, not separate entries.
- It contains a top-level function or class with a docstring of at least ~200 characters.
- It carries an explicit `cosai-index: snippet` comment marker (opts a non-default location in).

A file is excluded if it carries `cosai-index: ignore` or sits under a test path (`tests/`, `__tests__/`, `*_test.go`, `test_*.py`).

### Entry shape

```json
{
  "id": "snip:<project>/<slug>",
  "category": "snippet",
  "kind": "library | cli | service | claude-plugin | devcontainer-feature | other",
  "title": "<short title>",
  "path": "<rel-path>",
  "lines": "<start>-<end>",
  "language": "<implementation language>",
  "summary": "<embedded prose>",
  "tags": ["..."],
  "depends_on": ["..."],
  "content_hash": "sha256:..."
}
```

### Field reference

| Field | Purpose | Notes |
|---|---|---|
| `id` | store | `snip:<project>/<slug>`. |
| `category` | filter | Always `"snippet"`. Shared across all JSONL files; see [`category` values](#category-values). |
| `kind` | filter | What kind of pattern this is (library, cli, service, etc.). Uses the same enum as manifest `primary_kind`. See [`kind` values](#kind-values). |
| `title` | embed | Short. Names the pattern. |
| `path` | store | Repo-relative path. |
| `lines` | store | Range within the file, e.g. `"42-118"`. |
| `language` | filter | The snippet's language. Single value — Rule 2. |
| `summary` | embed | What the pattern does, when to use it. |
| `tags` | filter | Free-form. |
| `depends_on` | store | Imports the snippet actually uses (not the file's full import block), plus same-directory supporting files for notebook snippets. |
| `content_hash` | store | SHA-256 of inputs producing `summary`. |

## `references.jsonl`

One line per **doc chunk or structured content artifact**. This corpus carries everything read-for-context: README chunks, doc-site pages, whitepapers, rules, skills, prompts, checklists, individual YAML data items.

The same knowledge can come in different forms — a whitepaper section and a structured rule may both teach safe deserialization. References distinguish them by **form**, not by category.

### Entry shape

```json
{
  "id": "ref:<project>/<doc>#<anchor>",
  "category": "reference",
  "kind": "docs | whitepaper | working-group | ruleset | dataset | other",
  "title": "<heading or artifact title>",
  "doc": "<rel-doc-path>",
  "section_path": ["H1", "H2", "..."],
  "path": "<rel-doc-path>",
  "lines": "<start>-<end>",

  "form": "prose | structured | mixed",
  "structure_description": "<embedded prose; describes the form>",

  "summary": "<embedded prose>",
  "tags": ["..."],
  "content_hash": "sha256:..."
}
```

### Field reference

| Field | Purpose | Notes |
|---|---|---|
| `id` | store | `ref:<project>/<doc>#<anchor>`. |
| `category` | filter | Always `"reference"`. Shared across all JSONL files; see [`category` values](#category-values). |
| `kind` | filter | What kind of reference this is (docs, whitepaper, ruleset, etc.). Subset of manifest `primary_kind`. See [`kind` values](#kind-values). |
| `title` | embed | Heading text or artifact title. |
| `doc` | store | Source document path. |
| `section_path` | store | Heading breadcrumb, e.g. `["Architecture", "Indexing", "Embeddings"]`. |
| `path` | store | Repo-relative path, usually same as `doc`. |
| `lines` | store | Line range within `doc`. |
| `form` | filter | See [`form` values](#form-values). |
| `structure_description` | embed | Short prose describing the form. Empty / omitted for `form: "prose"`. See [structured content](#structured-content). |
| `summary` | embed | 1–3 sentences. The content's meaning. |
| `tags` | filter | Free-form. |
| `content_hash` | store | SHA-256 of inputs producing `summary` and `structure_description`. |

#### `form` values

| Value | Meaning |
|---|---|
| `prose` | Flowing text — whitepapers, README sections, blog posts. |
| `structured` | Schema'd content with directives, bullets, or frontmatter — rules, checklists, controls, prompts, skill bundles, individual YAML data items. |
| `mixed` | Prose with embedded structured fragments. |

### Chunking rules

- **Markdown documents are chunked per heading.** Default H2 boundaries; sub-split on H3/H4 when a section exceeds ~1500 tokens.
- **Minimum chunk size ~200 characters.** Tiny stub sections collapse into their parent.
- **Structured data files (YAML lists of items) decompose into one entry per item.** A `risks.yaml` with 28 items produces 28 reference entries — one per item, not one per file. The item's `id` field becomes part of the entry's `id` (e.g. `ref:secure-ai-tooling/risks/riskDataPoisoning`).
- **When markdown and PDF copies of the same document exist, index the markdown only.** Detected by adjacent files sharing a basename.
- **READMEs and docs-site sources coexist.** Both are indexed when present; ranking handles overlap.

### Structured content

When a reference has `form: "structured"`, the `structure_description` field carries a short prose description of how the content is structured. It's written for an LLM consumer and embedded alongside `summary`.

Example for a unified rule with frontmatter:

> "A Project CodeGuard unified rule. Frontmatter declares applicable languages (c, java, javascript, php, python) and an alwaysApply flag. Body is organized into Requirements (bulleted directives), Security Impact (rationale), and Examples (avoid/prefer pairs)."

When the source has frontmatter or typed attributes, the indexer:

1. **Reflects their meaning in `structure_description`** so the embedding can match queries like "find me bulleted security rules I can apply quickly."
2. **Lifts filter-worthy values into `tags`** so they remain hard-filterable.

Example: a rule covering Python and Java becomes:
- `structure_description: "...applicable languages (java, python)..."` (embedded prose)
- `tags: ["python", "java", ...]` (filter values)

Same source, two destinations — Rule 1 in action.

## Embedding strategy

| Source | Model |
|---|---|
| `packages[].summary`, `packages[].install` | `voyage-code-3` |
| `snippets[].title`, `snippets[].summary` | `voyage-code-3` |
| `references[].title`, `references[].summary`, `references[].structure_description` | `voyage-3` |
| `manifest.description` | `voyage-3` |

`voyage-code-3` for code-bearing content; `voyage-3` for prose. Each `content_hash` covers the inputs that produced an entry's embedded fields. Re-indexing skips unchanged entries.

## Related documents

- [`mcp-tool-surface-X.Y.Z.md`](mcp-tool-surface-0.0.1.md) — the MCP server's query interface.
- [`indexer-notes.md`](indexer-notes.md) — implementation hints for indexer authors.
- [`candidate-changes.md`](candidate-changes.md) — schema changes considered but not adopted, with reasoning preserved.
