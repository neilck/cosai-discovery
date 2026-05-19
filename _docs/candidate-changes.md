# Candidate Changes

Single source of truth for schema fields and behaviours that have been **considered** but are not yet in the spec. Tracks both **deferred** candidates (might still land) and **rejected** candidates (decided against, recorded so we don't relitigate).

The spec (`index-file-format-X.Y.Z.md`) and the project walkthrough log both **point here** rather than duplicating this content.

## How this doc works

Each candidate is one section. Inside:

- **Status** — `Deferred` (might still land) or `Rejected` (decided against; included to prevent relitigation).
- **Motivation** — what shape or query pulled it in.
- **Proposed shape** — what it would look like if added.
- **Evidence table** — one row per project walked, recording what that project showed about this candidate. The promotion case (or rejection case) accumulates here.
- **Promotion threshold** — what would have to happen for `Deferred` to become `Adopted`. For `Rejected`, what would have to change for us to reopen.
- **History** — phase/turn this was first surfaced, last reviewed.

## Working principle

A candidate moves from `Deferred` → `Adopted` only when a concrete user prompt (from [`evaluation-prompts.md`](evaluation-prompts.md)) demonstrably **fails or degrades** without it across at least two projects. Project shape alone — "this project's data *could* use this field" — is not evidence. Evidence is *retrieval failure on a real query*.

A candidate moves from `Deferred` → `Rejected` when ≥3 projects pass through without any prompt motivating it, or when a structural argument shows the candidate fights a load-bearing principle (granularity rule, embed/filter/store invariant, RAG-not-database framing).

---

## Deferred candidates

*All five remaining deferred candidates (C1, C3, C4, C5, C6) were rejected in Phase 9 after ten-walk review. See R8-R12 in the Rejected section.*

---



## Adopted candidates

Promoted to the schema. Recorded so the history of *why* and *based on what evidence* survives. The current schema (`index-file-format-X.Y.Z.md`) is the canonical reference for the field's shape — this section preserves the case for adoption.

### C8 — `builds_on` (manifest field, cross-project dependencies)

**Status:** Adopted in v0.0.4 (Phase 8) → **Removed in implementation phase 1** (replaced by `related_urls`).

**Note on removal:** The typed-enum design proved unreliable in practice. The first multi-project Stage 1 run produced `builds_on: []` on every project with Sonnet (and similarly thin output with Haiku), despite explicit prompt guidance with examples. The LLM consistently struggled to choose between `extends | implements | consumes | cites | donated_from | governed_by` for the same content, even when the relationship was obvious to a human reader.

**Replacement:** `related_urls` — a free-string array of repository URLs found in the project's `README.md`. Same intent (cross-project discovery signal) but without the typed-relationship requirement that the LLM couldn't populate consistently. Anti-hallucination guard in `planner.py` drops any URL not present verbatim in the source README.

**Lessons:**
- Schema fields that require classification across a multi-valued enum are higher-risk than they look. The LLM might do it well for canonical examples and fail silently on edge cases.
- "Strong prompt guidance with examples" doesn't reliably overcome this. The model knows what the answer should be but doesn't produce it.
- A simpler shape (just URLs) preserves most of the value (workspace connection signals) at a fraction of the cognitive load.

The original adoption rationale is preserved below for the historical record.

---

**Original promotion (Phase 8):**

**Why adopted:** Three concrete cases across seven walks established the pattern as structurally real, not anecdotal. The user's decision to promote was guided by: (a) the field serves a clear AI-traversal use case ("what builds on X?", "how does Y use X?"); (b) the workspace's actual collaboration pattern — 3 of 11 projects explicitly building on others — makes the relationship queryable, even if no user has issued the query yet; (c) the shape designed for the field (typed enum + optional URI hint) carries enough nuance to serve "the how," not just "the that."

**Final shape (as in v0.0.4 spec):**
```json
"builds_on": [
  {
    "project": "<slug>",
    "relationship": "extends | implements | consumes | cites | donated_from",
    "uri": "<optional hint>"
  }
]
```

- `project` (required): slug matching the upstream's `manifest.project`.
- `relationship` (required): typed enum distinguishing *kind* of dependency.
- `uri` (optional): hint, not a guarantee. Repo link, document URL, deep-link into an upstream entry, or internal reference. The indexer does not validate format.
- Embed / filter / store: **store**. Used by the model after retrieval to traverse.

**Evidence at time of promotion:**

| Project | Motivating | What it showed |
|---|---|---|
| project-codeguard | n/a | Itself an upstream. |
| codeguard-cli | Yes | Consumes project-codeguard rules. `builds_on: [{project: "project-codeguard", relationship: "consumes"}]`. |
| secure-ai-tooling | No | Self-contained. |
| ws2-defenders | No | References external frameworks (NIST, MITRE) but those aren't COSAI projects. |
| ws1-supply-chain | No | Self-contained workstream. |
| ws3-ai-risk-governance | Yes | SIG donated from Project CodeGuard. `builds_on: [{project: "project-codeguard", relationship: "donated_from"}]`. |
| ws4-secure-design-agentic-systems | Yes | `mcp-secure-tool-design.md` implements controls from the CoSAI Risk Map; README links to a doc in cosai-tsc. `builds_on: [{project: "secure-ai-tooling", relationship: "implements"}, {project: "cosai-tsc", relationship: "cites"}]`. |

**Decision rationale (Phase 8):** Working principle #9 (schema discipline) says promotion requires a query that demonstrably fails without the field, not shape evidence alone. Three options were considered: (A) add a new prompt to the evaluation list — risks fitting the prompt to the candidate; (B) keep deferring until a real user prompt motivates — might never arrive; (C) promote on shape evidence — loosens working principle #9. The user chose to promote *and* later add a P11 prompt to validate retrieval. The design discussion that preceded promotion produced a typed-enum shape with a URI hint, which carries enough nuance to justify the field on its own merits.

**History:** Surfaced Phase 8 (ws3 walk, on the strength of one weak case). Reinforced ws4 walk (third concrete case + explicit cross-project linking with deep URIs). Promoted Phase 8 with a designed shape rather than the simplest possible one.

---

## Rejected candidates

These were considered and decided against. Recorded so future sessions don't re-litigate.

### R1 — `semantic_id` (group entries by underlying semantic unit)

**Status:** Rejected

**Why rejected:** Treats the index as a database with foreign keys. RAG-not-database framing argues against this — the index should be a map of *content* the embedding sees, not a graph of IDs with structural relationships. When traced through the CISO dashboard prompt and other realistic queries, no benefit appeared. Multi-entry search + ranking covers the same need without forcing the schema to model identity.

**Considered shape:** Free-string field grouping entries presenting the same semantic unit across forms/languages/projects. Would have enabled query-time dedup (`search.dedup: "semantic"`) and sibling expansion (`get_entry.include="siblings"`).

**Killed by:** Phase 5/6 single-entry-vs-multi-entry conversation. The CISO dashboard prompt (P6) succeeds with v0.0.2's plain multi-entry approach. Two projects' worth of evidence in the prompt-driven re-evaluation showed no prompt benefits.

**What would reopen this:** A prompt where the *agent's behaviour* degrades because it sees the same idea multiple times and can't reconcile them. Hasn't happened in any walk.

**History:** Surfaced Phase 5 (in the structured-content discussion). Rejected Phase 6.

---

### R2 — `presentations` array (entry-level list of available renderings)

**Status:** Rejected

**Why rejected:** Same reasoning as R1, from a slightly different angle. Treats one entry as the canonical record with multiple "view" pointers. Adds schema complexity (plural `path`/`lines` structure) for a problem the multi-entry approach handles via semantic match + ranking.

**Considered shape:**
```json
"presentations": [
  {"form": "yaml-record", "path": "risks.yaml", "lines": "12-58"},
  {"form": "markdown-table-row", "path": "risks-full.md", "lines": "87-91"}
]
```

**Killed by:** Same Phase 6 conversation as R1. Goes hand-in-hand with `semantic_id`; collapses with it.

**What would reopen this:** A prompt where retrieving the *same idea in multiple forms* is the goal, and the multi-entry approach scatters the answer across results in a way that hurts retrieval.

**History:** Surfaced Phase 5. Rejected Phase 6.

---

### R3 — Splitting `language` into `code_languages` and `subject_languages`

**Status:** Rejected

**Why rejected:** project-codeguard's source code is Python, but its rules cover ~20 languages. A naive single-`languages` field conflates these. The temptation was to split into code (project's own implementation) vs. subject (what the content is *about*). Decided against: subject-matter languages live more naturally in free-text fields (`summary`, `structure_description`) where the embedding picks them up. Splitting adds a field that fights the embed/filter/store invariant.

**Considered shape:**
```json
"code_languages": ["python"],
"subject_languages": ["c", "java", "javascript", "php", "python", "..."]
```

**Killed by:** Q-A4 decision in Phase 4. Reinforced by Phase 6 prompt re-evaluation: no prompt's results changed under the single-`language`-is-implementation-only rule.

**What would reopen this:** A prompt where hard filtering by subject-matter language is the *load-bearing* mechanic and semantic match repeatedly underperforms. Pattern hasn't emerged.

**History:** Surfaced Phase 4. Rejected Phase 4. Confirmed Phase 6.

---

### R4 — `assets.jsonl` as a fourth corpus

**Status:** Rejected

**Why rejected:** Considered for structured project-native content (rules, skills, prompts, frameworks) that doesn't cleanly fit package/snippet/reference. The reframe in Phase 4 was: same knowledge can come in different *forms*; the difference is form/ingestibility, not category. `references.jsonl` extended with `form` + `structure_description` covers it without a fourth corpus.

**Considered shape:** A parallel JSONL file for "structured project-native content," with typed per-asset-type schemas.

**Killed by:** Q-A1 decision in Phase 4. Reinforced through every subsequent walk — references with `form: "structured"` handle rules, skills, agent definitions, framework reviews, YAML data items.

**What would reopen this:** A category of content that genuinely doesn't fit any v0.0.2/v0.0.3 corpus *and* a real prompt that needs to filter by it.

**History:** Surfaced Phase 4. Rejected Phase 4. No project since has produced content that escapes the three-corpus model.

---

### R5 — `equivalents` (cross-form linking within or across projects)

**Status:** Superseded by C1

**Why superseded:** Original conception was "same info, different form" — overlapped with C1 (`canonical_source`) which captures the cross-project copy case. The within-project case (different presentations of the same idea) is handled by storing each as a separate reference with its own `form` and letting semantic match surface them together; explicit links proved unnecessary.

**History:** Surfaced Phase 4 alongside Q-A1.2. Collapsed into C1 in Phase 5.

---

### R8 — `canonical_source` (cross-project artifact snapshot pointer)

**Status:** Rejected (Phase 9 — moved from C1)

**Why rejected:** One motivating case in ten walks (codeguard-cli ships byte-identical rule snapshots of project-codeguard's sources). The case is real but the duplication doesn't cause retrieval failure — both rule entries surface, the model reads both summaries, sees they're similar, and picks one. Three structural arguments seal the rejection:

1. **`builds_on` partially covers it.** codeguard-cli declares `builds_on: [{project: "project-codeguard", relationship: "consumes"}]`. A user asking "where do these rules come from?" gets a manifest-level answer; per-entry precision was unmotivated.
2. **No retrieval failure across 11 prompts × 10 projects.** P7 and P10 produce duplicate-hit pairs, but the model handles them. The "cost is real" concern was speculative.
3. **The fix, if needed, is indexer-side.** A project that wants to skip snapshot directories can do so via project config. Schema field unnecessary.

**Considered shape:** single string field on entries pointing at a canonical source ID in another project. Store-only.

**Evidence accumulated as C1:** one motivating case (codeguard-cli) across ten walks. project-codeguard is canonical-source-of; secure-ai-tooling, ws1, ws2, ws3, ws4, cosai-tsc, cosai-whitepaper-converter, oasis-open-project all original. **1/2 promotion threshold never met.**

**What would reopen this:** a prompt where duplicate hits from snapshot content visibly degrade the model's answer (not just produce paired results the model handles by inspection). Hasn't happened in ten walks.

**History:** Surfaced Phase 4 as `equivalents`; reshaped Phase 5; tracked as C1 through Phases 5–9; rejected Phase 9.

---

### R9 — `executable` (filter: boolean)

**Status:** Rejected (Phase 9 — moved from C3)

**Why rejected:** Zero motivating prompts across ten walks. Every shape that suggested `executable` is already covered by an existing field:

- Runnable notebooks → already classified as `kind: "snippet"` (the `kind` filter handles "runnable").
- Claude Code skill bundles → already `kind: "package"` with `ecosystem: "claude-plugin"`.
- Runnable agent definitions → already `kind: "reference"` with `form: "structured"`.

A new boolean filter would be redundant with `kind`, `ecosystem`, and `form` working together.

**Considered shape:** boolean on reference entries, filter-only.

**Evidence accumulated as C3:** weakly motivating shape in project-codeguard and secure-ai-tooling (skill/agent files exist), but no prompt benefits. Other eight projects: no shape-level motivation.

**What would reopen this:** a query where the user explicitly wants "runnable artifacts only" and the combination of `kind`/`ecosystem`/`form` filters can't narrow. Hasn't happened.

**History:** Surfaced Phase 4 as Q-A6; folded into Q-A1.2 deferral; tracked as C3; rejected Phase 9.

---

### R10 — `indexing.ignore` (manifest-level project-declared globs)

**Status:** Rejected (Phase 9 — moved from C4)

**Why rejected:** Zero motivating cases across ten walks. Every observed pattern of auto-generated or duplicate-shape content is handled by **baseline indexer ignore** rules:

- `.md + .pdf` whitepaper pairs → baseline (index markdown, skip PDF).
- `.excalidraw + .png`, `.drawio`, `.dot + .svg` diagram source/render → baseline.
- `dist/`, `build/`, `node_modules/`, `.next/`, `coverage/`, `*.lock`, lock files → baseline.

No project produced a case where it had project-specific generated content the baseline couldn't handle. secure-ai-tooling's tables came closest, but prompt-driven re-evaluation found they don't degrade retrieval (the canonical YAML entries outrank them naturally).

**Considered shape:** manifest field with `.gitignore`-style globs for project-declared exclusions.

**Evidence accumulated as C4:** weakly motivating shape in secure-ai-tooling; no retrieval degradation found. Other nine projects: handled by baseline.

**What would reopen this:** a project with auto-generated content that the baseline can't classify (uncommon build-output names, project-specific transforms) AND a prompt where indexing that content visibly hurts retrieval.

**History:** Surfaced Phase 5 (F-sat-2); tracked as C4; rejected Phase 9.

---

### R11 — `linked_ids` (within-project cross-references)

**Status:** Rejected (Phase 9 — moved from C5)

**Why rejected:** Zero motivating cases across ten walks. Three projects have rich internal cross-references (secure-ai-tooling's risk-map, ws4's MCP threat/control numbering, ws2's framework-mapping tables). In every case, the model traverses cross-references via **follow-up `search` calls** triggered by reading prose in retrieved chunks. No prompt failed for lack of structured links.

Same RAG-not-database structural argument that killed R1 (`semantic_id`) and R2 (`presentations`): the index is a content map for embedding-based retrieval, not a relational schema. Multi-hop traversal via "read → search again" works as designed.

**Considered shape:** array of related entry IDs on a reference entry.

**Evidence accumulated as C5:** weakly motivating shape in secure-ai-tooling; no prompt failed.

**What would reopen this:** a prompt where multi-hop traversal (e.g. risk → controls → personas in a single query) is needed AND the follow-up-search pattern produces visibly worse results than a structured link would.

**History:** Surfaced Phase 5 (F-sat-5); tracked as C5; rejected Phase 9.

---

### R12 — `role` field on packages

**Status:** Rejected (Phase 9 — moved from C6)

**Why rejected:** Zero motivating cases across ten walks. The candidate was theoretical from the start — a "what if backend and frontend share a language?" speculation that never materialized in the workspace. The **granularity rule** already handles every real multi-package case via distinct `language` + `name` per entry. ws2-defenders' three SDKs (Python, Go, TypeScript) are the canonical multi-package case; they're disambiguated by `language`, not by role.

**Considered shape:** loose enum on package entries (`backend | frontend | worker | cli | agent | library | service`).

**Evidence accumulated as C6:** zero motivating projects.

**What would reopen this:** a multi-package project where two packages share both `language` and `ecosystem` but serve distinct roles, and a query needs to distinguish them.

**History:** Surfaced Phase 4 ("mixed projects" speculation); tracked as C6; rejected Phase 9 — granularity rule has handled every actual case.

---

### R7 — Draft/template content handling (per-entry `status` filter)

**Status:** Rejected (Phase 9 — moved from C7 after ten-walk review)

**Why rejected:** Across ten walks, only two projects (ws1, ws2) produced even "weakly motivating" evidence — and in both cases, the observation was that drafts/templates surface as *low-relevance hits, not noise*. A user writing a new whitepaper is *helped* by the workspace template appearing at the bottom of results; it's a useful affordance, not a problem to filter out. The candidate exists to solve a problem the workspace doesn't actually have.

Three structural arguments against:

1. **Whole-repo planning state is already handled** by `manifest.status: "draft"` (Q-B2 resolved). The ws3-ai-risk-governance case demonstrates this works.
2. **Per-entry status as a filter is the wrong tool.** A hard filter on `status: "approved"` excludes drafts entirely — but the only motivating case (writing a new whitepaper, surfacing a template) wants the *opposite*: include drafts at low rank. Semantic match + ranking already does that. A hard filter would over-exclude.
3. **Same reasoning that killed R6 (`ingestibility`):** when content can be ranked by relevance, hard filters on coarse status flags shrink the pool the model sees rather than help the model choose. The model is good at ignoring low-ranked drafts when better-ranked approved content exists.

**Considered shape:** per-entry `status: "draft" | "approved" | "template"` enum, filter-only.

**Evidence accumulated as C7 (preserved for history):**

| Project | Motivating | What it showed |
|---|---|---|
| project-codeguard | No | No drafts or templates exposed. |
| codeguard-cli | No | None. |
| secure-ai-tooling | No | None. |
| ws2-defenders | Weakly yes | Template + drafts exist; surface as *useful low-relevance hits* for P10, not noise. |
| ws1-supply-chain | Weakly yes | `contributions/q1-25/` drafts. Same — low rank, not problematic. |
| ws3-ai-risk-governance | No | Entire repo is planning-state; covered by `manifest.status: "draft"`. |
| ws4-secure-design-agentic-systems | No | `whitepaper-template.md`; baseline pattern, no degradation. |
| cosai-tsc | No | `whitepaper_templates/` + `working-documents/`; baseline pattern. |
| cosai-whitepaper-converter | No | None. |
| oasis-open-project | No | All approved governance. |

**What's preserved from C7's life:** an indexer-side observation worth keeping. When a source document has frontmatter declaring `status: "Approved"` or similar (as ws4's whitepapers do), the indexer should lift that into entry-level `tags` (e.g. `tags: ["approved"]`). This gives query-side users an opt-in filter via existing `tags` without a new schema field. Added to `indexer-notes.md`.

**What would reopen this:** a prompt where draft/template hits visibly *confuse* the model or *degrade* the answer (not merely "surface at low rank"). Hasn't happened in ten walks across the workspace's most draft-heavy projects.

**History:** Surfaced Phase 6 (ws2-defenders F-ws2-8). Tracked as deferred C7 through Phases 6–9. Rejected Phase 9 after ten-walk review showed weakly-motivating cases were all benign.

---

### R6 — `ingestibility` (filter: high/medium/low)

**Status:** Rejected (Phase 8 — moved from C2 after six-walk re-evaluation)

**Why rejected:** Six project walks produced zero motivating prompts. Three structural arguments against:

1. **Chunk-per-heading already normalises size for prose.** The "very large reference entry" case mostly doesn't exist after chunking — most entries land at ~1–5KB regardless of the source document's size. Where sub-chunking is still needed (e.g. some whitepaper H2 sections), the fix is an indexer rule (max chunk size, sub-split on H3/H4), not a schema field.
2. **`form` is a stronger and more semantically meaningful proxy.** `form: "structured"` correlates with compact, parametric content; `form: "prose"` correlates with longer-form context. A user wanting "compact directives to apply quickly" filters on `form: "structured"` — which already exists and tells the model *what kind* of content it's getting, not just *how big*.
3. **Token-count-derived enum values are misleading.** They classify by surface size, not by what makes content useful (relevance, density, citability). A 200-word information-dense risk description is more citable than an 80-word stub. The filter would misclassify in both directions.

**Considered shape:**
```json
"ingestibility": "high" | "medium" | "low"
```
Enum on reference entries. Filter-only. Could have been derived from token count.

**Evidence accumulated as C2 (preserved for history):**

| Project | Motivating | What it showed |
|---|---|---|
| project-codeguard | No | Token count alone separates rules (small) from docs (medium). No prompt benefits from this filter. |
| codeguard-cli | No | The large JSON-schema-in-README example has *two* different "ingestibilities" depending on use case (context-load vs. precise-reference). Wrong axis for a hard filter. |
| secure-ai-tooling | No | Multi-form retrieval already lets the model pick the appropriate-size hit. No prompt benefits. |
| ws2-defenders | No | Whitepapers are large but their *chunks* are small (chunk-per-heading). The chunking already handles ingestibility. |
| ws1-supply-chain | No | Same pattern as ws2-defenders — large whitepapers chunked into small sections by H2/H3 boundaries. Ingestibility-as-filter unmotivated. |
| ws3-ai-risk-governance | No | Tiny corpus (~6 chunks). Ingestibility filtering is moot for a project this small. |

**Killed by:** Phase 8 re-evaluation, with the corpus shape from six walks visible. The original motivation ("model with tight context budget should prefer compact hits") doesn't survive contact with how the model actually uses the index — it ranks by relevance, loads summaries, inspects, then expands. Pre-filtering by size shrinks the pool of *what the model gets to see*, which is the wrong direction. Tool-surface concerns about result-set size belong in `search.limit`, not in entry metadata.

**What would reopen this:** A prompt where filtering by size produces a measurably better answer than the same query without the filter — and where neither `form` filtering nor `search.limit` tuning can achieve the same outcome. None seen in six walks.

**History:** Surfaced Phase 4 (project-codeguard's structured rule discussion). Tracked as deferred candidate C2 through Phases 5–8. Moved to Rejected in Phase 8 after fresh six-walk evaluation showed zero motivating prompts plus three structural arguments against.

---

## Summary

**Active deferred candidates: 0.**

**Adopted then removed (1):**
- ~~C8 `builds_on`~~ — promoted in v0.0.4 (Phase 8); removed during implementation phase 1 after the typed-relationship enum proved unreliable to populate. Replaced by `related_urls` (free-string array of repo URLs from README).

**Rejected (12):**
- R1 `semantic_id`
- R2 `presentations`
- R3 split `language`
- R4 `assets.jsonl` corpus
- R5 `equivalents` (superseded by R8)
- R6 `ingestibility` (was C2)
- R7 draft/template `status` filter (was C7)
- R8 `canonical_source` (was C1)
- R9 `executable` (was C3)
- R10 `indexing.ignore` (was C4)
- R11 `linked_ids` (was C5)
- R12 `role` field on packages (was C6)

**State at v0.1.0 cut:** ten project walks produced one adopted candidate (C8 `builds_on`) and twelve rejected candidates. No active deferred candidates remain. The schema is in a stable shape; the next non-trivial change would require new evidence from a project type not yet seen in the workspace.

**Renumbering note:** candidates that were rejected retained their renumbered ID (R6 from C2, R7 from C7, R8 from C1, etc.). The original C-numbers are preserved in history references throughout `_docs/archive/`.
