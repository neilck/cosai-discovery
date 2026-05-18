# Project Walkthrough Log

Tracks which workspace projects have been analyzed against the v0.0.1 index format, and what we learned from each.

## Status legend

- ⬜ Not started
- 🟡 In progress
- ✅ Analyzed — findings recorded
- 🔁 Re-analysis needed (format changed)

## Project queue

| # | Project | Status | Notes |
|---|---|---|---|
| 1 | project-codeguard | ✅ | See findings below |
| 2 | codeguard-cli | ✅ | See findings below |
| 3 | secure-ai-tooling | ✅ | See findings below |
| 4 | ws2-defenders | ✅ | See findings below |
| 5 | ws1-supply-chain | ⬜ | |
| 6 | ws3-ai-risk-governance | ⬜ | |
| 7 | ws4-secure-design-agentic-systems | ⬜ | |
| 8 | cosai-tsc | ⬜ | |
| 9 | cosai-whitepaper-converter | ⬜ | |
| 10 | oasis-open-project | ⬜ | |
| 11 | cosai-discovery (self) | ⬜ | Special — this is the host project |

## Findings per project

### 1. project-codeguard

**Analyzed:** 2026-05-18
**Commit:** `dddb5c3b` (2026-05-09)
**Repo:** https://github.com/cosai-oasis/project-codeguard

#### What's in the project

- **Top-level Python tool** (`project-codeguard` v1.3.1, Python ≥3.11) — converts unified markdown rules into formats for popular AI coding agents (Claude, Codex, Copilot, Cursor, Windsurf, etc.).
- **Sub-package**: `src/codeguard-mcp/` — its own `pyproject.toml`, exposes CoSAI CodeGuard rules as MCP tools over streamable HTTP. Independently versioned (v0.1.0).
- **Sources** (the curated content this project exists to ship):
  - `sources/rules/core/` — 24 unified-format rule markdowns
  - `sources/rules/owasp/` — 86 OWASP rule markdowns (110 rule files total)
  - `sources/skills/` — 2 reusable skills (`memory-safe-migration`, `security-review`) in claude-code-skill format
  - `sources/agents/` — `codeguard-reviewer` agent definition
  - `sources/templates/` — rule template
- **Packaged distributable**: `skills/software-security/SKILL.md` + bundled rules — a pre-packaged claude-code plugin (also referenced from `.claude-plugin/`).
- **Conversion code**: `src/formats/` — one Python module per target agent (claude, codex, copilot, cursor, etc.).
- **Docs site**: `docs/` + `mkdocs.yml` → published at project-codeguard.org.

#### How the v0.0.1 format maps onto this project

**Proposed `manifest.json`:**
```json
{
  "schema_version": "0.0.1",
  "project": "project-codeguard",
  "path": "project-codeguard",
  "description": "AI model-agnostic security coding agent skills framework and ruleset that embeds secure-by-default practices into AI coding workflows. Ships core security skills and rules, translators for popular coding agents, and validators.",
  "languages": ["python", "markdown"],
  "primary_language": "python",
  "license": "CC-BY-4.0",
  "status": "active",
  "project_kind": "mixed",
  "owners": ["@cosai-oasis"],
  "tags": ["cosai", "security", "secure-coding", "ai-coding-agents", "rules", "skills"],
  "repo_url": "https://github.com/cosai-oasis/project-codeguard",
  "default_branch": "main",
  "last_commit": {"sha": "dddb5c3b", "date": "2026-05-09T17:12:45-04:00"},
  "last_indexed": "2026-05-18T...",
  "counts": {"packages": 2, "snippets": ~8, "references": ~120}
}
```

**Proposed `packages.jsonl` (2 entries):**
- `pkg:project-codeguard/project-codeguard` (top-level tool, ecosystem: `none` — not on PyPI, installed via uv from source). Entrypoints: `src/converter.py`, `src/convert_to_ide_formats.py`, `src/emit_agents.py`, `src/validate_unified_rules.py`.
- `pkg:project-codeguard/codeguard-mcp` (ecosystem: `pypi`-style local, console script `codeguard-mcp`). MCP server.

**Proposed `snippets.jsonl`:** thin. Real "code snippets you'd copy" candidates are the per-format converter classes in `src/formats/*.py` (one pattern per agent type) — useful if someone is building a new converter. ~8 entries.

**Proposed `references.jsonl`:** the bulk of value here. ~110 rule files + ~5 skill/agent files + project README + docs site pages.

#### Findings — format issues surfaced

**F1. The 110 rule markdowns are neither "packages" nor "snippets" nor really "references" in the doc sense.**
They are **the product** of this project — structured, schema'd, parametric content (each has YAML frontmatter declaring `languages`, `description`, `alwaysApply`). Treating them as references means embedding their `description` field and surfacing them in `kind=references` queries. That works, but loses the structure.

**Options:**
1. Keep them in `references.jsonl` with rich `tags` (languages from frontmatter become tags). Cheap, lossy.
2. Add a fifth corpus, `assets.jsonl` (or `artifacts.jsonl`), for structured project-native content. Adds surface area.
3. Treat each rule as a **package** with `ecosystem: "codeguard-rule"`. Stretches the meaning of "package" but lets queries filter by ecosystem.

**Tentative recommendation:** option 1 for v0.0.2 — overload `references` with a `subtype` field. Revisit if more projects ship structured assets (likely).

**F2. Sub-packages with their own `pyproject.toml` need a clear rule.**
`src/codeguard-mcp/` is independently versioned, separately installable. v0.0.1 implies flat-list packages, which is fine — but we should make explicit that **a sub-`pyproject.toml` defines its own package entry**, regardless of nesting.

**F3. `project_kind` enum is insufficient.**
This project is `library` + `cli` + `docs` + ships "skills" + ships "rules". `mixed` is a true answer but useless for filtering. We need either:
- Multi-valued `project_kind` (array), or
- Drop `project_kind` and rely on tags + presence/absence of `packages`/`snippets`/`references` counts.

**Tentative recommendation:** make `project_kind` an array.

**F4. `ecosystem: "none"` is ambiguous.**
The top-level `project-codeguard` package isn't published anywhere but is installable from source. We should distinguish:
- `ecosystem: "source"` — installable from this repo (e.g. `uv pip install .`)
- `ecosystem: "vendor"` — copy files into your tree
- `ecosystem: "none"` — not installable code; the project just ships docs/rules

**F5. There's a "skills" concept that doesn't fit any of the three corpora cleanly.**
`sources/skills/security-review/` and `skills/software-security/` are markdown files with executable semantics (they're claude-code skill bundles, runnable). They are *more* than reference docs but *not* code snippets and *not* installable packages. Best v0.0.1 fit is `references`, but we lose the "this is a runnable artifact" signal.

**F6. Languages list in `manifest.json` understates reality.**
The project's Python code is in 1 language, but the rules cover ~20 languages. `manifest.languages` should probably distinguish:
- `code_languages`: the languages of the project's own source code
- `subject_languages`: the languages the project's *content* talks about

This matters for filtering: if a user asks "find me Python security rules", they want a rule that covers Python, not a rule written in Python.

**F7. Doc site pages duplicate README content.**
`docs/index.md`, `docs/getting-started.md` etc. are MkDocs sources; some overlap with `README.md`. The indexer needs a dedup story or a "canonical doc" convention.

**F8. `.claude-plugin/marketplace.json` is itself an indexable artifact.**
It declares a Claude Code plugin and could be relevant to "how do I install this CodeGuard thing?" queries. Currently no slot for plugin manifests. Probably absorb into `packages.jsonl` with `ecosystem: "claude-plugin"`.

#### Recommended schema changes for v0.0.2

1. `manifest.project_kind` → array (allow multiple kinds)
2. `manifest.languages` → split into `code_languages` and `subject_languages`
3. `packages.ecosystem` → add `source`, `vendor`, `claude-plugin` to the enum
4. `references` entries → add optional `subtype` field (e.g. `rule`, `skill`, `agent-definition`, `doc-chunk`, `whitepaper-section`) to preserve structure when overloading the corpus
5. Clarify: a nested `pyproject.toml` / `package.json` / `go.mod` always creates its own package entry
6. Add `executable: boolean` to `references` entries — flags runnable skills/agents distinct from passive docs

#### Open questions raised by this project

- Q1: Do we want a separate `assets.jsonl` corpus for structured project-native content (rules, prompts, skills) rather than overloading `references`?
- Q2: How should the indexer dedupe README vs. MkDocs docs site sources?
- Q3: For a project that *ships* claude-code skills, should those skills appear in `packages.jsonl` (installable) or `references.jsonl` (content)? Probably both, with cross-link via `see_also`.
- Q4: 110 rule files at one entry each = 110 vector rows. Is that the right granularity, or do we group by category (e.g. "owasp-injection" as one entry that references many rules)?

---

### 2. codeguard-cli

**Analyzed:** 2026-05-18 (against v0.0.2)
**Commit:** `98cbfa33` (2026-05-05)
**Repo:** https://github.com/neilck/codeguard-cli

#### What's in the project

A Python CLI tool that runs LLM-based security checks against source code using project-codeguard's rules. Single-package layout — much simpler than project-codeguard:

- **One Python package** at `codeguard/` with a `pyproject.toml` declaring `codeguard-cli` v1.0.0 and a console script `codeguard`.
- **CLI commands** (`check`, `scan`, `recheck`, `rules`) implemented in `codeguard/commands/` and wired up via `codeguard/cli.py`.
- **Supporting modules**: `checker.py` (LLM glue), `llm.py` (provider abstraction for Anthropic/OpenAI/Google), `rules.py` (rule loading), `updater.py` (downloads rules from upstream project-codeguard), `git.py`, `config.py`, `cli_helpers.py`.
- **Bundled rule snapshot** at `rules/` — 23 markdown files (the tier-0 + tier-1 set) copied from project-codeguard with identical frontmatter (`description`, `languages`, `tags`, `alwaysApply`).
- **Detailed README** documenting commands, config (`.codeguard.yaml`), text and JSON output schemas.
- **Example config** at `.codeguard.yaml.example`.

#### How the v0.0.2 format maps onto this project

**Proposed `manifest.json`:**
```json
{
  "schema_version": "0.0.2",
  "project": "codeguard-cli",
  "path": "codeguard-cli",
  "description": "Python CLI that uses an LLM to check source code against Project CodeGuard security rules. Provides check/scan/recheck commands with text and JSON output, plus a rules-version management command that fetches and caches rule sets from the upstream project-codeguard repository.",
  "languages": ["python"],
  "primary_kind": "cli",
  "also": [],
  "license": "<missing — no LICENSE file in repo>",
  "status": "draft",
  "owners": ["@neilck"],
  "tags": ["cosai", "codeguard", "security", "code-review", "llm", "cli"],
  "repo_url": "https://github.com/neilck/codeguard-cli",
  "default_branch": "main",
  "last_commit": {"sha": "98cbfa33", "date": "2026-05-05T21:26:32-07:00"},
  "last_indexed": "2026-05-18T...",
  "counts": {"packages": 1, "snippets": ~3, "references": ~30}
}
```

Note: the README explicitly says "99% AI-written, currently fails its own checks, never deploy." `status: "draft"` reflects this — the project is real but not production-ready by the author's own statement.

**Proposed `packages.jsonl` (1 entry):**
- `pkg:codeguard-cli/codeguard-cli` — `language: "python"`, `ecosystem: "source"` (no PyPI publish, installable via `pip install -e .`), entrypoint `codeguard.cli:cli`, console script `codeguard`. Single coherent unit — no decomposition needed.

**Proposed `snippets.jsonl` (~3 entries):**
- `snip:codeguard-cli/llm-provider-abstraction` — `llm.py`, multi-provider LLM wrapper (Anthropic/OpenAI/Google) with a uniform interface.
- `snip:codeguard-cli/file-hash-skip` — `recheck.py` + `checker.py`, SHA256-based skip-unchanged-files pattern.
- `snip:codeguard-cli/cached-rules-version-manager` — `updater.py`, "fetch versioned content from a GitHub repo and cache locally with version switching" pattern.

These are real, reusable patterns. Worth surfacing.

**Proposed `references.jsonl` (~30 entries):**
- ~25 README chunks (chunk-per-heading: About, Installation, Configuration, Usage/check, Usage/scan, Usage/recheck, Usage/rules, Output/text, Output/json, Requirements, Development).
- 23 bundled rule files in `rules/` — but **these are duplicates of project-codeguard's rules**. The interesting question.
- 1 chunk for `.codeguard.yaml.example`.

#### Findings — against v0.0.2

##### F-cli-1: Same rule content in two projects — duplication or first-class cross-project link?

The 23 rule files in `codeguard-cli/rules/` are byte-identical (or nearly so) snapshots of files in `project-codeguard/sources/rules/{core,owasp}/`. Both are `form: "structured"` references. If we index both:

- Query "deserialization rules" returns hits from **both** projects.
- The rule itself is the *same artifact*; the only project-discriminating signal is "this project ships a snapshot of it" vs. "this project authors it."

**Options:**
1. **Index both, accept the duplication.** Queries return both; ranking will surface the more relevant project depending on the query phrasing (e.g. "show me a CLI that checks for hardcoded credentials" → codeguard-cli; "what is the hardcoded credentials rule?" → project-codeguard).
2. **Don't index the snapshot.** codeguard-cli's `rules/` is a build artifact, not original content. Skip during indexing.
3. **Index but cross-link to the canonical source.** A new field `canonical_source: "ref:project-codeguard/rules/..."` on the codeguard-cli entries says "I'm a copy of that." Useful for dedup at query time and for "show me the upstream."

**Recommendation:** Option 3 — index but cross-link. Reasoning:
- codeguard-cli's `rules/` snapshot is *semantically meaningful*: it tells you what version this tool can check against without `codeguard rules download`. That's a real query: "what rules does codeguard-cli check by default?"
- Option 2 throws away that signal.
- Option 1 produces noisy dupes for the high-volume queries.
- Option 3 preserves the signal and lets the query side dedup or expand at will.

**This re-opens the `equivalents` / `canonical_source` field** that was deferred in v0.0.2 as Q-A1.2. We now have a second project producing evidence. Not promoting yet (need one more case), but this is the strongest pull so far.

##### F-cli-2: Schema-laden README JSON example

The README contains a ~70-line annotated JSON output schema (the `--format json` example with inline comments documenting every field). That's a high-value reference for any agent or developer working with codeguard-cli's output. By chunk-per-heading, it'd fall under the "Output / JSON output" section as one chunk.

It pushes the upper bound of `ingestibility` — large, dense, but structured and self-describing. The v0.0.2 spec correctly handles this: `form: "mixed"` (prose framing + a giant code block), no special schema beyond that.

But it does motivate the deferred `ingestibility` field somewhat — this chunk is "low" ingestibility for context-loading purposes (~2KB of JSON) but "high" for "I need to know the exact schema." That's two different uses, not two different ingestibilities. **The deferral still holds** — `ingestibility` would be a poor proxy here.

##### F-cli-3: `commands/` directory is a coherent sub-package, but not its own installable

`codeguard/commands/` has its own `__init__.py` and five command modules. Under the **nested manifest** rule from v0.0.2, this is *not* a separate package entry — no `pyproject.toml` lives there. Correct outcome: stays under the single `codeguard` package.

But it raises a sub-question: **should the indexer surface "sub-modules" of a package as separate entries?** Today, the package entry's `public_api` field would list things like `codeguard.cli:cli`, `codeguard.commands.check:check_command`, etc. — a flat list. The structure (commands grouped under `commands/`) is lost.

**Tentative answer:** the granularity rule says "decompose when filterable fields have different answers." `commands/` has the same language, same ecosystem, same role. No decomposition needed. If a future query needs "find me the `recheck` command code," that's a snippet, not a package — and we already plan snippet entries for distinctive patterns.

**No schema change motivated.** This is healthy — the v0.0.2 granularity rule held under a real test.

##### F-cli-4: Missing license

The repo has no `LICENSE` file. The v0.0.2 manifest declares `license` as an SPDX id; what do we put? `null`? Empty string? Omit the field?

**Tentative recommendation:** make `license` optional. When absent, omit from the manifest entirely (don't include `"license": null`). Document this. Document that `list_projects(filters={license: "..."})` won't return projects with no declared license. Don't try to derive (false-negative on permissively-licensed projects is worse than no answer).

This is a minor clarification, worth adding to v0.0.2 field notes but not a schema change.

##### F-cli-5: `status: "draft"` working as intended

The README explicitly says "99% AI-written, currently fails its own checks." This is the first concrete case of a non-`active` status. Confirms Q-B2's resolution: declared by the project, not auto-derived. The README sentence is the source — a human-authored signal that a derivation rule couldn't match without false positives elsewhere.

##### F-cli-6: README is one document, but ~12 distinct sections

This is a real test of the **short-README chunking** open question (#2 in v0.0.2). codeguard-cli's README is ~290 lines / 12 H2 sections. Pure chunk-per-heading gives ~12 reference entries. Whole-doc would be one ~12KB entry.

**Verdict:** chunk-per-heading is clearly correct here. A query for "how do I configure codeguard-cli?" should match the Configuration section, not the whole README. The `~200-character minimum` tentative rule from v0.0.2 wouldn't collapse any of these — every section is substantial.

**The open question can probably be closed** with: chunk-per-heading is the default; minimum chunk size of ~200 chars (tiny stub sections roll into their parent). Confirm after one more project.

##### F-cli-7: `pyproject.toml` doesn't declare a license either

Package's `pyproject.toml` has no `license` field. Same issue as F-cli-4 but at the package level. Same recommendation: optional, omit when absent.

#### Findings summary

| # | Finding | Action |
|---|---|---|
| F-cli-1 | Same content in two projects (rules) | Evidence pulling toward promoting `equivalents` / `canonical_source` from deferred → in spec. One more case needed. |
| F-cli-2 | Large schema-laden JSON example in README | No action. Confirms `ingestibility` is not yet motivated. |
| F-cli-3 | Sub-modules of a single package | No action. Granularity rule held. |
| F-cli-4 | Missing LICENSE file | Minor: clarify `license` is optional, omit when absent. |
| F-cli-5 | `status: "draft"` real case | Confirms Q-B2 resolution. No action. |
| F-cli-6 | Multi-section README | Closes open question #2 (chunk-per-heading default). Pending one more project. |
| F-cli-7 | `pyproject.toml` no license | Same as F-cli-4 at package level. |

#### Does v0.0.2 hold up?

Largely yes. The granularity rule and embed/filter/store invariant were *the right tools* for analyzing this project — they pre-empted a few decisions cleanly. The two real signals are:

1. **`equivalents` / `canonical_source` is gaining motivation.** Two of two non-trivial projects so far ship structured content that exists in another project too. If secure-ai-tooling or ws2-defenders also has this pattern, promote.
2. **Clarify `license` is optional.** Trivial doc fix.

Nothing in v0.0.2 broke. The schema bent slightly (license-missing) but didn't break.

---

### 3. secure-ai-tooling

**Analyzed:** 2026-05-18 (against v0.0.2)
**Commit:** `01fc50d8` (2026-05-17)
**Repo:** https://github.com/cosai-oasis/secure-ai-tooling

#### What's in the project

The CoSAI Risk Map (CoSAI-RM) — a framework for identifying AI security risks, controls, components, and personas. Distinct from project-codeguard: where project-codeguard ships rules *for AI coding agents*, this ships a *risk framework* (structured YAML data + visualizations + a web Explorer).

- **Risk Map data** under `risk-map/yaml/` — 10 YAML files, each carrying a list of typed entries:
  - `risks.yaml` (28 risks: Data Poisoning, Model Evasion, etc.)
  - `controls.yaml` (35 controls)
  - `components.yaml` (26 AI-system components)
  - `personas.yaml` (10 personas)
  - `actor-access.yaml`, `frameworks.yaml`, `impact-type.yaml`, `lifecycle-stage.yaml`, `mermaid-styles.yaml`, `self-assessment.yaml`
- **JSON schemas** under `risk-map/schemas/` — 13 `.schema.json` files defining the structure of each YAML.
- **Generated markdown tables** under `risk-map/tables/` — 12 markdown files (full/summary/xref views of the same data).
- **SVG visualizations** under `risk-map/svg/` — auto-generated from the YAML.
- **Documentation** under `risk-map/docs/` — 19 markdown guides (`guide-risks.md`, `guide-controls.md`, etc.) plus contributing/design subdirs.
- **Static site** under `site/` — the "CoSAI Risk Map Explorer" published to GitHub Pages. HTML + assets.
- **Tooling** under `scripts/`:
  - `scripts/hooks/` — Python validators (`validate_riskmap.py`, `validate_framework_references.py`, `validate_control_risk_references.py`, `yaml_to_markdown.py`)
  - `scripts/agents/` — 6 markdown agent definitions (`architect.md`, `code-reviewer.md`, `swe.md`, etc.)
  - `scripts/tools/`, `scripts/workflows/`, `scripts/docs/`, `scripts/TEMPLATES/`
- **No installable Python package** — `pyproject.toml` exists but only configures pytest/coverage. Scripts run in-place via `mise`/pre-commit.
- **Node toolchain** — `package.json` declares dev dependencies (`mermaid-cli`, `playwright`, `prettier`, `puppeteer`) used to generate diagrams and run site tests. Not an importable npm package.

#### How the v0.0.2 format maps onto this project

**Proposed `manifest.json`:**
```json
{
  "schema_version": "0.0.2",
  "project": "secure-ai-tooling",
  "path": "secure-ai-tooling",
  "description": "Coalition for Secure AI Tooling repository. Hosts the CoSAI Risk Map (CoSAI-RM): a framework of risks, controls, components, and personas for AI security, expressed as YAML data with JSON schemas, generated markdown tables, SVG visualizations, and a persona-based web Explorer. Includes validation tooling and pre-commit hooks that keep the data and generated artifacts consistent.",
  "languages": ["python"],
  "primary_kind": "dataset",
  "also": ["docs", "working-group"],
  "license": "Apache-2.0",
  "status": "active",
  "owners": ["@cosai-oasis"],
  "tags": ["cosai", "risk-map", "ai-security", "controls", "personas", "framework"],
  "repo_url": "https://github.com/cosai-oasis/secure-ai-tooling",
  "default_branch": "main",
  "last_commit": {"sha": "01fc50d8", "date": "2026-05-17T22:02:30-07:00"},
  "last_indexed": "2026-05-18T...",
  "counts": {"packages": 0, "snippets": ~3, "references": ~120-700+}
}
```

The huge range on `counts.references` reflects an unresolved granularity question — see F-sat-1.

**Proposed `packages.jsonl` (0 entries):**
None. No Python package is published or distributed. The scripts are repo-local tooling. `pyproject.toml` is config-only.

Initial reaction: this *feels* like it should produce a package. But applying the granularity rule honestly — no install command, no module entrypoint, no consumer story beyond "clone the repo and run scripts/" — `packages.jsonl` stays empty. The validators and `yaml_to_markdown.py` would more naturally appear as **snippets** if they're reusable patterns.

**Proposed `snippets.jsonl` (~3 entries):**
- `snip:secure-ai-tooling/yaml-to-markdown` — `scripts/hooks/yaml_to_markdown.py`, "render structured YAML into multiple table formats (full/summary/xref)" pattern.
- `snip:secure-ai-tooling/riskmap-validator` — `scripts/hooks/validate_riskmap.py`, "validate cross-references between entities in a structured framework" pattern.
- `snip:secure-ai-tooling/framework-reference-validator` — `scripts/hooks/validate_framework_references.py`, "validate references from a local framework into external frameworks (MITRE ATLAS, NIST AI RMF, etc.)" pattern.

**Proposed `references.jsonl` (~120 entries baseline, but see F-sat-1):**
- 19 docs guides × ~5 sections each = ~100 chunks
- README + risk-map/README chunked = ~10 chunks
- 6 agent definitions in `scripts/agents/` = 6 entries (`form: "structured"`, executable in the dropped sense)
- Generated tables (`risk-map/tables/*.md`) = ~12 entries... but are they references at all? See F-sat-2.
- The YAML data files themselves = either 10 entries (one per file) or **~100+ entries** (one per risk/control/component/persona/etc.) — see F-sat-1.

#### Findings — against v0.0.2

##### F-sat-1: The YAML risk map is the project's product, and granularity is the question

Each `risks.yaml`, `controls.yaml`, `components.yaml`, `personas.yaml` file is a **list of typed entries** (28 risks, 35 controls, 26 components, 10 personas). Each entry has its own `id`, `title`, `shortDescription`, `longDescription`, and cross-references (e.g. a control lists the risks it addresses).

Three indexing strategies:

1. **One reference entry per YAML file** (~10 entries) — coarsest. A query "data poisoning controls" hits `controls.yaml` as a whole, then the model reads the file to find the specific control. Cheap, lossy.
2. **One reference entry per item-in-YAML** (~100+ entries) — finest. Each risk/control/component/persona is its own entry with its own summary, structure_description, and tags. A query "data poisoning" hits `riskDataPoisoning` directly with high precision.
3. **Both** — coarse summary at file level + fine-grained at item level. Doubles the count.

This is the **same** question Q-A2 deferred for project-codeguard's 110 rules ("110 rules → 110 vector rows, or grouped?"). Two projects now produce evidence for the same granularity question. **Time to resolve.**

**Recommendation:** Option 2 — one entry per item. Reasoning:
- Voyage embeddings handle 100s of rows cheaply.
- The cross-references between items (controls→risks, risks→components) only become useful query-side if items are addressable. With Option 1, a query "show me all controls that address Data Poisoning" can't be answered — you'd have to retrieve all of `controls.yaml` and have the model scan it.
- Each item naturally has its own structure (the YAML schema defines it). v0.0.2's `structure_description` field expresses this cleanly.
- Filter precision wins. Option 1 returns "the controls file"; Option 2 returns the three controls that actually apply.

This **resolves Q-A2** in favor of fine-grained indexing.

##### F-sat-2: Generated content — index or skip?

`risk-map/tables/*.md` and `risk-map/svg/*.svg` are **auto-generated** from the YAML by pre-commit hooks. They contain no information that's not in the YAML. Should the indexer pick them up?

If we apply Option 2 from F-sat-1 (one entry per YAML item), the tables are pure redundancy — every fact in `risks-summary.md` is already in `risks.yaml`. Indexing both inflates the corpus with near-duplicates.

**Recommendation:** **skip auto-generated content by convention.** Indexer respects a `.cosai-index/ignore` glob list (similar to `.gitignore`) declared in the manifest or as a separate file. Default ignore list: `**/svg/**`, common build artifacts, and anything declared by the project.

This needs a new **manifest field**:
```json
"indexing": {
  "ignore": ["risk-map/tables/**", "risk-map/svg/**", "site/generated/**"]
}
```

Free text glob patterns. Filter category: **store** (not embedded, not searched — used only at index time).

##### F-sat-3: `primary_kind: "dataset"` finally has a real case

project-codeguard was `ruleset`; codeguard-cli was `cli`. secure-ai-tooling is the first real `dataset` — its primary deliverable is the structured YAML risk-map data, with docs, validators, and visualizations as supporting machinery. `also: ["docs", "working-group"]` captures the 19 docs guides and the OASIS Open Project nature.

Worth noting: the **YAML schema files** (`*.schema.json`) define the dataset's structure. They're not really referencable on their own, but they are *meaningful*. Candidate categorization: **references** with `form: "structured"`, summary = "JSON Schema defining the structure of risks.yaml entries; required for validators and external tools that consume the data."

##### F-sat-4: `scripts/agents/*.md` are claude-code-style agent definitions

Six markdown files under `scripts/agents/`: `architect.md`, `code-reviewer.md`, `swe.md`, etc. These look like **Claude Code agent prompts** — structured-but-prose definitions intended to be loaded into AI coding tools.

Three observations:
1. They're real `form: "structured"` references — frontmatter (likely YAML) + prose body.
2. They're **executable** in the dropped Q-A6 sense (the agent definition is loaded into Claude Code and run).
3. They duplicate roles you'd find in many projects — `architect.md`, `swe.md`, `code-reviewer.md`. Generic naming suggests these may be cross-project artifacts.

**This is the second project with content that may have canonical-source elsewhere.** project-codeguard had rules; codeguard-cli had snapshot rules; secure-ai-tooling has agent definitions that might exist in upstream Claude Code conventions or elsewhere in the COSAI workspace.

##### F-sat-5: Cross-references inside the YAML are first-class structure

Each control in `controls.yaml` declares which risks it addresses and which components/personas apply. These are **internal cross-references** that v0.0.2's `equivalents` (deferred) doesn't quite cover — `equivalents` was for same-info-different-form. Here we have *different things* that are *related to each other*.

The model querying "controls for Data Poisoning" needs to traverse: query → `riskDataPoisoning` → lookup all controls that list it → return those controls.

**Two design options:**

1. **Don't represent cross-refs in the index.** Let the model load the YAML and traverse. Works but requires the model to load larger context.
2. **Represent cross-refs as an entry-level field**, e.g. `references[].linked_ids: [...]`. Then `get_entry` could optionally expand references; `search` could include linked items in results.

I don't have strong opinion yet. **Tentative recommendation: defer.** v0.0.2's design (filter on tags, retrieve via embedding) already lets a query for "Data Poisoning controls" find both the risk entry and matching control entries (the controls' summaries should mention Data Poisoning explicitly). Whether this works in practice needs testing. If it doesn't, add `linked_ids` as a candidate field.

##### F-sat-6: Two manifest files exist (Python + Node)

- `pyproject.toml` — only `[tool.pytest]` and `[tool.coverage]` config. No `[project]` block.
- `package.json` — only `dependencies` (mermaid-cli, playwright, puppeteer, prettier). No `name` or `version`.

Both fail the criterion of "this declares an installable package." The v0.0.2 nested-manifest rule (any directory with a recognized manifest produces a package entry) is **too eager** here. We need a stricter test.

**Recommendation:** the rule should be **"declares an installable artifact,"** specifically:
- `pyproject.toml` requires a `[project]` table with a `name`.
- `package.json` requires a `name` field (and ideally not `private: true`).
- `go.mod` always qualifies (it always declares a module).
- `Cargo.toml` requires a `[package]` table.
- `.claude-plugin/plugin.json` always qualifies.

Tool-config-only manifests do not produce package entries. **Clarification for v0.0.3**, not a schema change.

##### F-sat-7: Static site `site/` and its tests

`site/` is a static GitHub Pages site (HTML, CSS, JS, generated assets) plus a `tests/` directory. It's a real deliverable — the user-facing Explorer. Two questions:

1. **Is `site/` a `package`?** No published package. It's served as a static site. v0.0.2's `ecosystem` doesn't have a value for "this is served as a website" — closest is `none`. We probably want `static-site` as an ecosystem value, but only if more projects produce one.
2. **Should `site/` be indexed at all?** The HTML is generated; the JS is part of the Explorer. Probably skip the site content itself (it duplicates what the YAML carries) but mention its existence in the manifest description. Same logic as F-sat-2 (auto-generated content).

**Recommendation:** add the site/ folder to the project's `indexing.ignore` list. Mention the Explorer in the project description.

##### F-sat-8: Generated SVGs and Mermaid diagrams

`risk-map/svg/*.svg` and `risk-map/diagrams/*` are generated visualizations of the YAML data. Same as F-sat-2: skip.

But there's a subtle case: the **SVG files contain meaningful text** (component names, risk titles) and could be retrieved by image search. We don't have image embeddings in v0.0.2 — Voyage's image embeddings exist but aren't in scope. **No action.** Skip SVGs. If image search becomes valuable, that's v0.x territory.

#### Findings summary

| # | Finding | Action |
|---|---|---|
| F-sat-1 | Granularity of structured data: one entry per item, not per file | **Resolves Q-A2.** Fine-grained is the rule. |
| F-sat-2 | Generated content (tables, SVGs, site) | **New manifest field `indexing.ignore`.** Skip generated artifacts by glob. |
| F-sat-3 | `primary_kind: "dataset"` working as designed | No action. Confirms the enum value. |
| F-sat-4 | Agent definitions in `scripts/agents/` may be cross-project | Tracks the same canonical-source signal as codeguard-cli. Promote `canonical_source` field if ws2-defenders also has this. |
| F-sat-5 | YAML cross-references between items | **Defer.** Test whether semantic search handles it before adding `linked_ids`. |
| F-sat-6 | Tool-config-only manifests should not produce package entries | **Clarification for v0.0.3.** Tighten the nested-manifest rule. |
| F-sat-7 | Static site under `site/` — skip via indexing.ignore | Covered by F-sat-2's mechanism. |
| F-sat-8 | Generated SVGs and Mermaid diagrams | Covered by F-sat-2. |

#### Does v0.0.2 hold up?

**Mostly. Three real changes motivated:**

1. **`indexing.ignore` glob list in the manifest** (F-sat-2, F-sat-7, F-sat-8). Without this, a project like secure-ai-tooling produces ~100 duplicate references for the generated tables alone. This is a v0.0.3 must-have.
2. **Tighten the nested-manifest rule** (F-sat-6): "declares an installable artifact," not "exists." Doc clarification; no schema change.
3. **Resolve Q-A2 as fine-grained** (F-sat-1): one entry per item in structured data files, not one per file. Doc clarification with worked example for v0.0.3.

**Q-A1.2 canonical-source field** has now appeared in:
- codeguard-cli (rule snapshots from project-codeguard)
- secure-ai-tooling (agent definitions that may be cross-project)

That's the ≥2-project evidence threshold I set when deferring it. **Recommend promoting `canonical_source` (single ID) field to entries in v0.0.3.** Single-value, store-only (not embedded, not filtered — used by the model to expand when needed).

The granularity rule continued to hold up — it told us how to think about the YAML (one entry per item) even before we made the granularity call explicit.

The `form` / `structure_description` design from Q-A1 is paying off here: the YAML items get `form: "structured"` and a structure description like *"A CoSAI Risk Map control. Fields: id, title, description, applicable components, applicable personas, addressed risks, lifecycle stages, framework mappings (MITRE ATLAS, NIST AI RMF, STRIDE, OWASP-LLM)."* That description embeds well and tells the model what shape the content is in.

---

## Prompt-driven re-evaluation (against [`evaluation-prompts.md`](evaluation-prompts.md))

Phase 6 introduced ten realistic user prompts as the evaluation discipline. Re-running each completed project against the prompt list grounds the schema decisions in retrieval reality rather than shape aesthetics. For each project, every prompt gets a verdict:

- **Hit** — the project would surface useful, well-ranked entries from v0.0.2 as it stands.
- **Partial** — some relevant entries would surface, but with caveats (incomplete coverage, weaker ranking, model has to do extra work).
- **Miss** — the project either has nothing to contribute (legitimate) or has something but the schema can't surface it (real gap).

Only **Misses** that *should* have been Hits are evidence for promoting deferred candidate fields.

### Re-evaluation: project-codeguard

| Prompt | Verdict | Entries that would surface | Notes |
|---|---|---|---|
| P1 (LLM provider wrapper) | Miss (legitimate) | none | project-codeguard doesn't ship an LLM wrapper. Codeguard-cli does. Not a schema gap. |
| P2 (MCP server scaffolding) | **Hit** | `pkg:project-codeguard/codeguard-mcp` (the sub-package) | Tests the nested-manifest rule. The package entry's `summary` covers "exposes CodeGuard rules as MCP tools over streamable HTTP" — directly relevant. `ecosystem: "mcp-server"` filter would narrow precisely. |
| P3 (file-hash skip pattern) | Miss (legitimate) | none | project-codeguard doesn't have this pattern. Codeguard-cli does. |
| P4 (versioned-content manager) | Partial | weak match via `src/converter.py` framing | project-codeguard is the *upstream* of codeguard-cli's `rules` manager. Its release/conversion machinery is related but not the same pattern. The model might surface it; user picks codeguard-cli. Not a schema issue. |
| P5 (YAML cross-ref validator) | Miss (legitimate) | none | project-codeguard's rules are markdown, not cross-referenced YAML. |
| P6 (CISO dashboard against risks) | Partial | rule entries tagged `cwe`, `owasp`, `injection`, etc. | project-codeguard's rules are *code-level* security guidance, not *risk taxonomy*. They surface for "security exceptions" queries but don't answer "high-level risks a CISO understands." The model would correctly weight secure-ai-tooling higher. Schema served correctly. |
| P7 (RAG-feature threat modeling) | **Hit** | `codeguard-0-input-validation-injection.md`, `codeguard-0-mcp-security.md`, possibly the `security-review` skill | Multiple rule entries should rank high on "prompt injection," "input validation." Reference-form embedding does the work. |
| P8 (hardening AI-generated code) | **Hit** | The `security-review` skill, the `codeguard-reviewer` agent, the full rule set | This is project-codeguard's core use case. All four sub-deliverables (rules, skills, agent, plugin) would surface. Tests whether `summary` + `structure_description` correctly disambiguate skill-bundle from rule from agent. |
| P9 (which projects ship runnables?) | **Hit** | manifest entry with `primary_kind: "ruleset"`, `also: ["library","cli","service","claude-plugin","docs"]` | `list_projects(filters={kind in [library,cli,service]})` returns project-codeguard because of `also`. The `primary_kind` + `also` reshape (Q-A3) is doing exactly what it was designed to do here. |
| P10 (supply-chain position paper) | **Hit** | `codeguard-0-supply-chain-security.md`, `codeguard-0-devops-ci-cd-containers.md`, related rules | Rule entries cover supply-chain (cvalidate-dependencies, SBOM, etc.). The user's paper would cite them as code-level controls. |

**Score: 5 Hit / 2 Partial / 3 Miss (all legitimate).** No retrieval failures.

**What this confirms:**
- The `primary_kind` + `also` reshape (Q-A3) is load-bearing for P9. Confirmed in production query.
- `ecosystem: "mcp-server"` (Q-A5) is load-bearing for P2. Confirmed.
- Nested-manifest detection is load-bearing for P2.
- The 110 rule entries being separately indexed (resolving Q-A2 as fine-grained) is load-bearing for P7, P8, P10. Confirmed in production query.

**What the deferred fields would have changed:** nothing. `equivalents` doesn't help here (no equivalence queries). `canonical_source` doesn't help (no copy-of-something queries from this project's side). `indexing.ignore` doesn't help (no duplicate content surfaces in any query result). All correctly deferred.

### Re-evaluation: codeguard-cli

| Prompt | Verdict | Entries that would surface | Notes |
|---|---|---|---|
| P1 (LLM provider wrapper) | **Hit** | `snip:codeguard-cli/llm-provider-abstraction` (`codeguard/llm.py`) — and the package itself | The package's `summary` mentions multi-provider; the snippet describes the pattern. Tests Goal 1 + Goal 2 together. `language: "python"` filter and `ecosystem: "source"` value both matter. |
| P2 (MCP server scaffolding) | Miss (legitimate) | none | codeguard-cli doesn't ship an MCP server. Project-codeguard does. |
| P3 (file-hash skip pattern) | **Hit** | `snip:codeguard-cli/file-hash-skip` (`recheck.py` + `checker.py`) | The snippet's `summary` mentions SHA256 hash skip — semantic match on "skip unchanged files." |
| P4 (versioned-content manager) | **Hit** | `snip:codeguard-cli/cached-rules-version-manager` (`codeguard/updater.py`) | Tests semantic match: user says "policy versions" or "config snapshots," `updater.py` summary says "rules versions, cache locally, switch active." `summary` carries the abstraction; tags help. |
| P5 (YAML cross-ref validator) | Miss (legitimate) | none | codeguard-cli's rules are markdown, not cross-referenced YAML. |
| P6 (CISO dashboard against risks) | Miss (legitimate) | none | codeguard-cli is a tool, not a taxonomy. |
| P7 (RAG-feature threat modeling) | Partial | the bundled rule snapshots — but **same content as project-codeguard** | This is the duplicate-hit case. Both projects return rule entries for the same content. The model would see (e.g.) `ref:codeguard-cli/rules/input-validation-injection` and `ref:project-codeguard/rules/owasp/codeguard-0-input-validation-injection.md` as separate hits with similar summaries. **Noisy but not broken.** The model can dedup by inspection. Whether this earns `canonical_source` depends on whether it actually degrades model behavior. |
| P8 (hardening AI-generated code) | **Hit** | The package entry (codeguard-cli's whole purpose) + README chunks describing `codeguard check` and `codeguard scan` | The README's "About" section explicitly frames this — direct match. |
| P9 (which projects ship runnables?) | **Hit** | manifest entry with `primary_kind: "cli"`, but `status: "draft"` | `list_projects` returns it; the `status: "draft"` flag signals "not production-ready." User can choose to include or exclude. Q-B2 resolution paying off. |
| P10 (supply-chain position paper) | Partial | the bundled `codeguard-0-supply-chain-security.md` rule — same duplicate-hit caveat as P7 | Same as P7: noisy with project-codeguard but not broken. |

**Score: 5 Hit / 2 Partial / 3 Miss (all legitimate).** Two Partials both flag the same issue: duplicate rule entries across project-codeguard and codeguard-cli.

**What this confirms:**
- `ecosystem: "source"` (Q-A5) is load-bearing for P1 — codeguard-cli isn't on PyPI, the source ecosystem value is what makes the install command meaningful.
- Snippet entries doing real work in P1, P3, P4. The snippet/package split is justified — these are *patterns to copy*, not *packages to install*.
- `status: "draft"` (Q-B2 resolution) is load-bearing for P9. A user filtering "only production-ready tools" would exclude codeguard-cli using this filter. Confirmed.

**Real signal on `canonical_source`:** P7 and P10 both show duplicate hits across project-codeguard and codeguard-cli. The model can handle it (read both summaries, recognize they're the same content), but it's not free — costs context and ranking quality. **Whether `canonical_source` earns promotion depends on how noisy the duplicates are in *retrieval reality* (not just inventory).** Without running an actual retrieval, this is still suggestive, not conclusive.

**Tentative read:** still defer. The Partials are tolerable; the model dedups by inspection. Promote `canonical_source` only if a third project produces similar duplicate-hit noise *and* the noise visibly degrades a query.

### Re-evaluation: secure-ai-tooling

| Prompt | Verdict | Entries that would surface | Notes |
|---|---|---|---|
| P1 (LLM provider wrapper) | Miss (legitimate) | none | secure-ai-tooling is a dataset/framework, not a tool. |
| P2 (MCP server scaffolding) | Miss (legitimate) | none | No MCP server here. |
| P3 (file-hash skip pattern) | Miss (legitimate) | none | Not applicable. |
| P4 (versioned-content manager) | Miss (legitimate) | none | Not applicable. |
| P5 (YAML cross-ref validator) | **Hit** | `snip:secure-ai-tooling/riskmap-validator`, `snip:secure-ai-tooling/framework-reference-validator` | These snippets are the exact pattern requested. The summaries describe "validate cross-references between entities in a structured framework" — direct semantic match. |
| P6 (CISO dashboard against risks) | **Hit (strong)** | `risks.yaml` entries (per risk), the risk-map README chunks, framework-mappings doc | This is the project's reason for existing. Fine-grained YAML entries (resolving Q-A2) means a query for "Data Poisoning" hits `riskDataPoisoning` directly with high precision. The README chunks frame the four-pillar grouping (Data/Infra/Model/App). Multi-entry composition working as designed. |
| P7 (RAG-feature threat modeling) | **Hit** | RAG-related risk entries from `risks.yaml`, components covering RAG context, related controls | Cross-project: secure-ai-tooling provides the *risk taxonomy*; project-codeguard provides *code-level rules*. Model composes them. Tests `search` across projects without project-scoping. |
| P8 (hardening AI-generated code) | Partial | controls covering "Code Review," "AI-Assisted Development" if such control entries exist | Indirect match. The model would lean on project-codeguard primarily; secure-ai-tooling contributes context. Schema served correctly. |
| P9 (which projects ship runnables?) | **Hit (correctly excluded)** | manifest entry with `primary_kind: "dataset"`, `also: ["docs","working-group"]` | The user's query *excludes* this project (it's dataset, not runnable). Correct outcome — `primary_kind` + `also` separation is precisely the disambiguation needed. |
| P10 (supply-chain position paper) | **Hit (strong)** | supply-chain risk entries from `risks.yaml`, related controls, framework mappings | Multi-form retrieval: risk entries (structured) + framework-mappings doc (prose) + related controls (structured). Tests the hardest prompt against the richest project. Should work cleanly with v0.0.2 as-is. |

**Score: 5 Hit / 1 Partial / 4 Miss (all legitimate).** Strong validation of the `dataset` primary_kind decision and the fine-grained YAML entry resolution.

**What this confirms:**
- Q-A2 resolution (one entry per YAML item) is load-bearing for P6, P7, P10. Coarse-grained (one entry per file) would have failed P6 entirely — the user wants specific risk entries, not "the risks file."
- `form: "structured"` + `structure_description` (Q-A1) load-bearing for P6 — the model reads `structure_description` ("A CoSAI Risk Map risk. Fields: id, title, shortDescription, longDescription, components, lifecycleStages, frameworkMappings...") and knows it can pull cross-references via subsequent queries.
- `primary_kind: "dataset"` (Q-A3) load-bearing for P9 (correctly excluded).
- Snippets (Q-A1.2 / general): `riskmap-validator` and `framework-reference-validator` snippets earn their existence in P5. Tests that even a dataset-primary project can contribute via snippets.

**What deferred fields would have changed:**
- `indexing.ignore` — would have *removed* table/SVG redundancy. Re-evaluation finds **no prompt where the redundant entries hurt retrieval**. P6 (the strongest dataset query) hits the YAML entries directly because their `summary` matches more precisely than the table-rendered summaries. Tables might appear lower in results, but the model picks the YAML; tables become low-priority context. **`indexing.ignore` still not justified by user queries.**
- `linked_ids` for YAML cross-references — P7 (RAG threat modeling) needs the model to traverse from a risk to its addressing controls. Re-evaluation: the model can issue a follow-up `search` for "controls addressing prompt injection" and find them. `linked_ids` would have made this one fewer call but isn't required. **Still deferred.**
- `semantic_id` / `presentations` — no prompt benefits. The CISO dashboard query (P6) doesn't ask "what other forms of this data exist," it asks "what risks are there." Multi-entry serves it. **Reject from consideration unless a new prompt motivates.**

---

## Re-evaluation summary

**Across three projects × ten prompts (30 verdicts):**

- **15 Hit** — schema served correctly
- **5 Partial** — schema served, with caveats (model has to dedup or do follow-up work)
- **10 Miss (legitimate)** — the project doesn't have what the prompt asks for; not a schema gap

**Zero retrieval failures attributable to schema gaps.** v0.0.2 served every prompt where the project had something relevant.

### What this confirms about resolved decisions

Every Tentative decision from Phase 4 has been **vindicated** by at least one prompt that depends on it:

| Decision | Confirmed by |
|---|---|
| Q-A3 (`primary_kind` + `also`) | P9 across all three projects |
| Q-A1 (`form` + `structure_description`) | P6, P7, P10 in secure-ai-tooling |
| Q-A4 (`language` = implementation only) | P1 in codeguard-cli (language filter works), P6 in secure-ai-tooling (subject "AI risks" not stuck in a language filter) |
| Q-A5 (extended `ecosystem` enum) | P2 (mcp-server), P1 (source) |
| Q-A2 resolution (fine-grained YAML entries) | P6, P7, P10 — coarse-grained would have failed P6 outright |
| Q-A4.1 (granularity rule) | P9 (filter at entry level), P6 (each YAML item retrievable) |
| Q-B2 (`status` declared, not derived) | P9 in codeguard-cli (`status: "draft"` flag matters) |

### What this confirms about deferred candidate fields

All deferred fields remain deferred:

- **`equivalents`** — no prompt asks "what other forms exist." Defer.
- **`canonical_source`** — P7/P10 in codeguard-cli show duplicate-hit noise across project-codeguard's source rules and codeguard-cli's snapshot. The model can handle it, but cost is real. *Still tentative defer pending ws2-defenders evidence.*
- **`ingestibility`** — no prompt's results would change with this filter.
- **`executable`** — no prompt asks "give me only runnable artifacts."
- **`indexing.ignore`** — generated content doesn't break any prompt's results in secure-ai-tooling.
- **`semantic_id` / `presentations`** — no prompt motivates. *Reject from consideration.*
- **`linked_ids`** — P7 cross-traversal works via follow-up queries.
- **`role` on packages** — no prompt benefits.

### Net takeaways

1. **v0.0.2 is sufficient for the queries that matter.** Every prompt that should have succeeded did. No "real query failed because the schema lacked X."
2. **v0.0.3 stays a clarifications-only release.** Confirmed.
3. **Schema discipline (working principle #9) just paid for itself.** Three projects of deferred-candidate inventory, re-evaluated against ten realistic queries, produced zero promotions. Without the discipline, several fields would already be in the schema unjustified.
4. **`canonical_source` is the only candidate with non-trivial signal** — duplicate-hit noise across project-codeguard and codeguard-cli in P7/P10. Watch ws2-defenders for the third data point.
5. **One refinement to evaluation-prompts.md:** P7 and P10 both stress cross-project retrieval and multi-form composition; consider adding a prompt that *exclusively* tests filter-driven narrowing (e.g. "show me only Python snippets relating to crypto"). Not urgent.

---

### 4. ws2-defenders

**Analyzed:** 2026-05-18 (against v0.0.2, with prompt-driven evaluation)
**Commit:** `58c46d78` (2026-05-05)
**Repo:** https://github.com/cosai-oasis/ws2-defenders

#### What's in the project

A working-group repository that ships *both* substantial whitepaper content *and* a real multi-language SDK. Markedly richer than the typical CoSAI workstream — closer in shape to project-codeguard than a pure docs repo:

- **Two formally-approved whitepapers** at the root and under `incident-response/`:
  - `preparing-defenders-of-ai-systems.md` (~38K markdown, also as PDF) — v1.0, approved 2025-07-14. Workstream's flagship deliverable.
  - `incident-response/AI-Incident-Response.md` (also PDF) — v1.0, approved 2026-10-27. AI Incident Response Framework.
- **Framework reviews** under `frameworks/` — 7 markdown docs reviewing AI security frameworks: `NIST.md`, `MITRE.md`, `OWASP.md`, `MIT.md`, `CISA.md`, `OASIS.md`, `OCSF.md`. Each follows the same template: overview / scoping / persona / guidance / detail / what's missing.
- **AI Telemetry Framework (AITF)** under `telemetry/` — a *substantial* sub-project, effectively a project in its own right:
  - **Three SDKs** with their own package manifests:
    - `telemetry/sdk/python/pyproject.toml` (Python SDK)
    - `telemetry/sdk/go/go.mod` (Go SDK)
    - `telemetry/sdk/typescript/package.json` (TypeScript SDK)
  - **Spec** under `telemetry/spec/` — `overview.md` (375 lines), `semantic-conventions/`, `ocsf-mapping/`, `schema/`, plus an `AICMv1.0.3` Excel spreadsheet.
  - **Integrations** under `telemetry/integrations/` — 10 vendor-specific telemetry collectors (`anthropic`, `azure-ai`, `cohere`, `databricks`, `google-ai`, `litellm`, `nvidia`, `openai`, `openrouter`, `vector-db`).
  - **Examples** under `telemetry/examples/` — 16+ runnable Python tracing examples (`basic_llm_tracing.py`, `agent_tracing.py`, `mcp_tracing.py`, `rag_pipeline_tracing.py`, `ai_bom_generation.py`, `shadow_ai_discovery_tracing.py`, etc.), plus `attack-detection-demo/`, `siem-forwarding/`, `synthetic-telemetry/`, and `aitf_colab_demo.ipynb`.
  - **Collector** under `telemetry/collector/` — OpenTelemetry collector configuration.
  - **Dashboards** under `telemetry/dashboards/grafana/` — Grafana dashboard configs.
  - **Docs** under `telemetry/docs/` and `telemetry_gaps_analysis.md`, `framework_telemetry_requirements.md`.
- **Whitepaper template** at `whitepaper-template.md` — meta-content for future workstream papers.
- **Draft documents** under `draft-documents/`.

#### How the v0.0.2 format maps onto this project

**Proposed `manifest.json`:**
```json
{
  "schema_version": "0.0.2",
  "project": "ws2-defenders",
  "path": "ws2-defenders",
  "description": "CoSAI Workstream 2: Preparing Defenders for a Changing Cybersecurity Landscape. Hosts two approved whitepapers (Preparing Defenders of AI Systems v1.0; AI Incident Response Framework v1.0), seven AI-security framework reviews (NIST, MITRE, OWASP, MIT, CISA, OASIS, OCSF), and the AI Telemetry Framework (AITF) — a security-first telemetry framework built on OpenTelemetry and OCSF that ships Python, Go, and TypeScript SDKs, 10 vendor integrations, runnable examples, an OTel collector config, and Grafana dashboards.",
  "languages": ["python", "go", "typescript"],
  "primary_kind": "working-group",
  "also": ["whitepaper", "library", "dataset"],
  "license": "<dual: CC-BY-4.0 for docs/data, Apache-2.0 for source/models>",
  "status": "active",
  "owners": ["@cosai-oasis", "Josiah Hagen", "Vinay Bansal (Cisco)"],
  "tags": ["cosai", "defenders", "telemetry", "incident-response", "frameworks", "opentelemetry", "ocsf"],
  "repo_url": "https://github.com/cosai-oasis/ws2-defenders",
  "default_branch": "main",
  "last_commit": {"sha": "58c46d78", "date": "2026-05-05T14:32:35-04:00"},
  "last_indexed": "2026-05-18T...",
  "counts": {"packages": 3, "snippets": ~12, "references": ~80+}
}
```

**Proposed `packages.jsonl` (3 entries):**
- `pkg:ws2-defenders/aitf-python` — `language: "python"`, `ecosystem: "source"` (the `pyproject.toml` declares an AITF Python SDK).
- `pkg:ws2-defenders/aitf-go` — `language: "go"`, `ecosystem: "go"` (declared via `go.mod`).
- `pkg:ws2-defenders/aitf-typescript` — `language: "typescript"`, `ecosystem: "npm"` (or `source` — depends on whether the `package.json` declares it as publishable).

The granularity rule from v0.0.2 is **doing exactly the job it was designed for** here: three sibling SDKs, three different languages, three different ecosystems. Each gets its own entry, each filterable independently.

**Proposed `snippets.jsonl` (~12 entries):**
The `telemetry/examples/` directory is rich snippet material. Each `*_tracing.py` is a focused example of one pattern:
- `snip:ws2-defenders/basic-llm-tracing` — basic LLM call tracing with AITF.
- `snip:ws2-defenders/agent-tracing` — agent lifecycle spans, delegation, memory.
- `snip:ws2-defenders/mcp-tracing` — MCP tool-use telemetry.
- `snip:ws2-defenders/rag-pipeline-tracing` — RAG-specific telemetry.
- `snip:ws2-defenders/ai-bom-generation` — generating an AI Bill of Materials.
- `snip:ws2-defenders/shadow-ai-discovery` — detecting unsanctioned AI use via telemetry.
- `snip:ws2-defenders/openrouter-tracing`, `model-ops-tracing`, `vendor-mapping-tracing`, etc.
- `snip:ws2-defenders/agentic-log-tracing`, `dual-pipeline-tracing`, `skills-tracing`.

Each is `language: "python"`, with distinct `tags` and `depends_on`. The granularity rule continues to hold — these are coherent units, one per file.

**Proposed `references.jsonl` (~80+ entries):**
- **Whitepaper chunks** — `preparing-defenders-of-ai-systems.md` has 14 H2 sections; the incident-response framework has many more. ~30 chunks across both whitepapers.
- **Framework reviews** — 7 framework docs, each ~6 sub-sections per framework reviewed, with multiple frameworks per file. Easily ~30 reference chunks.
- **AITF spec** — `telemetry/spec/overview.md` alone is 375 lines; `semantic-conventions/`, `ocsf-mapping/`, `schema/`. ~15 chunks.
- **Telemetry docs** — `telemetry/README.md`, `framework_telemetry_requirements.md`, `telemetry_gaps_analysis.md`. ~10 chunks.
- **Integration READMEs** — 10 vendor integrations, each with a small README. 10 chunks.

#### Prompt-driven evaluation

| Prompt | Verdict | Entries that would surface | Notes |
|---|---|---|---|
| P1 (LLM provider wrapper) | Partial | the 10 vendor integrations under `telemetry/integrations/` | The user is looking for *abstraction over providers for invocation*. ws2-defenders has the opposite — *telemetry collectors* for each provider. Semantically adjacent, the model should disambiguate. Codeguard-cli's `llm.py` remains the stronger hit. ws2-defenders surfaces as "you may also want telemetry for whatever you build." Schema served — `tags: ["telemetry", "opentelemetry", "anthropic"]` and the snippet/package `summary` make this clear. |
| P2 (MCP server scaffolding) | Partial | `snip:ws2-defenders/mcp-tracing` and AITF MCP-namespace spec sections | The user wants to *build* an MCP server. ws2-defenders has *MCP telemetry* — what you'd add to an MCP server you'd built. The model would surface these as "if you build it, here's how to instrument it." project-codeguard's `codeguard-mcp` remains the primary hit for scaffolding. |
| P3 (file-hash skip pattern) | Miss (legitimate) | none | Not applicable. |
| P4 (versioned-content manager) | Miss (legitimate) | none | Not applicable. |
| P5 (YAML cross-ref validator) | Miss (legitimate) | none | Not applicable — AITF uses OCSF/OTel semantic conventions, not custom YAML. |
| P6 (CISO dashboard against risks) | **Hit (strong)** | "Preparing Defenders" whitepaper chunks (esp. "The Growing Attack Surface", "AI Risks in Business Processes"), framework-review chunks for NIST AI RMF and OWASP LLM Top 10, the `telemetry/dashboards/grafana/` configs | This prompt was originally written with secure-ai-tooling in mind, but ws2-defenders **also strongly answers it from a different angle**: the *defender's* perspective on which risks matter to executive stakeholders, plus actual Grafana dashboards as starting points. **Multi-project complementary retrieval — exactly the win Q-A4.1 granularity rule + multi-project search enables.** |
| P7 (RAG-feature threat modeling) | **Hit (strong)** | `snip:ws2-defenders/rag-pipeline-tracing`, AITF spec chunks on RAG telemetry, incident-response framework chunks on "Model Incidents" and "User Interaction Incidents", relevant whitepaper sections on the AI attack surface | The richest cross-project query: secure-ai-tooling gives the *taxonomy* (`riskPromptInjection`), project-codeguard gives the *code-level rules* (`codeguard-0-input-validation-injection`), and ws2-defenders gives the **detection/response** perspective (telemetry to catch it, playbooks for when it happens). Three projects, three angles, all surface for the same query. v0.0.2 schema does this *cleanly* with existing fields. |
| P8 (hardening AI-generated code) | Partial | incident-response framework's "Pre-Incident Preparation" and "Detection and Analysis" chunks | The user is asking about *static review* primarily; ws2-defenders contributes *operational* perspective ("once it's running, here's how you'd know"). Project-codeguard remains the primary hit; ws2-defenders is a secondary, complementary one. |
| P9 (which projects ship runnables?) | **Hit** | manifest entry with `primary_kind: "working-group"`, `also: ["whitepaper", "library", "dataset"]` | This is a *test* of the `also` array's expressiveness. A naive filter on `primary_kind in [library,cli,service]` would exclude ws2-defenders even though it ships three real SDKs. With `also: ["library", ...]`, the project surfaces. **The `primary_kind` + `also` reshape (Q-A3) pays off significantly here.** Without `also`, ws2-defenders would be misclassified as docs-only. |
| P10 (supply-chain position paper) | **Hit (strong)** | whitepaper sections on supply chain (esp. "Secure the supply chain and introduction points of AI"), framework-review chunks on MITRE ATLAS and OWASP supply-chain risks, AITF `ai_bom_generation` snippet, telemetry spec on model provenance / AI-BOM | The richest hit yet for P10. ws2-defenders explicitly addresses supply chain in the whitepaper *and* ships runnable AI-BOM generation code. Cross-project: pair with secure-ai-tooling's supply-chain risk entries and project-codeguard's `codeguard-0-supply-chain-security.md`. **v0.0.2 schema serves this end-to-end without modification.** |

**Score: 5 Hit / 3 Partial / 2 Miss (legitimate).** No retrieval failures attributable to schema gaps.

#### Findings — against v0.0.2

##### F-ws2-1: `primary_kind: "working-group"` + `also: ["library", ...]` is load-bearing

This is the first project that genuinely *needed* the `also` array. ws2-defenders is, at its root, a CoSAI workstream — but the AITF sub-project is a real multi-language SDK with installable Python, Go, and TypeScript packages. Q-A3's reshape from single-kind to primary+also was speculative when made; this project converts it from speculative to load-bearing. P9's verdict depends on it.

**No schema change.** Confirms a Phase 4 decision.

##### F-ws2-2: Three sibling SDKs in three languages — granularity rule held

The three package entries (Python, Go, TypeScript) each carry their own `language` and `ecosystem`. A query "AI telemetry SDK in Go" filters `language: "go"` at the entry level; the Python and TS siblings don't false-match. Q-A4.1's granularity rule is doing exactly what it was designed for.

The packages are conceptually related — they implement the same AITF spec — but treating them as a single package with `languages: [...]` would have broken filtering. The discipline of "decompose to where filterable fields have a single answer" produces the right structure here.

**No schema change.** Confirms a Phase 4 decision.

##### F-ws2-3: Whitepaper PDFs alongside markdown — index markdown, ignore PDF (now confirmed)

v0.0.2 carried this as an open question (#3). ws2-defenders is the first project with both PDF and rendered markdown copies of approved whitepapers (`preparing-defenders-of-ai-systems.{md,pdf}`, `incident-response/AI-Incident-Response.{md,pdf}`). The markdown is the **source-of-truth, structured, chunkable, embeddable** form; the PDF is the **distribution artifact**.

**Recommendation:** close open question #3 with: *"When markdown and PDF copies exist for the same whitepaper, index the markdown, skip the PDF."* The convention is clear; no schema change needed. The indexer needs to know not to index PDFs by default (a baseline behaviour, not a manifest field).

##### F-ws2-4: Cross-project retrieval is the project's strongest contribution

P6, P7, P10 all light up when ws2-defenders is added to the corpus alongside secure-ai-tooling and project-codeguard. The same query pulls *complementary* material from three projects:
- secure-ai-tooling → taxonomy / what to call it
- project-codeguard → code-level rules / how to write it safely
- ws2-defenders → detection-and-response / how to know when it goes wrong, what to do

This is exactly the **discovery + integration** value the MCP server is supposed to provide. The schema doesn't need anything special to make this work — `summary` semantic match across projects already does the job. **Validates the original architecture intent.**

##### F-ws2-5: Telemetry examples are textbook snippet material

The `telemetry/examples/` directory contains 16+ focused Python files, each demonstrating one telemetry pattern (`basic_llm_tracing.py`, `agent_tracing.py`, `mcp_tracing.py`, etc.). These are *exactly* the kind of snippets v0.0.2 was designed to expose:
- Single file per pattern → one snippet entry each.
- Distinct `tags` (`llm`, `agent`, `mcp`, `rag`).
- Clear `depends_on` (the AITF SDK packages, OpenTelemetry).
- Real "I want to copy this and adapt it" use case.

**The snippet selection heuristics implied by v0.0.2 (files under `examples/`) work cleanly for this project.** Resolves open question #1 (snippet heuristics) as: *"files under `examples/`, `cookbook/`, `recipes/` are snippet candidates by default; otherwise functions/classes with substantial docstrings."* No schema change.

##### F-ws2-6: `frameworks/*.md` reviews — each is a structured doc, not a chunk-per-heading case

The 7 framework-review files (`NIST.md`, `OWASP.md`, etc.) follow a consistent internal structure: per framework, six sub-sections (Overview / Scoping / Persona / Guidance / Detail / What's Missing). With v0.0.2's chunk-per-heading default:
- `NIST.md` alone produces ~24 entries (4 NIST frameworks × 6 sub-sections each).
- `OWASP.md` produces ~6 entries.
- Total across `frameworks/` ≈ 50+ entries.

That's reasonable, and queries like "what's missing in NIST AI RMF for defenders?" hit the *specific* "What's Missing" sub-section of *NIST AI RMF 1.0*. The granularity is **right** — coarser would have made these sub-sections invisible.

**However**, there's a question: should `tags` include the framework name? Currently `tags` would carry document-level themes; a query "OWASP LLM Top 10 vulnerabilities" wants to retrieve specifically the OWASP doc's relevant subsection. The `section_path` + `summary` should carry "OWASP Top 10 for LLM Applications" — semantic match should do the work.

**Tentative: no schema change.** If retrieval underperforms in practice on this kind of query, revisit.

##### F-ws2-7: Sub-project-with-its-own-README pattern (AITF inside ws2-defenders)

`telemetry/README.md` is a 36KB document that reads as a *project README*, not a sub-section. It introduces AITF as a framework, lists its capabilities, compares it to OTel GenAI, documents how to install/use it. It's effectively the README of a project living inside another project.

This is a real pattern: ws2-defenders ships AITF as a flagship sub-project. Indexing-wise:
- The packages (Python/Go/TS SDKs) each get their own `packages.jsonl` entry — already covered by the nested-manifest rule.
- The README itself becomes chunked references like any other doc.
- The project manifest's `description` mentions AITF prominently.

**But:** P9 ("which projects ship runnables?") — does AITF *appear in `list_projects` as its own project*? **No, and that's the right answer.** AITF is *part of* ws2-defenders, not a separate project. The `packages.jsonl` entries surface AITF's SDKs; `list_projects` correctly returns "ws2-defenders" because the workspace organizes by repository.

**No schema change.** This validates that "project = repository" is a clean boundary even when a repo contains a flagship sub-project.

##### F-ws2-8: `whitepaper-template.md` and `draft-documents/`

The root has `whitepaper-template.md` (meta-template for future papers) and `draft-documents/` (works in progress). These are *low-signal-per-token* for most queries — a query for "incident response framework" should hit the *approved* document, not the draft or the template.

Options:
1. Index everything; let ranking handle it. Drafts will rank lower than approved versions if their content is less complete.
2. Add a per-entry `status: "draft" | "approved" | "template"` field that the model can filter on.
3. Project declares `indexing.ignore: ["draft-documents/**", "whitepaper-template.md"]` and we're back to the `indexing.ignore` discussion.

**Re-evaluation against prompt list:** does any of P1–P10 actually surface drafts/templates as a problem? P10 (supply-chain position paper) would surface the whitepaper template as a *low-relevance* hit — the user is writing a new paper, the template is a starting point. That's arguably *useful*, not noise.

**Tentative: index everything, defer ignore/status fields.** If a real query produces a template/draft hit that confuses the model in practice, revisit. **Open question.**

##### F-ws2-9: `canonical_source` evidence — does ws2-defenders show duplicate-hit noise like codeguard-cli did?

The third data point for the `canonical_source` candidate field. Walking through ws2-defenders carefully:

- Framework reviews (`frameworks/NIST.md`, `OWASP.md`, etc.) discuss frameworks that **also** exist as risk-map references in secure-ai-tooling (which has framework mappings to MITRE ATLAS, NIST AI RMF, etc.) and as rule cross-references in project-codeguard.
- These are **not duplicate copies** (like codeguard-cli's snapshot rules). They are **different content discussing the same external framework**.

For P7 (RAG threat modeling), the model might retrieve:
- secure-ai-tooling: `riskPromptInjection` (taxonomy)
- project-codeguard: `codeguard-0-input-validation-injection` (code-level rules)
- ws2-defenders: NIST framework review section on AI input validation + RAG-tracing snippet + incident-response RAG-relevant chunk

These are **complementary, not equivalent**. The `canonical_source` field exists to dedup equivalent content. Complementary content is what the system *wants* to surface.

**Re-evaluation:** the `canonical_source` candidate is only motivated when content is *the same artifact, copied*. Within ws2-defenders, no such cross-project duplication appears. Within ws2-defenders + codeguard-cli + project-codeguard, the only true case remains codeguard-cli's `rules/` snapshot.

**Verdict: `canonical_source` still has only one strong motivating case (codeguard-cli's snapshot rules).** ws2-defenders **does not provide a second data point.** The candidate stays deferred. If we want it, we should walk one or two more projects watching specifically for snapshot patterns, or accept that even one case might earn promotion if the query degradation is real.

##### F-ws2-10: Dual license — manifest field needs to handle this

The README states: *"CC-BY 4.0 for documentation and data contributions; Apache License v2.0 for source code and models."* v0.0.2's `manifest.license` is single-valued (SPDX ID). What goes there?

Three options:
1. License is an array: `license: ["CC-BY-4.0", "Apache-2.0"]`.
2. License is an SPDX expression string: `license: "CC-BY-4.0 AND Apache-2.0"` (this is valid SPDX).
3. License gets per-content-type sub-fields: `license: {documentation: "CC-BY-4.0", code: "Apache-2.0"}`.

The first option breaks single-valued filters. The third option over-types something that's usually simple. The second uses **existing SPDX expression syntax** — the model can parse it, the field stays single-valued, filters still work (`filters.license: "Apache-2.0"` matches any expression containing it).

**Tentative recommendation:** `license` accepts SPDX expressions. Single-license projects use a plain ID (`"Apache-2.0"`); dual-license projects use the expression form (`"CC-BY-4.0 AND Apache-2.0"`). The indexer doesn't need to interpret; the model reads it. **Doc clarification, not schema change.**

#### Findings summary

| # | Finding | Action |
|---|---|---|
| F-ws2-1 | `primary_kind` + `also` load-bearing for P9 | No change. Confirms Q-A3. |
| F-ws2-2 | Three sibling SDKs, granularity rule held | No change. Confirms Q-A4.1. |
| F-ws2-3 | Whitepaper PDF + markdown — index markdown only | **Resolves open question #3.** Doc clarification. |
| F-ws2-4 | Cross-project complementary retrieval works | No change. Validates architecture intent. |
| F-ws2-5 | `examples/` directory as snippet source | **Resolves open question #1** (snippet heuristics). Doc clarification. |
| F-ws2-6 | Framework reviews chunk to ~50 entries — fine | No change. Granularity rule held. |
| F-ws2-7 | Sub-project within a repo (AITF inside ws2-defenders) | No change. "project = repository" boundary held. |
| F-ws2-8 | Draft + template files | **Open question.** Defer ignore/status fields unless a query degrades. |
| F-ws2-9 | `canonical_source` — no new evidence | Candidate field stays deferred. |
| F-ws2-10 | Dual-license repos | Doc clarification: license accepts SPDX expressions. |

#### Does v0.0.2 hold up?

**Yes, decisively.** ws2-defenders is the richest project walked so far — multi-language SDK, two approved whitepapers, seven framework reviews, runnable examples, dashboards, vendor integrations — and v0.0.2 absorbed it without breakage.

**What this walk produced for v0.0.3:**
1. **Close open question #1** (snippet selection): files under `examples/`, `cookbook/`, `recipes/` are snippet candidates by default. ✅
2. **Close open question #3** (PDFs): when both markdown and PDF exist, index markdown only. ✅
3. **Close open question #6** (cross-project links / `see_also`): re-confirmed deferred. Cross-project retrieval works without explicit links; complementary content does the job.
4. **Doc clarification** on dual licenses (SPDX expressions).
5. **Doc clarification** on dual licenses + the `examples/` heuristic + the markdown-over-PDF rule.

**Candidate fields after four projects:**
- `canonical_source` — one strong case (codeguard-cli snapshots). **Stays deferred.**
- `equivalents`, `ingestibility`, `executable`, `indexing.ignore`, `linked_ids`, `role`, `semantic_id`, `presentations` — zero motivating prompts. **Stays deferred or rejected.**
- `license` accepts SPDX expressions — clarification, not new field.

**Net:** v0.0.3 is a clarifications-only release with closing of three open questions and zero new fields. Schema discipline (working principle #9) continues to pay for itself.





