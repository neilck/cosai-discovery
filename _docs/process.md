# COSAI Discovery — Process Log

A living STAR-format record of how this project is being designed and built. Updated as we go. Newest phase at the bottom.

**STAR** = **S**ituation · **T**ask · **A**ction · **R**esult.

---

## Phase 0 — Project framing

### Situation
When generating with AI agents — whether inside a community of open source projects or inside an enterprise with its own packages — we want to integrate with existing projects (importing a package, or running and connecting to services), copy code directly into our project when a good implementation already exists, bring in context for better decision making, and let humans discover more about existing projects during planning research.

Doing so ensures that:
- Engineering effort isn't wasted re-implementing what already exists, and AI-generated code converges toward the patterns the surrounding community has already validated.
- Decisions made during generation and planning are informed by the full landscape of available work, not just the single repository the agent is sitting in.

**The concrete dataset we'll use to validate this design** is the user's own VS Code workspace: ~11 sibling COSAI OASIS repositories opened together (codeguard-cli, project-codeguard, secure-ai-tooling, ws1–ws4, cosai-tsc, cosai-whitepaper-converter, oasis-open-project, and the empty `cosai-discovery` itself). When working in any one of them with Claude Code today, there is no efficient way for the agent to discover what already exists in the siblings — leading to duplicated work, missed reuse opportunities, and incomplete context during planning. This workspace is rich enough (code + docs + whitepapers + working-group artifacts) to serve as the empirical ground truth against which the index format and tool surface are designed: rather than specifying in the abstract, we will iterate the specifications by walking each project, simulating indexing, and recording where the spec bends or breaks.

### Task
Design and build an MCP server, hosted from `cosai-discovery`, that lets Claude Code (or any MCP client) discover and query content across the sibling projects. The server must support four user-stated goals:

1. Decide whether to write new code vs. import an existing package
2. Decide whether existing code can be cut-and-pasted to solve a problem
3. Surface reference material to include in planning-mode context
4. Answer user questions about the other projects

The architecture must scale horizontally (suggesting a RAG database backing the MCP server), and the server must also expose a tool to generate a per-project **index file** that makes each project discoverable.

### Action
Initial scoping conversation resolved four foundational decisions via `AskUserQuestion`:

- **Scope**: local prototype first (SQLite + sqlite-vec), pluggable backend later — not horizontal scale from day 1.
- **Indexing trigger**: on-demand via MCP tool. No git hooks or CI in v0.
- **Index unit types**: all four — packages, snippets, references, project metadata — **stored separately**.
- **Embeddings**: Voyage (voyage-code-3 for code, voyage-3 for text), Anthropic's recommended embeddings partner.

### Result
A clear north star: a local-first MCP server with on-demand indexing, four-corpus index files committed per-project, Voyage embeddings, SQLite-vec as the local vector store. The architectural shape is settled; the index format and tool surface still need design.

---

## Phase 1 — Index file format v0.0.1

### Situation
With the high-level architecture agreed, the next bottleneck is concrete: what does an index file *look like*? Without a format, neither the indexer nor the query side can be built. The user wanted the format proposed first, then validated by walking real projects rather than designed in the abstract.

### Task
Produce a strawman index file format that:
- Stores the four content types separately
- Is committed to each repo (travels with the code)
- Supports filter dimensions (language, last-updated, tags, etc.)
- Is friendly to incremental updates and diffs

### Action
Proposed a `.cosai-index/` directory per project with:
- `manifest.json` — singleton project metadata
- `packages.jsonl` — importable units
- `snippets.jsonl` — copy-pasteable code
- `references.jsonl` — doc chunks

JSONL chosen for the three corpora for diff/append/stream friendliness; JSON for the singleton manifest. Each entry includes a `content_hash` so re-indexing skips unchanged content. Embedding strategy: voyage-code-3 for code-bearing entries, voyage-3 for prose.

### Result
v0.0.1 index file format documented in [`index-file-format-0.0.1.md`](index-file-format-0.0.1.md). Format intentionally has open questions baked into a dedicated section — the plan is to surface and resolve them while walking real projects, not to over-design upfront.

---

## Phase 2 — MCP tool surface v0.0.1

### Situation
The index format describes the *data at rest*. The MCP tool surface defines *how Claude Code interacts with that data* — both writing it (indexer) and reading it (query). Without this, there's no contract for either the server implementation or the client behaviour.

### Task
Define the minimum tool surface needed to serve the four original user goals, while keeping the API small enough to be coherent and memorable.

### Action
Proposed 8 tools across three groups:
- **Write (3)**: `build_index`, `reindex_all`, `drop_project`
- **Read (4)**: `list_projects`, `search`, `get_entry`, `find_similar`
- **Introspection (1)**: `index_status`

Then **back-checked** the tool surface against each of the four original goals by tracing how the model would actually call them. This surfaced two real gaps:
- Goal 3 (reference material for planning) needed a way to expand from a chunk-hit to the whole doc → added `full_document` to `get_entry.include`.
- Goal 4 (answer project-level questions) needed a way to aggregate hits by project → added `group_by: "project"` to `search`.

Two minor tools considered (`summarize_project`, `explain_choice`) and dropped because they were derivable from the existing surface or belonged in prompts, not tools.

### Result
v0.0.1 tool surface documented in [`mcp-tool-surface-0.0.1.md`](mcp-tool-surface-0.0.1.md). The hot path is `list_projects → search → get_entry`. The back-checking step proved valuable — it caught real gaps that a forward design pass missed. Worth doing again at each version bump.

---

## Phase 3 — Walk real projects to validate the format

### Situation
v0.0.1 of both the format and the tool surface are clean-room designs. Until they meet real project shapes, we don't know what's wrong. The user's workspace contains 11 sibling projects spanning code, docs, whitepapers, and working-group artifacts — a rich validation set.

### Task
Walk each project in order, simulate what its index files would look like, identify mismatches between the format and the project's reality, and iterate the format accordingly. Track progress and findings in a dedicated log so future sessions can resume.

### Action
Created [`project-walkthrough-log.md`](project-walkthrough-log.md) as the per-project findings ledger. Defined a status legend (⬜ / 🟡 / ✅ / 🔁) and an explicit queue with a priority ordering:

1. project-codeguard
2. codeguard-cli
3. secure-ai-tooling
4. ws2-defenders
5. ws1-supply-chain
6. ws3-ai-risk-governance
7. ws4-secure-design-agentic-systems
8. cosai-tsc
9. cosai-whitepaper-converter
10. oasis-open-project
11. cosai-discovery (self)

Decided to **accumulate findings across multiple projects** before bumping the schema version, rather than re-revising the spec after each project. Target: bump to v0.1.0 after the first four projects in the queue.

#### Candidate fields and the evidence-threshold pattern

As findings accumulate, three categories of change emerge:

1. **Resolved** — clear win, applied to the spec at the next version bump.
2. **Deferred candidate fields** — plausible additions motivated by one project, but not yet justified across the broader workspace. These are tracked explicitly in the spec's "candidate fields" section with **why they were deferred**, so a future session can see what was on the table and why it wasn't taken.
3. **Rejected** — explicitly considered and ruled out, with reasoning preserved in the decisions log so we don't relitigate.

The rule for promoting a candidate field from deferred → in spec is an **evidence threshold**: typically ≥2 projects independently producing motivation for the same addition. This prevents over-fitting the schema to whichever project we walked first (which would feel insightful but produce a project-codeguard-shaped schema unsuited to the rest). It also prevents the opposite failure — adding fields speculatively because they *might* be useful.

A candidate field's lifecycle:

- **Surfaced** in walking one project; logged in that project's findings with the case that motivated it.
- **Recorded** in the next spec version's "candidate fields — deferred" section, listing where/what/why.
- **Watched** as subsequent projects are walked. Each project either reinforces (second motivating case) or weakens (a project that *should* have needed it but didn't) the candidate.
- **Promoted** to the schema when the evidence threshold is met, or **dropped** if multiple projects pass through without needing it.

This treats the spec as a hypothesis-tracking document, not a wishlist. Each candidate field carries its own provisional status — "maybe" — and the walk-through is the experiment that resolves it.

#### Evaluation prompts

A fixed list of ten realistic user prompts (in [`evaluation-prompts.md`](evaluation-prompts.md)) anchors every project walk. The prompts cover all four original user goals and are written in the user's voice — what someone building a COSAI-related project would actually type into Claude Code. Examples: *"Is there an existing package in the COSAI workspace that abstracts LLM provider selection?"* (Goal 1), *"What AI risk taxonomies exist that I could map a CISO dashboard to?"* (Goal 3), *"Which projects ship runnable tools vs. documentation-only?"* (Goal 4).

For each project, the walk records whether each prompt would surface useful hits from that project, and what entries it would contribute. This grounds schema decisions in retrieval reality rather than schema aesthetics: a candidate field only earns promotion when a real prompt fails or degrades without it — project shape alone is not evidence.

The list is small on purpose (ten). Enough to exercise breadth across goals; small enough that each walk-through stays an evaluation rather than a benchmarking exercise.

#### Phase 3.1 — project-codeguard (✅ analyzed)

**Findings:** the project broke v0.0.1 in six concrete ways:
- 110 structured rule markdowns don't fit cleanly into any of the three corpora
- `src/codeguard-mcp/` has its own `pyproject.toml` — nested-package rule needed
- `project_kind` enum is insufficient (project is library + CLI + docs + rules-shipper + skills-shipper)
- `languages` conflates project-source language with subject-matter languages
- `ecosystem: "none"` is too coarse (need `source`, `vendor`, `claude-plugin`)
- Claude-code skills are runnable markdown — neither code snippets nor passive docs

Six schema-change recommendations and four open questions logged in the walkthrough doc.

### Result
**In progress.** project-codeguard analyzed and logged. Format proved usefully fragile — surfacing genuine gaps rather than nitpicks. Confidence growing that the "walk projects, then revise" approach is sounder than designing forward. Next decision point: resolve open questions before moving to codeguard-cli, or accumulate more findings first.

---

## Phase 4 — Resolve open questions before continuing the walk

### Situation
After project-codeguard, the open-questions list grew to ~19 items across three buckets: project-specific findings (A1–A9), spec carryovers (B1–B8), and tool-surface details (C1–C4 + meta). Continuing to walk projects against an unresolved spec risks producing findings that conflict with later resolutions, forcing re-analysis.

### Task
Triage the open questions, propose recommendations with reasoning for each, and reach decisions before walking the next project. Capture the decisions so the spec can be bumped cleanly at the agreed cadence.

### Action
*(In progress.)* The pattern being used to work through these:

1. **Surface and group.** All open questions are listed in one place and grouped by where they came from (project-specific findings vs. spec carryovers vs. tool surface).
2. **Triage by urgency.** Questions are sorted into "must resolve before the next project walk," "should resolve" (cheap to do now, hard to retrofit), and "can defer" (no impact on the next 1–2 projects, or no schema cost).
3. **One question at a time, conversationally.** The user picks a question; Claude lays out the real shape of the problem (what the question is actually asking, often two distinct questions hiding under one), enumerates 3–5 named options with pros/cons, and gives a recommendation with reasoning.
4. **Decision recorded immediately.** Once the user picks, the decision is written to the Decisions log below — marked `Tentative` so it can be revisited as later projects surface counter-evidence.
5. **Remaining queue re-summarized.** After each decision, the still-open questions are re-listed so the user always knows what's left.

Recommendations are drafted for all 19 questions, but only ~5 need resolution before the next project walk; the rest can ride. Decisions will roll into v0.0.2 (or v0.1.0 if the user prefers to accumulate further).

### Decisions log

| ID | Question | Decision | Status |
|---|---|---|---|
| Q-A3 | How to handle projects that are a mix of kinds? | Use `primary_kind` (single value) + `also` (array). Constrained enum: `library`, `cli`, `service`, `claude-plugin`, `ruleset`, `docs`, `whitepaper`, `working-group`, `dataset`, `template`. Primary = the consumer-facing answer to "what did I get?" | Tentative — revisit as further projects are walked |
| Q-A1 | Where do structured project-native assets (rules, skills, prompts) live? | **Stay in `references.jsonl`.** Reframe: same knowledge can come in different forms; difference is form/ingestibility, not category. Add two fields: `form` (enum: `prose` \| `structured` \| `mixed`) and `structure_description` (free text describing the structure, included in the embedding input alongside `summary`). | Tentative |
| Q-A1.1 | Embed/filter/store invariant for future fields | Establish as a working principle: every new field must declare whether it's **embedded** (contributes to vector match), **filterable** (hard filter at vector store), or **reference-only** (stored, not retrieved). Drives the choice between enums and free text. | Adopted |
| Q-A1.2 | Candidate fields for later: `ingestibility`, `executable`, `equivalents` | **Defer.** Recorded as candidate fields motivated by Q-A1 but not added in v0.0.2. Promote when ≥2 projects produce evidence the filter/link is actually needed in queries. | Deferred |
| Q-A6 | `executable: boolean` for runnable references? | **Folded into Q-A1.2 (deferred).** Same evidence threshold applies. | Deferred |
| Q-A4 | Split `languages` into `code_languages` / `subject_languages`? | **No split.** `language` (and `manifest.languages`) means **implementation language only**, full stop. Subject-matter languages are not given a dedicated field — they're captured in `summary` and `structure_description` where the embedding picks them up. `tags` may carry languages opportunistically but no field requires them. Trade-off: lose hard filtering by subject language; semantic match does the job more faithfully. Revisit if "all rules that apply to language X" queries underperform repeatedly. | Tentative |
| Q-A4.1 | Where does language/kind filtering actually happen? | **At the entry level, not the manifest.** A mixed project (e.g. Go backend + TS frontend) must decompose into multiple entries — one per coherent unit. `manifest.languages` becomes a **derived union** used only for coarse project-level discovery in `list_projects`; `search` filters always apply at the entry level where each answer is single and unambiguous. Establishes the **granularity rule**: every entry must be specific enough that filterable fields have one answer. | Tentative |
| Q-A5 | Expand the `ecosystem` enum on packages | Adopt **flat enum, add values**: `pypi`, `npm`, `go`, `cargo`, `source`, `vendor`, `claude-plugin`, `mcp-server`, `none`. Single value per package (pick the consumption-facing answer); install mechanics live in the free-text `install` field. Hold other registries (`oci`, `nuget`, `maven`, etc.) until evidence demands them. | Tentative |
| Q-A4.2 | Optional `role` field on packages (backend/frontend/worker/etc.)? | **Defer.** Candidate field, motivated by the mixed-project case, but no project in the queue yet *requires* it for disambiguation — decomposing into multiple package entries with their own `language` + `name` is sufficient. Promote when a real query needs role-based filtering. | Deferred |

### Result
Five questions resolved (Q-A3, Q-A1, Q-A1.1, Q-A4, Q-A4.1, Q-A5), three deferred (Q-A1.2, Q-A6, Q-A4.2). The most consequential outcome was Q-A4.1: filtering by language/kind belongs at the **entry level**, not the manifest. This became the **granularity rule** — each entry must be specific enough that filterable fields have a single answer. It reshaped how the schema is read: the manifest summarises, entries are the truth.

The embed / filter / store invariant (Q-A1.1) and the granularity rule (Q-A4.1) are the two load-bearing additions from this phase. Together they make the schema's typing decisions (free text vs. enum, manifest vs. entry) deterministic instead of case-by-case.

Decisions packaged into v0.0.2 ([`index-file-format-0.0.2.md`](index-file-format-0.0.2.md)).

---

## Phase 5 — Index file format v0.0.2

### Situation
With six decisions from Phase 4 ready to land, v0.0.1 was no longer accurate. Continuing to walk projects against a stale spec would conflate fresh findings with already-resolved ones. v0.0.1 stays frozen as a historical snapshot; v0.0.2 becomes the working spec.

### Task
Cut v0.0.2 as a fresh document (not a patch over v0.0.1) that:
- Documents the two load-bearing principles (embed/filter/store, granularity rule) up front.
- Reshapes the manifest and reference schemas per the resolved decisions.
- Extends `ecosystem` cleanly without inflating the enum.
- Calls out deferred candidate fields so they remain visible for future evidence.
- Restates the layout to make clear that multiple entries per file is the normal case for any non-trivial project.

### Action
Wrote [`index-file-format-0.0.2.md`](index-file-format-0.0.2.md) with:
- A "What changed since v0.0.1" header.
- The embed/filter/store invariant promoted to a dedicated section.
- The granularity rule promoted as load-bearing, before any field definitions, with consequences spelled out.
- Layout section explicit about JSONL carrying many entries by design.
- Per-corpus sections updated for the new fields (`form`, `structure_description` on references; extended `ecosystem` enum on packages).
- A "Candidate fields — deferred" table preserving Q-A1.2 / Q-A6 / Q-A4.2 with rationale.
- Carried-forward open questions reduced to six items that genuinely need walk-through evidence.

### Result
v0.0.2 is the working spec. The MCP tool surface doc remains at v0.0.1 — no decisions in this phase changed it. The next project walk (codeguard-cli) targets v0.0.2.

---

## Phase 6 — Anchor evaluation in realistic user prompts

### Situation
By the third project walk (secure-ai-tooling), a drift had appeared in how schema decisions were being made. Each project surfaced *shapes* the schema could conceivably accommodate — duplicate forms of the same data, cross-project artifact snapshots, multi-implementation snippets — and each shape triggered a proposal for a new field (`semantic_id`, `presentations`, `canonical_source`, `equivalents`, `indexing.ignore`, `linked_ids`). The proposals were defensible on aesthetic grounds: the schema *could* be more expressive.

But the question that kept surfacing in the conversation — most pointedly during the discussion of single-entry-with-presentations vs. multi-entry references — was whether any of these additions would actually *change retrieval* for queries a real user would issue. When traced through a concrete example ("I want to create a dashboard for a CISO that shows known security exceptions against higher-level risks"), almost all of the proposed additions turned out to be unnecessary: v0.0.2's existing `summary`, `structure_description`, `form`, `tags`, and `path` fields served the query end-to-end. The proposals weren't wrong; they were premature.

The risk was clear: continue walking projects this way and the schema would grow to fit *project shapes*, not *user needs*. A schema fit to shapes feels insightful in design discussion but produces a corpus the user's actual queries don't benefit from.

### Task
Introduce a discipline that grounds every schema decision in a concrete user query, and apply it retroactively to the candidate fields already in flight. Make the discipline visible in the process so future walks can't drift back into shape-driven design.

### Action
Two changes landed:

1. **A fixed list of ten realistic user prompts** in [`evaluation-prompts.md`](evaluation-prompts.md), each phrased in the user's voice rather than the schema's. The prompts cover all four original user goals (write-vs-import, cut-and-paste, planning context, project questions) and were chosen to be specific (CISO dashboard, MCP server scaffolding, threat-modeling a RAG feature) rather than abstract. Specificity was deliberate — abstract prompts hide retrieval failures; specific ones expose them.

2. **Two new working principles** (#9 and #10): schema discipline ("candidate fields stay deferred unless a real query demands them — project shape alone is not evidence"), and prompt-anchored evaluation ("each project walk runs the fixed prompt list against what the index would return"). These join the earlier principles as part of the standing how-we-work guide.

The list is small on purpose. Ten prompts is enough to exercise breadth across the four goals without turning every walk into a benchmarking exercise. The list is explicitly open to growth: a project that surfaces a query the current ten don't cover earns a new prompt; redundant prompts get pruned.

### Result
The schema discipline now has teeth. Every candidate field has a concrete bar to clear: *which prompt would degrade without it?* Applied retroactively, this leaves all the candidate fields proposed in Phases 3–5 — `equivalents`, `canonical_source`, `semantic_id`, `presentations`, `indexing.ignore`, `linked_ids` — still deferred, because none of the ten prompts demonstrably needs them. v0.0.3, when cut, can be a *clarifications-only* release with no schema growth, which itself signals how the project is being run.

A secondary effect: it makes the walk-through faster. Instead of speculating about every shape a project exhibits, each walk asks the same ten questions and records whether the schema served them. Findings become comparable across projects.

---

## Phase 7 — Reorganise docs after four walks

### Situation
After the fourth project walk (ws2-defenders), the working docs had drifted out of shape:
- `project-walkthrough-log.md` had grown to several hundred lines of dense per-project analysis, with candidate-field evidence buried in prose rather than tabulated against the candidate.
- Candidate fields were tracked in **three places** — a section in `index-file-format-0.0.2.md`, scattered rows in `process.md`'s decisions log, and prose findings inside the walkthrough log — none of which gave a clean per-candidate evidence picture.
- The walkthrough log mixed two purposes: long-form analysis for one project (useful at the time it's written) and the cumulative "what's still pending" view (useful for planning the next walk). The first crowds out the second.
- A v0.0.3 release was overdue. The four walks plus the Phase 6 re-evaluation had produced enough confirmed direction to land, but the spec wasn't cut.

### Task
Reorganise the documentation around three principles:
1. **One source of truth per concern.** Schema → `index-file-format-X.Y.Z.md`. Candidate changes → one dedicated doc. Per-project findings → walkthrough log. Process/why-we-work-this-way → `process.md`. Implementation hints → `indexer-notes.md`. Each doc references the others rather than duplicating their content.
2. **Compact-by-default with archived long-form.** The walkthrough log carries five-bullet summaries + the prompt verdict grid. Detailed per-project analysis lives in `_docs/archive/` and is linked.
3. **Evidence per candidate, not prose per project.** Candidate changes get their own evidence table, one row per project, so the promotion case (or rejection case) is visible at a glance.

### Action
Five concrete changes landed:

1. **Created [`candidate-changes.md`](candidate-changes.md)** as the single source of truth for deferred and rejected schema changes. Each candidate has a `Status`, a motivation, proposed shape, **per-project evidence table**, promotion threshold, and history. Tracks rejected candidates too, so future sessions don't re-litigate them.

2. **Cut [`index-file-format-0.0.3.md`](index-file-format-0.0.3.md)** as a clarifications-only release. No new schema fields. Closes four open questions (snippet heuristics, PDF-vs-markdown, README-vs-docs, cross-project links), tightens the nested-manifest rule, and clarifies license handling (optional + SPDX expressions). The spec no longer carries a "candidate fields" section — it points at the dedicated doc.

3. **Archived the long-form walkthrough log to [`archive/project-walkthrough-log-v0.0.2.md`](archive/project-walkthrough-log-v0.0.2.md).** Keeps the detailed analysis browseable without bloating the active working doc.

4. **Created a fresh compact [`project-walkthrough-log.md`](project-walkthrough-log.md)** with: a status table for the project queue; a template for future walks; per-project compact summaries (five-bullet findings + prompt verdict grid + candidate evidence pointer + link to the archived long-form). Stops being the place where candidate evidence accumulates — that moved to `candidate-changes.md`.

5. **Updated this Phase 7 entry** so the reorganisation itself is captured as a process moment, not just a doc reshuffle. Future sessions can see why the docs are shaped the way they are.

### Result
The doc set is now clean for the second half of the project queue:

- `_docs/index-file-format-0.0.3.md` — current schema
- `_docs/mcp-tool-surface-0.0.1.md` — current tool surface (unchanged through Phases 3–6)
- `_docs/candidate-changes.md` — deferred + rejected, with evidence per project
- `_docs/project-walkthrough-log.md` — compact summaries + queue status
- `_docs/evaluation-prompts.md` — the ten prompts driving evaluation
- `_docs/indexer-notes.md` — implementation hints separate from spec
- `_docs/process.md` — this doc; STAR-format process log + working principles
- `_docs/archive/` — historical long-form analysis

Walks 5–11 will follow the compact format and update candidate-changes' evidence tables directly.

---

## Phase 8 — First adopted candidate (v0.0.4)

### Situation
After Phase 7's reorganisation, walks 5–7 (ws1-supply-chain, ws3-ai-risk-governance, ws4-secure-design-agentic-systems) added evidence to the candidate-changes ledger. Two notable patterns emerged:

1. **C2 (`ingestibility`) reached six walks with zero motivating prompts.** A fresh re-evaluation alongside the corpus shape from those six walks produced three structural arguments against the field: chunk-per-heading already normalises size; `form` is a stronger proxy than size; token-count-derived enums misclassify by surface rather than relevance. C2 was moved to Rejected as R6 mid-Phase 8.

2. **C8 (`builds_on`) reached three concrete cases.** codeguard-cli consumes project-codeguard rules; ws3 was donated from Project CodeGuard; ws4 explicitly implements controls from secure-ai-tooling's Risk Map and cites cosai-tsc's published principles. The pattern was structurally real — but working principle #9 (schema discipline) requires *prompt evidence*, not shape evidence, for promotion. Three options surfaced: (A) add a prompt and create the evidence; (B) keep deferring; (C) promote on shape alone.

### Task
Resolve C8 without abandoning working principle #9. Either keep deferring (until a real user prompt motivates) or promote with a *designed shape* that justifies its complexity — and immediately add a prompt to validate the field on the remaining walks. Avoid the trap of fitting a prompt to a candidate; the prompt must correspond to a query a real user would issue.

### Action
Five steps:

1. **Designed the shape of `builds_on`** before deciding to promote. Considered four options (bare slug array, slug + relationship, slug + relationship + scope, manifest + entry-level split). Landed on **manifest-level typed array**: `{project, relationship, uri}` where `relationship` is a constrained enum (`extends | implements | consumes | cites | donated_from`) and `uri` is an optional hint. The design preserves three AI use cases: forward traversal ("what does X build on?"), reverse traversal ("what builds on X?"), and *kind*-aware filtering ("show me implementations of X, not citations").

2. **Promoted C8 to Adopted** in `candidate-changes.md` with full history preserved — the evidence table that justified promotion, the design rationale, and the decision context.

3. **Cut [`index-file-format-0.0.4.md`](index-file-format-0.0.4.md)** with `builds_on` added to the manifest schema. Resolved open question #2 (notebook handling) as a clarification. First non-clarification release since v0.0.2.

4. **Added P11 to [`evaluation-prompts.md`](evaluation-prompts.md)**: *"Which COSAI projects extend Project CodeGuard?"* — a reverse-traversal query that exercises `builds_on`. The prompt was added simultaneously with the field's promotion, so the remaining four walks (cosai-tsc, cosai-whitepaper-converter, oasis-open-project, cosai-discovery) validate retrieval against it.

5. **Moved C2 to R6 (Rejected)** in the same phase, with three structural arguments preserved in the rejection section.

### Result
v0.0.4 is the working spec. The candidate-changes ledger now has three sections (Deferred, Adopted, Rejected) rather than two — the Adopted section preserves the case for promoted fields so future sessions can see *why* and *based on what evidence*.

The schema-discipline principle (working principle #9) gained a nuance worth noting: **shape evidence plus a designed schema plus a validating prompt** is sufficient justification. Without the prompt, shape evidence alone would have been a violation of #9. The prompt's presence converts the next four walks from "passive observation" to "active validation" — if semantic search handles "which projects extend Project CodeGuard?" cleanly without `builds_on`, the field was a mistake; if not, it earned its keep.

This avoids the failure mode (fitting prompts to candidates) by anchoring the prompt in a real user need (workspace discovery is a documented user goal) and committing to demote the field if subsequent walks show the prompt resolves without it.

---

## Working principles

A few principles have emerged from the way this project is being run. Capture them so future phases don't drift from them:

1. **Design against real data, not in the abstract.** Specs that meet real projects break in instructive ways. Spec-first then validate beats spec-and-build.
2. **Back-check every API against the user goals.** A forward design pass misses gaps that tracing real call sequences catches.
3. **Bake "open questions" into specs deliberately.** Don't pretend a v0 is final. A dedicated open-questions section per doc is cheaper than rewriting later.
4. **Track work in living docs, not in-conversation memory.** `project-walkthrough-log.md`, `process.md`, and the versioned format/surface docs survive context boundaries.
5. **Accumulate findings, then revise.** Don't bump schema versions after every finding — let patterns emerge across multiple projects.
6. **Decisions are conversational, not prescriptive.** Claude proposes — surfacing the real shape of the question, named options with trade-offs, and a recommendation with reasoning. The user decides. Decisions are recorded as `Tentative` and revisited when later evidence warrants. Neither party drives alone: Claude does the analysis and option-generation; the user steers the direction and applies judgment that Claude can't (taste, project-history context, intent).
7. **Triage before resolving.** Not every open question deserves the same treatment. Sort into "must resolve now" (blocks the next concrete step), "should resolve now" (cheap now, expensive to retrofit), and "can defer" (low-cost defaults, or won't recur soon). Resolving everything at once burns time and locks in decisions before evidence arrives.
8. **One question at a time.** When working through a list of decisions, pull the next one, do it justice (real shape + options + recommendation), record the outcome, then re-summarize what's left. Batches feel efficient but skip the depth that catches "this is actually two questions hiding under one."
9. **Schema discipline: candidate fields stay deferred unless a real query demands them.** When walking a project, it is tempting to add a field every time the project's shape *could* use one. Resist. A field is justified only when a concrete user query — phrased in the user's voice, not the schema's — would fail or degrade without it. Project-shape alone is not evidence; user-query is.
10. **Project evaluation is anchored in realistic user prompts.** Each project walk includes running a fixed list of representative prompts (across all four original user goals) against what the index *would* return for that project. This grounds the analysis in retrieval reality rather than schema aesthetics, and surfaces queries the schema can already serve from those it cannot.
11. **Reversible local actions are free; commits/pushes/deletes are not.** No tooling has been built yet, so this principle is mostly a placeholder for the implementation phase.
