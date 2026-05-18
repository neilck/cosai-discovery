# Indexer Notes

Captured during the project walkthroughs by simulating what the indexer would have to do. These are practical hints, edge cases, and unresolved issues for whoever builds the indexer — separate from the format/tool-surface specs because they're implementation-side concerns, not schema decisions.

Not a spec. Bullet-point form, intentionally rough.

---

## Project detection & boundaries

- **"Project = repository" is the working boundary.** Even when a repo contains a flagship sub-project (e.g. AITF inside ws2-defenders), the manifest belongs to the outer repo. Sub-projects surface via their own package entries, not their own `.cosai-index/`.
- **Empty corpora are zero-line files, not missing files.** `packages.jsonl` with no entries still exists; the indexer creates it. Makes "did we run yet?" testable.
- A repo that fails to produce a `.cosai-index/manifest.json` (because the indexer crashed mid-run) should leave partial state cleanly removable. Write atomically (`manifest.json.tmp` → rename) so the index is never half-written.

## Discovering packages

- A nested package manifest (`pyproject.toml`, `package.json`, `go.mod`, `Cargo.toml`, `.claude-plugin/plugin.json`) produces its own entry **only if it declares an installable artifact**:
  - `pyproject.toml` — requires `[project]` table with `name` (NOT just `[tool.pytest]` or `[tool.coverage]`).
  - `package.json` — requires `name` field. If `private: true`, skip unless it's the only project manifest.
  - `go.mod` — always qualifies.
  - `Cargo.toml` — requires `[package]` table (not just `[workspace]`).
  - `.claude-plugin/plugin.json` — always qualifies; produces `ecosystem: "claude-plugin"`.
- **Don't treat `pyproject.toml` files that only configure tools as package manifests.** secure-ai-tooling has one of these at the root; it's not a package.
- **Workspace / monorepo manifests are not package entries themselves** — only their member projects are. `Cargo.toml` with `[workspace]` only → recurse into members.
- Discovering sub-packages requires walking the tree; don't rely on glob patterns alone. Stop recursing into `node_modules/`, `.git/`, `venv/`, etc. (baseline ignore — see below).

## Snippet discovery

- **By default, treat files under `examples/`, `cookbook/`, `recipes/` as snippet candidates** — one snippet entry per file. Confirmed via ws2-defenders' `telemetry/examples/`.
- For other files: functions/classes with substantial docstrings (≥ ~200 chars) are candidates. Detection is language-specific — use language parsers, not regex.
- An explicit comment marker (e.g. `# cosai-index: snippet` or `// cosai-index: snippet`) **opts a non-default location in**. The reverse marker (`# cosai-index: ignore`) **opts a default location out**.
- Don't extract snippets from generated code or test files by default. Tests sometimes have the cleanest API examples — but indexer can't tell which, so default ignore.
- One file under `examples/` = one snippet entry. Don't split into multiple snippets per file unless the file has obvious sub-units (multiple top-level `if __name__ == "__main__"` blocks, etc.).
- `language` for a snippet is the file's language. `depends_on` is the set of imports actually used in the snippet, not the file's full import block.

## Reference discovery & chunking

- **Chunk-per-heading is the default for markdown.** Confirmed across codeguard-cli (12-section README), ws2-defenders (whitepapers with deep TOCs), project-codeguard (MkDocs site).
- **Minimum chunk size ~200 characters.** Tiny stub sections (e.g. `## Installation\n\nSee below.`) collapse into their parent.
- Maximum chunk size: TBD. A 36KB README section (telemetry/README.md has these) probably needs sub-splitting on H3/H4 boundaries. Pick a target token count (~1500?) and split deeper when exceeded.
- **`section_path` is the H1→Hn breadcrumb.** Include all levels even if the H1 is implicit (the document title).
- **Skip auto-generated content by detection where reasonable**: files in `dist/`, `build/`, `out/`, files matching `AUTO-GENERATED` markers in their first few lines, files declared as outputs in pre-commit hooks. Otherwise rely on the baseline ignore.
- **When markdown and PDF copies exist for the same whitepaper, index the markdown only.** Confirmed via ws2-defenders' approved whitepapers. Detection: same basename, `.md` and `.pdf` adjacent. PDF gets baseline-ignored.
- **Don't index `.svg` files even though they may contain meaningful text.** Image embeddings are out of scope.

## Structured content (YAML, schema-driven data)

- **Decompose structured data files into one entry per item.** secure-ai-tooling's `risks.yaml` produces 28 reference entries, not one. Resolved Q-A2 — fine-grained is the rule.
- Detection: a YAML file whose top level is a list of objects each with an `id` field is structured data. Each item gets its own entry.
- **The item's `id` field becomes part of the entry's `id`** (e.g. `ref:secure-ai-tooling/risks/riskDataPoisoning`). This makes cross-references inside the YAML resolvable later.
- `form: "structured"` for these entries.
- `structure_description` is generated from a **per-schema template** when known (e.g. secure-ai-tooling has a `.schema.json` for each YAML file; project-codeguard rule frontmatter has a known shape). Fall back to LLM-generated description if no template registered.
- **Lift filter-worthy frontmatter/field values into `tags`.** Languages, severity, framework names, etc.

## Lift frontmatter `status` into tags when present

When a source document has frontmatter declaring `status: "Approved"`, `status: "Draft"`, or similar (ws4's whitepapers do this — `status: Approved` in their YAML frontmatter), the indexer should lift that value into entry-level `tags` (e.g. `tags: [..., "approved"]` or `tags: [..., "draft"]`).

This gives query-side users an opt-in filter via the existing `tags` mechanism — `search(filters={tag: "approved"})` works without any new schema field. The lift happens at index time, costs nothing at query time, and preserves an existing source-of-truth signal that would otherwise be ignored.

Note: this is *not* the same as `manifest.status`. The manifest-level status flags whole-repo draft state (ws3-ai-risk-governance has `status: "draft"`). The per-entry tag lift handles individual documents within an otherwise-active repo (a draft whitepaper inside an active workstream).

This was C7's only durable lesson before C7 was rejected as a candidate field — the source data is already there; it just needs to be carried through.

## Workspace-specific terminology must survive into summaries

When a project's README or docs carry workspace-specific language (e.g. "CoSAI whitepaper," "CoSAI branding," "CoSAI Risk Map," "OASIS Open Project"), the LLM-generated summary must preserve those terms rather than generalize them away. A summary that paraphrases "CoSAI whitepaper converter" into "Markdown-to-PDF tool" loses the workspace-discovery signal — a user querying "how do I render a CoSAI whitepaper?" would no longer match on the summary.

**Rule for summary generation:** project-name, workspace-name, and workspace-convention terms in the source content must appear verbatim in the summary at least once. Treat them as load-bearing nouns, not stylistic noise to compress.

This came out of the cosai-whitepaper-converter walk. The project's value depends entirely on it being recognizable as *the workspace's* whitepaper tool — generic phrasing in the summary would hide it from production-use queries even though semantic match would still hit on adjacent terms like "Markdown" and "PDF."

**Adjacent observation worth tracking (not yet a candidate):** the schema doesn't currently capture "this project is the workspace's canonical tooling for X" as a structured signal. Semantic match handles it today because each workspace convention has one obvious provider, but a future workspace with competing tools would need a structured way to express "use this one for whitepapers." Park as a notional candidate; revisit if/when a workspace has multiple tools for the same convention.

## Summaries (the embedded prose)

- **Summaries are LLM-generated unless deterministic content suffices.**
  - Package summary: README first paragraph + entrypoint docstring → LLM rewrite.
  - Snippet summary: function docstring + signature → LLM rewrite if docstring is thin.
  - Reference (prose) summary: first ~500 chars of the chunk + heading path → LLM rewrite.
  - Reference (structured) summary: the item's `shortDescription` or `description` field → use directly when present, LLM rewrite if it's too long.
- **Use Haiku for summary generation by default.** Cost-sensitive operation, doesn't need Opus.
- **Cache LLM responses by content hash.** Re-running `build_index` should be near-free if nothing changed.
- **Summary should be 1–3 sentences.** Longer summaries dilute embedding signal.

## `content_hash` strategy

- Hash the **inputs** that produced the embedded fields, not the embedded fields themselves. Otherwise a regenerated summary always invalidates the hash.
- For packages: hash `{manifest_file_contents, README_chunk_used, entrypoint_docstrings}`.
- For snippets: hash `{file_contents_at_line_range, language}`.
- For references: hash `{chunk_contents, structure_description_inputs}`.
- Use SHA-256 truncated to ~16 hex chars in the entry; full hash if needed.

## Manifest fields the indexer derives

- `languages` — union of `language` across all entries. Don't ask the project to declare.
- `counts` — populated by counting entries written.
- `last_indexed` — current UTC timestamp at end of run.
- `last_commit` — from `git log -1` if it's a git repo; omit otherwise.
- `default_branch` — from `git symbolic-ref refs/remotes/origin/HEAD` if available; default `"main"`.
- `repo_url` — from `git remote get-url origin`.
- Everything else (`description`, `primary_kind`, `also`, `tags`, `owners`, `status`, `license`) is either project-declared (in a `.cosai-index/config.yaml` if we end up needing one) or LLM-suggested + human-confirmed on first run.

## License handling

- **License field accepts SPDX expressions, not just IDs.** Single-license: `"Apache-2.0"`. Dual-license: `"CC-BY-4.0 AND Apache-2.0"` (valid SPDX expression syntax). Confirmed via ws2-defenders.
- **License is optional. Omit when absent.** Don't write `"license": null` or `"license": ""`. Confirmed via codeguard-cli (no LICENSE file).
- Detection: check `LICENSE`, `LICENSE.md`, `LICENSE.txt` at root, then `license` field in `pyproject.toml` / `package.json`. Multiple sources may disagree — prefer the explicit `LICENSE` file.

## `primary_kind` + `also` inference

- The indexer should **propose** values but require human confirmation on first run.
- Detection signals:
  - `primary_kind: "library"` if `packages.jsonl` has entries and project has no CLI/service deliverables.
  - `primary_kind: "cli"` if a package declares a console script entry point and the project's README leads with CLI usage.
  - `primary_kind: "service"` if `mcp-server`, `docker-compose.yml` at root, or service entrypoint detected.
  - `primary_kind: "ruleset"` if a directory called `rules/`, `policies/`, or `guidance/` contains most content.
  - `primary_kind: "dataset"` if structured YAML/JSON data files are the largest content category and there's no CLI.
  - `primary_kind: "docs"` if `docs/` dominates and there are no installables.
  - `primary_kind: "whitepaper"` if root has one or two prominent markdown files representing approved papers.
  - `primary_kind: "working-group"` if README explicitly identifies the repo as a CoSAI workstream.
- `also` is everything else that's present. ws2-defenders is the canonical messy case: `primary_kind: "working-group"`, `also: ["whitepaper", "library", "dataset"]`.

## Baseline ignore list

The indexer always skips these regardless of project config:
- `.git/`, `.svn/`, `.hg/`
- `node_modules/`, `bower_components/`
- `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `*.egg-info/`
- `venv/`, `.venv/`, `env/`, `.env/`
- `dist/`, `build/`, `target/`, `out/`, `.next/`
- `*.lock`, `package-lock.json`, `uv.lock`, `Cargo.lock`, `Gemfile.lock`, `poetry.lock`
- `*.pdf` (when an adjacent `.md` exists with the same basename — see whitepaper rule)
- `*.svg`, `*.png`, `*.jpg`, `*.jpeg`, `*.gif`, `*.webp` (until image embeddings are in scope)
- `*.excalidraw`, `*.drawio`, `*.vsdx` (diagram source formats — binary/JSON, no useful text for embedding)
- `*.pyc`, `*.class`, `*.o`, `*.so`, `*.dylib`, `*.dll`
- `coverage/`, `.coverage`, `htmlcov/`

If a project legitimately needs to index something on this list (e.g. a `dist/` that's hand-curated), the project can override via a future config.

## Cross-project considerations

- **The indexer runs per-project.** It produces `.cosai-index/` in one repo. The MCP server is what stitches multiple projects' indexes together.
- **Don't try to detect cross-project duplicates at index time.** codeguard-cli's `rules/` snapshot is byte-identical to project-codeguard's, but the indexer running on codeguard-cli has no awareness of project-codeguard. If we promote `canonical_source` later, the cross-project link is set **at query time** or via a separate "stitch" step, not during per-project indexing.

## Schema-side problem worth flagging: closed enums don't scale across niches

Today, several fields use closed enums: `ecosystem` (pypi, npm, claude-plugin, mcp-server, ...), `relationship` in `builds_on` (extends, implements, consumes, cites, donated_from), and `primary_kind` (library, cli, ruleset, whitepaper, ...). Each is baked into the spec. Adding a value requires a schema version bump.

**The problem:** different communities and industries need different niche-specific values. A finance-industry workspace might need `ecosystem: "compliance-policy-bundle"`; an infra workspace might need `ecosystem: "terraform-module"`; a documentation-heavy community might need `primary_kind: "standards-track"`. Forcing one closed enum across all communities is the wrong abstraction for a federated ecosystem. We already see this pressure within COSAI: each project walk has surfaced one or two new niche values (`claude-plugin`, `mcp-server`, now `devcontainer-feature` from cosai-whitepaper-converter).

**Sketched direction (not designed):**
- Manifest declares a `namespaces` block, mapping enum-bearing fields to a namespace identifier (e.g. `"ecosystem": "cosai-core@1"`).
- An MCP server tool (`get_namespace_definitions` or similar) returns the value definitions for a namespace, so the model can look up what an unfamiliar `ecosystem` value means rather than relying on training data.
- Namespaces can `extends` a parent namespace — a community-specific namespace adds values without redefining existing ones.
- Defaults preserve backwards compatibility: a manifest with no `namespaces` block uses the bundled `cosai-core` namespace at the indexer's version.

**Why not designed yet:** the COSAI workspace has only ever needed one namespace's worth of values. Designing namespace mechanics speculatively risks over-engineering. The closed enum has been adequate through 9 project walks; the structural pressure is real but not yet retrieval-failing in a way that motivates an immediate design pass. Flag and defer until a second community needs the system or until adding `ecosystem` values becomes a frequent enough operation to justify the indirection.

**What would force the design pass:**
- A second workspace (non-COSAI) wanting to use the MCP server.
- Three or more closed-enum bumps in a short window.
- A prompt where the model fails to interpret an unknown enum value and needs a definition lookup.

Until then, treat this as a known limitation of the closed-enum approach. Add new values via schema version bumps as usual.

## Open implementation questions

- **Per-project config file?** Some decisions (project-declared status, `primary_kind` override, custom ignore globs, custom snippet markers) need a place to live. Options:
  - Extend `manifest.json` with an `indexing` block (project declares preferences alongside manifest data).
  - Separate `.cosai-index/config.yaml`.
  - Inline frontmatter on individual files.
  - **Tentative:** add fields to `manifest.json` as needed; resist a separate config file until 3+ unrelated settings exist.
- **How does `build_index` handle merge conflicts on `.cosai-index/*`?** Re-running should be idempotent — same inputs produce same outputs (modulo timestamps). LLM-generated summaries with temperature > 0 break this. Either pin temperature to 0 for indexer LLM calls, or cache by content hash so re-runs return the cached summary.
- **What happens when the LLM provider is unavailable?** Three options: (a) abort; (b) write entries with empty summaries and mark `incomplete: true`; (c) use deterministic fallback summaries (first N chars of content). Pick one and document. Tentative: (a) abort, surface a clear error.
- **Streaming progress for large repos.** ws2-defenders has 100+ chunks across whitepapers + framework reviews + telemetry docs. Per-chunk LLM calls × 100 = real wall time. Indexer needs progress reporting (compatible with the `build_index` MCP tool's response).
- **`build_index` returning partial results vs. all-or-nothing.** Tentative: all-or-nothing per corpus. If references partially failed, don't half-update `references.jsonl`. Easier rollback.

## Worth deciding before any code

- LLM provider for summary generation: Anthropic (Haiku) by default? User-configurable? Where does the API key live?
- Embedding provider: Voyage (decided). Where does its API key live?
- Where does the vector store live? `cosai-discovery/.data/index.db` (SQLite + sqlite-vec). Confirmed.
- Should the indexer commit `.cosai-index/*` automatically? Tentative: no — write the files, let the user commit. Avoids surprise commits.
- Logging: structured JSON to stderr? Required for the MCP tool wrapper.

## Misc

- **Don't index `cosai-discovery` itself for now.** The MCP server is the consumer; indexing its own docs creates a circular bootstrap. Revisit once the project has substance.
- **PDF text extraction is a non-trivial step** if we ever do support PDF-only projects. `pdfminer.six` or `pypdf` works; quality varies. Punt until needed.
- **Notebook (`.ipynb`) handling:** ws2-defenders has `aitf_colab_demo.ipynb`. Treat as a snippet candidate; extract code cells + leading markdown as the summary. Don't embed cell outputs.
