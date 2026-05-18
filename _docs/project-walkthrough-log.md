# Project Walkthrough Log

Compact per-project summaries. For each completed walk: a status row, five-bullet key findings, the prompt-driven verdict grid, and links to the long-form analysis (archived).

**Candidate changes and their evidence are tracked in [`candidate-changes.md`](candidate-changes.md), not here.**

**Schema decisions are recorded in the current spec ([`index-file-format-0.0.3.md`](index-file-format-0.0.3.md)).**

## Status

| # | Project | Status | Walked against | Notes |
|---|---|---|---|---|
| 1 | project-codeguard | ✅ | v0.0.1 → v0.0.2 → re-eval | See compact summary below |
| 2 | codeguard-cli | ✅ | v0.0.2 → re-eval | See compact summary below |
| 3 | secure-ai-tooling | ✅ | v0.0.2 → re-eval | See compact summary below |
| 4 | ws2-defenders | ✅ | v0.0.2 + prompt eval | See compact summary below |
| 5 | ws1-supply-chain | ✅ | v0.0.3 | See compact summary below |
| 6 | ws3-ai-risk-governance | ✅ | v0.0.3 | See compact summary below |
| 7 | ws4-secure-design-agentic-systems | ✅ | v0.0.3 | See compact summary below |
| 8 | cosai-tsc | ✅ | v0.0.4 | See compact summary below |
| 9 | cosai-whitepaper-converter | ✅ | v0.0.4 | See compact summary below |
| 10 | oasis-open-project | ✅ | v0.0.4 | See compact summary below |
| 11 | cosai-discovery (self) | ⬜ | special case — host project | |

**Legend:** ⬜ Not started · 🟡 In progress · ✅ Analyzed · 🔁 Re-analysis needed

## Template (for future walks)

When walking a project, create a new section using this shape:

```
### N. <project-name>

**Analyzed:** YYYY-MM-DD · **Commit:** `<sha>` · **Walked against:** vX.Y.Z

#### Key findings
- (3–5 bullets, each ≤2 lines)

#### Prompt-driven verdict grid
| Prompt | Verdict | Notes |
| P1 (LLM provider wrapper)            | Hit / Partial / Miss | one-line |
| P2 (MCP server scaffolding)          | ... | ... |
| P3 (file-hash skip pattern)          | ... | ... |
| P4 (versioned-content manager)       | ... | ... |
| P5 (YAML cross-ref validator)        | ... | ... |
| P6 (CISO dashboard against risks)    | ... | ... |
| P7 (RAG-feature threat modeling)     | ... | ... |
| P8 (hardening AI-generated code)     | ... | ... |
| P9 (which projects ship runnables?)  | ... | ... |
| P10 (supply-chain position paper)    | ... | ... |
**Score:** X Hit / Y Partial / Z Miss

#### Candidate field evidence
- New rows for affected candidates in [`candidate-changes.md`](candidate-changes.md): which candidate, what this project showed.

#### Schema changes proposed
- (If any.) Otherwise: "None — v0.0.3 held."

#### Long-form analysis
- [`archive/project-walkthrough-log-vX.Y.Z.md#N-<project-name>`](archive/project-walkthrough-log-vX.Y.Z.md)
```

The long-form analysis (per-finding sections, options-considered, full reasoning) lives in the archive. This doc carries the executive summary.

---

## Completed walks (compact)

### 1. project-codeguard

**Analyzed:** 2026-05-18 · **Commit:** `dddb5c3b` · **Walked against:** v0.0.1, re-evaluated against v0.0.2.

#### Key findings
- 110 structured rule markdowns + 2 packages + plugin manifest + MkDocs site. The richest test of v0.0.1 — drove the Phase 4 reshape into v0.0.2.
- Motivated `primary_kind` + `also` (replaces single `project_kind`), `form` + `structure_description` on references, extended `ecosystem` enum (added `source`, `vendor`, `claude-plugin`, `mcp-server`).
- Nested-package rule (`src/codeguard-mcp/` has its own `pyproject.toml`) confirmed; tightened in v0.0.3 to require `[project]` table, not just file presence.
- Hosts the canonical rule corpus that codeguard-cli snapshots — the one strong motivating case for the `canonical_source` candidate (C1).

#### Prompt-driven verdict grid
| Prompt | Verdict | Notes |
|---|---|---|
| P1 (LLM provider wrapper) | Miss (legitimate) | Doesn't ship one. |
| P2 (MCP server scaffolding) | Hit | `pkg:project-codeguard/codeguard-mcp` surfaces via nested-manifest rule + `ecosystem: "mcp-server"`. |
| P3 (file-hash skip pattern) | Miss (legitimate) | n/a. |
| P4 (versioned-content manager) | Partial | Conversion machinery is related but not the same pattern. |
| P5 (YAML cross-ref validator) | Miss (legitimate) | Rules are markdown, not cross-referenced YAML. |
| P6 (CISO dashboard against risks) | Partial | Rules are code-level, not risk-taxonomy; secure-ai-tooling weighs higher correctly. |
| P7 (RAG-feature threat modeling) | Hit | Input-validation and MCP-security rules surface for prompt-injection. |
| P8 (hardening AI-generated code) | Hit | Core use case — rules, skill, agent all surface. |
| P9 (which projects ship runnables?) | Hit | `also: ["library","cli","service","claude-plugin","docs"]` makes it surface. |
| P10 (supply-chain position paper) | Hit | Supply-chain rules cited as code-level controls. |

**Score:** 5 Hit / 2 Partial / 3 Miss (all legitimate).

#### Candidate field evidence
- **C1 `canonical_source`:** project-codeguard is the *canonical source* — no other project's content is copied here. Doesn't motivate the field from its own side; the case lives in codeguard-cli's row.

#### Schema changes proposed
- Phase 4 reshape into v0.0.2 (`primary_kind` + `also`, `form` + `structure_description`, extended `ecosystem`). All landed.

#### Long-form analysis
- [`archive/project-walkthrough-log-v0.0.2.md`](archive/project-walkthrough-log-v0.0.2.md) — see section 1.

---

### 2. codeguard-cli

**Analyzed:** 2026-05-18 · **Commit:** `98cbfa33` · **Walked against:** v0.0.2.

#### Key findings
- Clean single-package Python CLI. Granularity rule held without strain — same-language, same-ecosystem internal modules don't need decomposition.
- Ships a snapshot of project-codeguard's rules at `rules/` — byte-identical content. **The one strong motivating case for C1 (`canonical_source`)** — appeared in P7 and P10 as duplicate hits across the two projects.
- No LICENSE file at all → v0.0.3 clarifies `license` is optional, omit when absent.
- `status: "draft"` confirmed in real use ("99% AI-written, fails its own checks") — validates Q-B2 ("status declared, not derived").
- `examples/`-as-snippet-source heuristic was implicit here; confirmed by ws2-defenders later.

#### Prompt-driven verdict grid
| Prompt | Verdict | Notes |
|---|---|---|
| P1 (LLM provider wrapper) | Hit | `codeguard/llm.py` — multi-provider abstraction. Confirms `language: "python"` + `ecosystem: "source"` filtering. |
| P2 (MCP server scaffolding) | Miss (legitimate) | Doesn't ship one. |
| P3 (file-hash skip pattern) | Hit | `recheck.py` + `checker.py` — SHA256 skip pattern surfaces directly. |
| P4 (versioned-content manager) | Hit | `updater.py` — rules-version manager. Semantic match on functionality. |
| P5 (YAML cross-ref validator) | Miss (legitimate) | n/a. |
| P6 (CISO dashboard) | Miss (legitimate) | Tool, not a taxonomy. |
| P7 (RAG-feature threat modeling) | Partial | Bundled rule snapshots produce duplicate hits with project-codeguard. **C1 evidence.** |
| P8 (hardening AI-generated code) | Hit | The tool's whole purpose; README "About" matches directly. |
| P9 (which projects ship runnables?) | Hit | `primary_kind: "cli"`. `status: "draft"` lets users filter further. |
| P10 (supply-chain position paper) | Partial | Same snapshot-duplication caveat as P7. **C1 evidence.** |

**Score:** 5 Hit / 2 Partial / 3 Miss (all legitimate).

#### Candidate field evidence
- **C1 `canonical_source`:** strong motivating case. P7 + P10 both show duplicate-hit noise with project-codeguard's source rules.

#### Schema changes proposed
- v0.0.3 clarification: `license` optional, omit when absent.

#### Long-form analysis
- [`archive/project-walkthrough-log-v0.0.2.md`](archive/project-walkthrough-log-v0.0.2.md) — see section 2.

---

### 3. secure-ai-tooling

**Analyzed:** 2026-05-18 · **Commit:** `01fc50d8` · **Walked against:** v0.0.2.

#### Key findings
- The CoSAI Risk Map: 10 YAML data files (28 risks, 35 controls, 26 components, 10 personas), 13 schemas, 12 generated tables, 19 docs, validators, a static-site Explorer. First real `primary_kind: "dataset"` case.
- **Resolves the granularity question for structured YAML data:** one entry per *item*, not per *file*. The 28 risks become 28 reference entries with `form: "structured"`. This unlocks P6 (the CISO dashboard prompt) and P7.
- Generated content (`tables/*.md`, `svg/*.svg`) appears in the corpus but **doesn't break retrieval** — prompt re-evaluation found the canonical YAML entries rank higher. C4 (`indexing.ignore`) stays deferred.
- No installable packages. `pyproject.toml` is tool-config-only; nested-manifest rule (tightened in v0.0.3) correctly skips it.
- Validators (`validate_riskmap.py`, `validate_framework_references.py`) are textbook snippet material; surface for P5.

#### Prompt-driven verdict grid
| Prompt | Verdict | Notes |
|---|---|---|
| P1 (LLM provider wrapper) | Miss (legitimate) | Dataset, not a tool. |
| P2 (MCP server scaffolding) | Miss (legitimate) | n/a. |
| P3 (file-hash skip pattern) | Miss (legitimate) | n/a. |
| P4 (versioned-content manager) | Miss (legitimate) | n/a. |
| P5 (YAML cross-ref validator) | Hit | `riskmap-validator`, `framework-reference-validator` snippets surface directly. |
| P6 (CISO dashboard) | **Hit (strong)** | Per-risk entries + framework-mappings doc + README chunks. Fine-grained YAML decomposition is load-bearing. |
| P7 (RAG threat modeling) | Hit | RAG-related risks + components + controls. Cross-project: pairs with project-codeguard's rules. |
| P8 (hardening AI-generated code) | Partial | Controls covering code-review/AI-assisted dev — secondary to project-codeguard. |
| P9 (runnables filter) | Hit (correctly excluded) | `primary_kind: "dataset"` excludes it from the runnables query. |
| P10 (supply-chain position paper) | **Hit (strong)** | Supply-chain risk and control entries + framework mappings. Cross-project win. |

**Score:** 5 Hit / 1 Partial / 4 Miss (all legitimate).

#### Candidate field evidence
- **C4 `indexing.ignore`:** weakly motivated by shape (generated tables exist), but prompt-driven re-eval found no retrieval degradation. **Stays deferred.**
- **C5 `linked_ids`:** YAML cross-refs are rich but P7 traverses them via follow-up searches. **Stays deferred.**
- **R4 `assets.jsonl` rejection** validated: fine-grained references with `form: "structured"` carry the risk-map data cleanly.

#### Schema changes proposed
- None. v0.0.2 absorbed this project. v0.0.3 doc-clarifies the nested-manifest rule (tool-config-only manifests don't make packages — driven by this walk).

#### Long-form analysis
- [`archive/project-walkthrough-log-v0.0.2.md`](archive/project-walkthrough-log-v0.0.2.md) — see section 3.

---

### 4. ws2-defenders

**Analyzed:** 2026-05-18 · **Commit:** `58c46d78` · **Walked against:** v0.0.2 + prompt-driven evaluation.

#### Key findings
- The richest project walked. Two formally-approved whitepapers (`.md` + `.pdf`), 7 framework reviews, plus the **AITF telemetry framework** — a real multi-language SDK with Python, Go, and TypeScript packages, 10 vendor integrations, 16+ runnable example scripts, OTel collector configs, and Grafana dashboards.
- **First project that genuinely needed the `also` array.** `primary_kind: "working-group"` + `also: ["whitepaper", "library", "dataset"]` makes P9 surface it correctly; without `also` it would have been mis-classified as docs-only.
- **Three sibling SDKs in three languages** stress-tested the granularity rule. Each gets its own package entry with distinct `language` + `ecosystem`; "Go telemetry SDK" filters cleanly to the Go entry alone.
- **Closes three open questions:** `examples/` directory as snippet source (Open Q#1), index markdown skip PDF when both exist (Open Q#3), cross-project complementary content works via semantic match (Open Q#6).
- **Dual license** (`CC-BY-4.0 AND Apache-2.0`) → v0.0.3 clarifies `license` accepts SPDX expressions.
- **C1 (`canonical_source`) gained no new evidence:** framework reviews discussing NIST/OWASP/etc. are *original commentary*, not snapshots. Still 1/2.

#### Prompt-driven verdict grid
| Prompt | Verdict | Notes |
|---|---|---|
| P1 (LLM provider wrapper) | Partial | Has *telemetry collectors* for providers — semantically adjacent. codeguard-cli's `llm.py` remains the primary hit. |
| P2 (MCP server scaffolding) | Partial | `mcp-tracing` snippet and AITF MCP-namespace spec — what you'd add to an MCP server you'd built. |
| P3 (file-hash skip pattern) | Miss (legitimate) | n/a. |
| P4 (versioned-content manager) | Miss (legitimate) | n/a. |
| P5 (YAML cross-ref validator) | Miss (legitimate) | AITF uses OCSF/OTel conventions, not custom YAML. |
| P6 (CISO dashboard) | **Hit (strong)** | Defender-perspective whitepaper chunks + framework reviews + Grafana dashboards. Multi-project complementary retrieval. |
| P7 (RAG threat modeling) | **Hit (strong)** | RAG-tracing snippet + AITF RAG spec + incident-response framework. The cleanest cross-project win. |
| P8 (hardening AI-generated code) | Partial | Incident-response framework contributes operational perspective. |
| P9 (runnables filter) | Hit | `also: ["library", ...]` makes it surface despite `primary_kind: "working-group"`. |
| P10 (supply-chain position paper) | **Hit (strong)** | Whitepaper supply-chain section + framework reviews + AI-BOM generation snippet. |

**Score:** 5 Hit / 3 Partial / 2 Miss (all legitimate).

#### Candidate field evidence
- **C1 `canonical_source`:** **no new evidence** — framework discussions are complementary, not snapshot duplicates. Stays at 1/2.
- **C7 (drafts/templates):** `whitepaper-template.md` and `draft-documents/` exist. P10 surfaces the template as low-relevance — arguably useful (the user is writing a new paper), not noise. Deferred.

#### Schema changes proposed
- None. v0.0.3 doc-clarifies: SPDX-expression licenses, `examples/` snippet convention, markdown-over-PDF rule, nested-manifest tightening.

#### Long-form analysis
- [`archive/project-walkthrough-log-v0.0.2.md`](archive/project-walkthrough-log-v0.0.2.md) — see section 4.

---

## Summary across completed walks

**Prompts × projects matrix** (verdict pooled across 4 projects × 10 prompts = 40 verdicts):

- **20 Hit** — schema served correctly.
- **8 Partial** — schema served, with caveats (mostly duplicate-hit noise from C1's case, or secondary-projects-for-the-query).
- **12 Miss** — all legitimate; project genuinely doesn't have what the prompt asks for.
- **0 retrieval failures attributable to schema gaps.**

**Resolved decisions vindicated by real prompts:** Q-A1 (form + structure_description), Q-A2 (fine-grained YAML entries), Q-A3 (primary_kind + also), Q-A4 (language = implementation only), Q-A4.1 (granularity rule), Q-A5 (extended ecosystem enum), Q-B2 (status declared not derived).

**Candidate fields after four walks:** zero have met the promotion threshold. See [`candidate-changes.md`](candidate-changes.md).

**Next:** ws1-supply-chain against v0.0.3. Specifically watch for: (a) cross-project snapshot patterns that would give C1 a second motivating case; (b) any prompt failures that motivate a deferred candidate.

---

### 5. ws1-supply-chain

**Analyzed:** 2026-05-18 · **Commit:** `cb9523be` · **Walked against:** v0.0.3.

#### Key findings
- A **pure whitepaper repo**. Two formally-approved papers (both with `.md` + `.pdf` pairs): *Establish Risks and Controls for the AI Supply Chain* (V1.0, approved 2025-06-12, ~111KB md) and *Signing ML Artifacts* (approved 2025-09-29, ~43KB md). Plus an RFC template, a ROADMAP, and a `contributions/q1-25/` folder with draft/outline/release-notes.
- **No code**, no installable packages, no SDKs. `manifest.languages: []`. Confirms Q-A4's "languages = implementation language only" — a docs-only project legitimately has zero.
- **First clean test of the markdown-over-PDF rule** (v0.0.3 §reference chunking rules). Both whitepapers have `.md` + `.pdf` pairs. The indexer indexes the markdown; the PDF is skipped. Subject-matter clearly aligns: the user-facing entries are the chunked markdown sections, which is the right outcome.
- **`primary_kind: "whitepaper"`** finally has a real case. project-codeguard never fit `whitepaper`; ws2-defenders has whitepapers + a flagship SDK so it's `working-group` with `also: ["whitepaper", ...]`. ws1-supply-chain is the *cleanest* whitepaper case — two papers, nothing else of comparable weight. The enum value was speculative until now.
- **Excalidraw + PNG asset pairs.** Eight `assets/drawings/*.excalidraw` source files, each with a generated `assets/img/*.png` counterpart. Diagrams referenced from the whitepapers. Both files exist; v0.0.3's baseline ignore correctly skips both (`.png` is in image baseline; `.excalidraw` isn't explicitly listed but is a non-textual binary). **Open question worth tracking:** should `.excalidraw` and similar diagram-source formats be in baseline ignore?

#### Prompt-driven verdict grid
| Prompt | Verdict | Notes |
|---|---|---|
| P1 (LLM provider wrapper) | Miss (legitimate) | No code. |
| P2 (MCP server scaffolding) | Miss (legitimate) | No code. |
| P3 (file-hash skip pattern) | Miss (legitimate) | No code. |
| P4 (versioned-content manager) | Miss (legitimate) | No code. |
| P5 (YAML cross-ref validator) | Miss (legitimate) | No structured YAML. |
| P6 (CISO dashboard) | Hit | "Risks and Controls" whitepaper chunks on AI-specific supply-chain risks would surface — these are exactly the kind of higher-level risks a CISO understands. Pairs with secure-ai-tooling and ws2-defenders for full coverage. |
| P7 (RAG threat modeling) | Partial | "Risks and Controls" covers RAG context enrichment and broader supply-chain risk; less granular than secure-ai-tooling or ws2-defenders' RAG-specific snippets, but valid context. |
| P8 (hardening AI-generated code) | Miss (legitimate) | Whitepaper-level guidance, not code-level rules; project-codeguard remains primary. |
| P9 (runnables filter) | Hit (correctly excluded) | `primary_kind: "whitepaper"`, `also: []`. Excluded from a runnables query, included in a `kind: "whitepaper"` query. |
| P10 (supply-chain position paper) | **Hit (strongest yet)** | This is the workstream's *reason for existing*. The two approved papers cover risks, controls, mitigations, signing, attestations, claimant model. Every section is directly citable. Pairs with secure-ai-tooling's supply-chain risk/control entries and project-codeguard's `codeguard-0-supply-chain-security.md`. |

**Score:** 2 Hit / 1 Partial / 7 Miss (all legitimate — a docs-only project legitimately misses code-pattern prompts).

#### Candidate field evidence
- **C1 `canonical_source`:** **no new evidence.** ws1-supply-chain's whitepapers are original work, not snapshots. The "Signing ML Artifacts" paper *cites* "Risks and Controls" (same workstream) but doesn't copy from it. Cross-references within a project; not the same artifact in two places. Stays at 1/2 (codeguard-cli still the only strong case).
- **C7 (drafts/templates):** `contributions/q1-25/draft.md`, `outline.md`, and `Release-Notes.md` exist as historical contribution drafts. Less prominent than ws2-defenders' draft-documents but same pattern. No prompt's results are degraded by surfacing them — at worst they're low-relevance hits. Stays deferred.
- **R3 (split language) rejection** further validated: `manifest.languages: []` is a perfectly reasonable answer for a whitepaper repo. No temptation to add subject-matter languages here even though "AI supply chain" implicitly involves Python/Go/etc.

#### Schema changes proposed
- None. v0.0.3 held cleanly. One minor question: extend baseline ignore in `indexer-notes.md` to include `.excalidraw` (source-of-diagram binary). Doc clarification only; not a spec change.

#### Long-form analysis
- *(No archive — Phase 7's compact format applies from this walk forward. If long-form analysis is later needed for ws1-supply-chain, it would be added to `_docs/archive/` separately.)*

---

### 6. ws3-ai-risk-governance

**Analyzed:** 2026-05-18 · **Commit:** `d5c7285d` · **Walked against:** v0.0.3.

#### Key findings
- **The smallest workstream repo by far.** Just a charter (in the README's Description section), one SIG scope-and-deliverables doc, two meeting outlines, an RFC template, and the standard governance files. No whitepapers, no code, no datasets.
- **Pure `primary_kind: "working-group"`** with `also: []`. First case where neither `whitepaper` nor `library` nor anything else applies — the deliverables are *planned*, not *delivered*. The repo is the workstream's organizational scaffolding.
- **Cross-project signal:** SIG1 explicitly references Project CodeGuard as a donated foundation ("Leveraging the donation of Project CodeGuard as a critical accelerant"). This is the first time a CoSAI workstream repo **points at another COSAI workspace project** by name. Semantic match should surface this naturally for P8 ("hardening AI-generated code") — and it does — but it's worth noting as a query that crosses project boundaries via prose reference, not via structural link.
- **Manifest:** `languages: []`, `license: "CC-BY-4.0 AND Apache-2.0"`, `status: "draft"` (the SIG deliverables are "Priority: Immediate" / "Medium-Term" — declared but not produced). `status: "draft"` finally has a working-group case to validate it, beyond codeguard-cli's tool case.
- **About 6 reference chunks total.** The README description, the SIG scope doc (broken into ~4 sections), the two meeting outlines. Nothing else.

#### Prompt-driven verdict grid
| Prompt | Verdict | Notes |
|---|---|---|
| P1 (LLM provider wrapper) | Miss (legitimate) | No code. |
| P2 (MCP server scaffolding) | Miss (legitimate) | No code. |
| P3 (file-hash skip pattern) | Miss (legitimate) | No code. |
| P4 (versioned-content manager) | Miss (legitimate) | No code. |
| P5 (YAML cross-ref validator) | Miss (legitimate) | No YAML data. |
| P6 (CISO dashboard) | Partial | The SIG scope doc names "Target Personas: CISO / Security Leadership" and describes a control framework. Surfaces as planning context for the dashboard's framing, but is *planned work*, not delivered guidance. |
| P7 (RAG threat modeling) | Miss (legitimate) | Out of this SIG's scope. |
| P8 (hardening AI-generated code) | **Hit** | The SIG is literally about "Security of AI-Assisted Code Development." Scope doc surfaces directly. Pairs with project-codeguard (the donated foundation) and codeguard-cli (the tool that runs the rules). |
| P9 (runnables filter) | Hit (correctly excluded) | `primary_kind: "working-group"`, no `library`/`cli`/`service` in `also`. Excluded from runnables queries. |
| P10 (supply-chain position paper) | Miss (legitimate) | Out of this workstream's scope. ws1-supply-chain owns this. |

**Score:** 2 Hit / 1 Partial / 7 Miss (all legitimate). Same shape as ws1-supply-chain — small-surface project legitimately misses most prompts.

#### Candidate field evidence
- **C1 `canonical_source`:** **no new evidence.** The reference to Project CodeGuard is *prose-level acknowledgement*, not snapshot duplication. Stays 1/2.
- **C5 `linked_ids`:** weakly motivating signal — the SIG explicitly names Project CodeGuard. But the link is **cross-project, not within-project**, and C5 was originally framed as within-project. Cross-project links would be a different field (subsumed by C1's territory in a slightly different shape — "we cite/build on X"). Doesn't move C5. Tentatively note: if a fifth project produces a similar "explicitly builds on another project" pattern, this might motivate a *new* candidate field (`builds_on: ID` or similar).
- **C7 (drafts/templates):** the entire repo is essentially "draft state" content. `status: "draft"` at the manifest level covers this; no per-entry status field is motivated.

#### Schema changes proposed
- None. v0.0.3 held.
- **Worth tracking:** the "this workstream builds on Project CodeGuard" pattern — if it recurs in ws4 or elsewhere, it might motivate a new candidate. Not promoting yet; just noting.

#### Long-form analysis
- *(None — compact format only.)*

---

### 7. ws4-secure-design-agentic-systems

**Analyzed:** 2026-05-18 · **Commit:** `807f7823` · **Walked against:** v0.0.3.

#### Key findings
- **Substantial whitepaper + practical-guide repo.** Two approved whitepapers as `.md + .pdf` pairs: *Agentic Identity and Access Management* (V1.0, approved 2026-03-20, ~51KB md) and *Model Context Protocol (MCP) Security* (approved 2026-01-08, ~76KB md). Plus two practical guides under `practical-guides/`: *Input and Data Sanitization and Filtering* and *Tool Design for Secure Agentic Systems* (`mcp-secure-tool-design.md`).
- **First notebook-bearing project.** `practical-guides/examples/` has five subdirs each containing a Jupyter notebook (`.ipynb`) plus supporting files (`utils.py`, `dummy_sql.json`, `run_1.json`, `assets/`). These are *runnable security-guardrail demos* — `command_obfuscation`, `direct_guardrails`, `detached_defence`, `function_hijacking`, `output_filtering`. **Resolves v0.0.3 open question #2 (notebook handling)** — see below.
- **First strong cross-project reference.** `mcp-secure-tool-design.md` explicitly cites the CoSAI Risk Map in secure-ai-tooling with deep links to specific risks (e.g. `risks-summary.md#:~:text=PIJ`). The README also points at `cosai-tsc/security-principles-for-agentic-systems.md` as the workstream's published principles. **Third C8 (`builds_on`) data point** — see candidate evidence.
- **`primary_kind: "working-group"` with `also: ["whitepaper"]`.** Two approved whitepapers + two practical guides + executable notebook examples. Without an installable package, `library` is not in `also`.
- **`practical-guides/` is a new content type** — neither pure prose like a whitepaper section nor structured like a YAML risk entry. It reads as long-form *guide* content: 6-principles-style writeups with annotated rationale, example snippets, and pointers to runnable notebooks. v0.0.3's `form: "mixed"` is the right answer.

#### Prompt-driven verdict grid
| Prompt | Verdict | Notes |
|---|---|---|
| P1 (LLM provider wrapper) | Miss (legitimate) | No code/SDK. |
| P2 (MCP server scaffolding) | Hit | MCP Security whitepaper + `mcp-secure-tool-design.md` practical guide directly address what to build into an MCP server. Pairs strongly with project-codeguard's `codeguard-mcp`. |
| P3 (file-hash skip pattern) | Miss (legitimate) | n/a. |
| P4 (versioned-content manager) | Miss (legitimate) | n/a. |
| P5 (YAML cross-ref validator) | Miss (legitimate) | n/a. |
| P6 (CISO dashboard) | Partial | Whitepaper section "2.3 Capability-impact risk framing" and "Risks and failure modes for agents" surface; secondary to secure-ai-tooling's risk-map. |
| P7 (RAG threat modeling) | **Hit (strong)** | MCP Security whitepaper covers prompt injection, input/instruction boundary failures, tool poisoning — directly relevant to RAG-system threats. Practical guide on input sanitization surfaces. Notebooks `direct_guardrails` and `output_filtering` are runnable demos. Pairs with secure-ai-tooling and ws2-defenders for taxonomy + telemetry. |
| P8 (hardening AI-generated code) | Partial | Agentic IAM section on "Authorization and delegation" is relevant context for code-generating agents, but the project's primary focus is *agentic systems at runtime*, not *code generation*. ws3-ai-risk-governance and project-codeguard are stronger hits. |
| P9 (runnables filter) | Hit (correctly excluded) | `primary_kind: "working-group"`, `also: ["whitepaper"]` — no `library`/`cli`/`service`. Excluded from runnables. **But:** the notebooks under `practical-guides/examples/` are *runnable* in a different sense (`.ipynb` snippet entries). If a future prompt asks specifically for "runnable security demos," the snippet corpus would surface them. |
| P10 (supply-chain position paper) | Miss (legitimate) | Out of scope. |

**Score:** 3 Hit / 2 Partial / 5 Miss (all legitimate).

#### Candidate field evidence
- **C1 `canonical_source`:** **no new evidence.** ws4's references to secure-ai-tooling's Risk Map and cosai-tsc's principles are *inline citations with deep links*, not snapshot copies. Stays 1/2.
- **C8 `builds_on`:** **third motivating case.** `mcp-secure-tool-design.md` opens "This cookbook implements controls and mitigations for several key risks in the CoSAI Risk Map." Plus the README's "Published work from this workstream" links to cosai-tsc. This is a project that explicitly **builds on multiple other COSAI projects**. Now **3 cases for C8** (codeguard-cli, ws3, ws4) — promotion threshold could be argued met. But no prompt yet tests for "what builds on X?" — see below.
- **C7 (drafts/templates):** `whitepaper-template.md` exists. Same as ws2/ws1 pattern. No prompt degradation.
- **R6 `ingestibility`:** further validates rejection. The whitepaper sections are large but chunk cleanly; notebooks are snippets, not references. No size-based filter motivated.

#### Schema changes proposed
- **None.** v0.0.3 held.
- **Resolves open question #2 (notebook handling):** notebooks (`.ipynb`) under `examples/` are **snippet candidates**, one entry per notebook. Supporting files (`utils.py`, `dummy_sql.json`) are part of the snippet's `depends_on`, not separate entries. The indexer extracts code cells + leading markdown as the snippet's `summary` (already noted in `indexer-notes.md`). Close open question #2 in v0.0.4 (or as a clarification to v0.0.3 changelog).
- **C8 (`builds_on`) has crossed 2 motivating cases (codeguard-cli, ws3) and now has 3 (adding ws4).** Does it earn promotion? The honest answer per working principle #9: **not yet**, because no prompt in [`evaluation-prompts.md`](evaluation-prompts.md) tests for it. The pattern is real but the *query* isn't. Recommend either: (a) adding a new prompt to the evaluation list ("What projects build on Project CodeGuard / the CoSAI Risk Map?") to *create* the evidence; or (b) keep deferring until a real user prompt motivates. Worth deciding before continuing the walk.

#### Long-form analysis
- *(None — compact format only.)*

---

### 8. cosai-tsc

**Analyzed:** 2026-05-18 · **Commit:** `a4cc1157` · **Walked against:** v0.0.4 (first walk with `builds_on` field + P11 prompt).

#### Key findings
- **The TSC repo itself** — Technical Steering Committee minutes, organizational governance documents, and TSC-approved whitepapers that span workstream boundaries.
- **Three substantive published documents at the root:**
  - `security-principles-for-agentic-systems.md` (~4KB) — the canonical "CoSAI Principles for Secure-by-Design Agentic Systems," approved 2025-07-14. **This is the doc ws4 cites.**
  - `intro-agentic-security-principles.md` (~13KB) — explanatory companion piece.
  - `the-future-of-agentic-security.md` (~40KB + PDF) — substantial whitepaper "The Future of Agentic Security: From Chatbots to Autonomous Swarms" (V1.0, 2026-03-16).
- **20 TSC meeting minutes files** under `tsc-meeting-minutes/` (2024-09-27 through 2026-05-12). Plus a `2025/` subdirectory implying historical archival.
- **Five DOT/SVG diagram pairs** under `diagrams/` (research-authorization-attestation, research-control-boundaries, research-edr-oversight, research-privilege-identity, research-privilege-identity-v2). The DOT files are GraphViz source; SVG is the rendered output. Same pattern as ws1's `.excalidraw + .png` pairs — both go in baseline ignore.
- **Whitepaper template + working documents** under `whitepaper_templates/` and `working-documents/`. Plus a `scripts/prompts/` directory.
- **Reverse-`builds_on` target.** ws4 declares `builds_on: [{project: "cosai-tsc", relationship: "cites", uri: "...security-principles-for-agentic-systems.md"}]`. cosai-tsc itself is an *upstream*, not a downstream — its own `builds_on` should be empty or near-empty. This is the **first opportunity to test P11's reverse-traversal mechanic**.

#### Prompt-driven verdict grid (now with P11)
| Prompt | Verdict | Notes |
|---|---|---|
| P1 (LLM provider wrapper) | Miss (legitimate) | No code. |
| P2 (MCP server scaffolding) | Miss (legitimate) | No code. |
| P3 (file-hash skip pattern) | Miss (legitimate) | No code. |
| P4 (versioned-content manager) | Miss (legitimate) | No code. |
| P5 (YAML cross-ref validator) | Miss (legitimate) | No code. |
| P6 (CISO dashboard) | Partial | "Principles for Secure-by-Design Agentic Systems" + "Future of Agentic Security" both frame executive-level concerns. Surface as framing context; secondary to secure-ai-tooling's structured risk-map data. |
| P7 (RAG threat modeling) | Partial | "Future of Agentic Security" covers semantic-layer attack surface, prompt injection at scale, and agent-to-agent threats. Pairs well with ws4 and ws2 for full coverage. |
| P8 (hardening AI-generated code) | Partial | The principles doc touches on "agents can author code" and the future paper expands on it; relevant context but not code-level rules. ws4, project-codeguard primary. |
| P9 (runnables filter) | Hit (correctly excluded) | `primary_kind: "working-group"`, `also: ["whitepaper"]`. Excluded from runnables. |
| P10 (supply-chain position paper) | Miss (legitimate) | Out of scope. ws1 owns this. |
| **P11 (builds_on reverse-traversal)** | **Hit** | cosai-tsc is *upstream* — its own `builds_on` is empty or near-empty. The reverse query "what builds on cosai-tsc?" should surface ws4-secure-design-agentic-systems via its `builds_on: [{project: "cosai-tsc", relationship: "cites", ...}]` declaration. **This is the load-bearing test for the field** — and as a *machine-readable structured traversal*, it works in a way that semantic match alone would not (semantic match would surface ws4 for queries about agentic security, but couldn't distinguish "cites" from "ships related content"). |

**Score:** 2 Hit / 3 Partial / 6 Miss (all legitimate). P11 hits cleanly — the field is doing work.

#### Candidate field evidence
- **C8 `builds_on` (now Adopted):** **P11 validated.** Without `builds_on`, the reverse traversal "what builds on cosai-tsc?" reduces to semantic search across project descriptions — which would surface ws4 for adjacency reasons, but couldn't tell the user that ws4 *cites* cosai-tsc specifically. The structured field carries information that semantic match doesn't: *kind* of dependency. First validation that the promotion wasn't premature.
- **C1 `canonical_source`:** **no new evidence.** cosai-tsc's documents are original. The "Future of Agentic Security" references external frameworks but doesn't snapshot from other COSAI projects. Stays 1/2.
- **C4 `indexing.ignore` / baseline ignore extension:** `.dot` files (GraphViz source for the 5 diagrams) are baseline-ignored like `.excalidraw` and `.drawio`. Already noted in indexer-notes.md.
- **Meeting minutes (20 files) as references:** Tests chunking of a *series* of related short documents. Each minutes file is small (~1-5KB) and chunk-per-heading produces ~2-5 entries per file. ~50-100 reference entries total just from minutes. No retrieval problem expected — meeting minutes are tagged by date and semantic match handles "decisions on X in 2026" queries.

#### Schema changes proposed
- **None.** v0.0.4 held.
- **`builds_on` shape note:** cosai-tsc itself declares an *empty* `builds_on: []` (or omits the field). Confirms that the field handles "upstream-only" projects correctly — absence of declarations is the right answer when a project doesn't build on others.

#### Long-form analysis
- *(None — compact format only.)*

---

### 9. cosai-whitepaper-converter

**Analyzed:** 2026-05-18 · **Commit:** `62b8b748` · **Walked against:** v0.0.4.

#### Key findings
- **A real tool, mixed-stack.** Python CLI (`convert.py`, ~28KB monolithic script) that converts Markdown to PDF via Pandoc + LaTeX + Mermaid, plus assets (logo, LaTeX template, fonts, CoSAI styling). Has both `pyproject.toml` and `package.json`.
- **`pyproject.toml` is tool-config-only** (`[tool.pytest]` + `[tool.coverage]`). No `[project]` table. **Per v0.0.4's tightened nested-manifest rule, this does NOT produce a Python package entry** — `convert.py` is run directly, not installed. Validates F-sat-6 from the secure-ai-tooling walk in real use.
- **`package.json` similarly tool-config-only** — dev dependencies (`@mermaid-js/mermaid-cli`, `puppeteer`) with no `name` field. **No package entry.**
- **The actual installable deliverable: a VS Code devcontainer feature** at `src/whitepaper-converter/` with `devcontainer-feature.json`. Published to ghcr.io as `ghcr.io/cosai-oasis/cosai-whitepaper-converter/whitepaper-converter:1`. **First encounter with this artifact type.**
- **Strongest reverse-`builds_on` target so far.** Multiple workstream whitepapers (ws1's two papers, ws2's two papers, ws4's two papers, cosai-tsc's "Future of Agentic Security") are produced by this converter. Whether each of those repos *declares* `builds_on: [{project: "cosai-whitepaper-converter", relationship: "consumes"}]` is a question for those projects' indexer authors. Most don't currently — they use the converter as a build tool, not a runtime dependency. But the relationship is real.
- **Substantial docs.** Five docs (configuration, customization, installation, maintainer, troubleshooting) under `docs/`. README is also substantial (~8KB). ~20+ reference entries after chunking.

#### Prompt-driven verdict grid
| Prompt | Verdict | Notes |
|---|---|---|
| P1 (LLM provider wrapper) | Miss (legitimate) | Not an LLM tool. |
| P2 (MCP server scaffolding) | Miss (legitimate) | Not an MCP-related tool. |
| P3 (file-hash skip pattern) | Miss (legitimate) | n/a. |
| P4 (versioned-content manager) | Miss (legitimate) | n/a. |
| P5 (YAML cross-ref validator) | Miss (legitimate) | n/a. |
| P6 (CISO dashboard) | Miss (legitimate) | Not a security framework. |
| P7 (RAG threat modeling) | Miss (legitimate) | n/a. |
| P8 (hardening AI-generated code) | Miss (legitimate) | n/a. |
| P9 (runnables filter) | **Hit** | The devcontainer feature IS a runnable installable. With the new ecosystem value (see schema changes below), `primary_kind: "cli"`, `also: ["docs"]`, and the devcontainer-feature package entry, this surfaces correctly. |
| P10 (supply-chain position paper) | Miss (legitimate) | n/a. |
| P11 (builds_on reverse-traversal) | **Hit (mechanic)** | cosai-whitepaper-converter's own `builds_on: []` (it builds on nothing in the workspace). But the **reverse query** "what other projects use this converter?" — *if* downstream projects declared `builds_on: [{project: "cosai-whitepaper-converter", relationship: "consumes"}]` — would surface ws1, ws2, ws4, cosai-tsc. **However**, none of those projects currently declare it because the converter is a *build tool*, not a runtime/published dependency. Two interpretations: (a) build tools shouldn't appear in `builds_on` — keep the field for content/code dependencies only; (b) they should, because workspace discovery wants to know "what produced these PDFs?" Worth flagging for the user; my read is (a) — but the question is real. |

**Score:** 2 Hit / 0 Partial / 9 Miss (all legitimate). Surface only ever hits P9 / P11 — narrow but coherent.

#### Candidate field evidence
- **C1 `canonical_source`:** **no new evidence.** No content snapshots from other projects.
- **C8 `builds_on`:** Second clean validation of the *empty* `builds_on` case for upstream-only projects. Plus: surfaces a **design question** — should build-tool dependencies count? Tentative answer: no, the field is for content/code/framework dependencies; build tools are infrastructure, not workspace-discovery-relevant. Document this as `builds_on` authoring guidance.
- **No other candidates motivated.**

#### Schema changes proposed
- **One change motivated:** add a **`devcontainer-feature`** value to the `ecosystem` enum. This is a real installable artifact category — published to ghcr.io as a feature, with a declared install mechanism (`devcontainer.json`), and used by downstream projects. It's structurally analogous to `claude-plugin` and `mcp-server` — a niche-but-real ecosystem.

  **Proposed for v0.0.5** (or batched with another walk's findings):
  - Add `devcontainer-feature` to the `ecosystem` enum.
  - Install hint format: `"Add to devcontainer.json features: ghcr.io/.../feature-id:version"`.
  - Matches the structural test for nested-manifest detection: `devcontainer-feature.json` becomes a recognized manifest file alongside `pyproject.toml`, `package.json`, etc.

- **`builds_on` authoring clarification:** the field is for content/code/framework dependencies (a project *implements*, *cites*, *consumes content from*, or *was donated from* another). Build-tool relationships (e.g. "we run our docs through this converter") don't qualify. Without this clarification, all four workstreams plus cosai-tsc would arguably need `builds_on: [{project: "cosai-whitepaper-converter", relationship: "consumes"}]` — bloating the field and weakening its discriminating power. **Recommend adding as a doc clarification in v0.0.5.**

#### Long-form analysis
- *(None — compact format only.)*

---

### 10. oasis-open-project

**Analyzed:** 2026-05-18 · **Commit:** `2ac02536` · **Walked against:** v0.0.4.

#### Key findings
- **The umbrella governance repo.** Contains the CoSAI project's charter, governance, onboarding, contribution policies, standing rules, workstream descriptions, AI-usage guidelines, sponsors list, and meeting minutes for three committees (PGB, ESC, PSC). No whitepapers, no code, no datasets — it's the "what is CoSAI" repo.
- **15 governance docs at root.** `CHARTER.md`, `GOVERNANCE.md`, `WORKSTREAMS.md`, `ONBOARDING.md`, `CONTRIBUTING.md`, `STANDING-RULES.md`, `TSC-WS-GOVERNANCE.md`, `MARKETING-COMMITTEE-GUIDELINES.md`, `PROJECT-GOVERNING-BOARD.md`, `PUBLIC-SECTOR-COMMITTEE-GOVERNANCE.md`, `TECHNICAL-STEERING-COMMITTEE.md`, `SPONSORS.md`, `AI-USAGE-GUIDELINES.md`, `IPR-STATEMENT.md`, `CODE-OF-CONDUCT.md`.
- **~49 meeting minutes** across three directories (30 PGB + 14 ESC + 5 PSC). Each is short (1-3KB typically) but structured similarly.
- **A trivial `docs/` directory** — `_config.yml`, an `index.md`, the logo — this is a GitHub Pages config, not a docs site.
- **The strongest reverse-`builds_on` target in the workspace.** *Every* CoSAI workstream README points back to `oasis-open-project` for governance docs. Plus codeguard-cli, project-codeguard, secure-ai-tooling, cosai-tsc all reference it. **Eight different projects link to it.**
- **`primary_kind: "working-group"`** with `also: []`. Pure governance — no whitepaper, no library, no dataset, no ruleset.

#### Prompt-driven verdict grid
| Prompt | Verdict | Notes |
|---|---|---|
| P1 (LLM provider wrapper) | Miss (legitimate) | No code. |
| P2 (MCP server scaffolding) | Miss (legitimate) | No code. |
| P3 (file-hash skip pattern) | Miss (legitimate) | No code. |
| P4 (versioned-content manager) | Miss (legitimate) | No code. |
| P5 (YAML cross-ref validator) | Miss (legitimate) | No YAML data. |
| P6 (CISO dashboard) | Miss (legitimate) | Governance, not security taxonomy. |
| P7 (RAG threat modeling) | Miss (legitimate) | Out of scope. |
| P8 (hardening AI-generated code) | Partial | `AI-USAGE-GUIDELINES.md` is exactly about AI-assisted contributions to CoSAI — surfaces for queries about AI-generated content policy, but is governance, not technical hardening. project-codeguard remains primary. |
| P9 (runnables filter) | Hit (correctly excluded) | `primary_kind: "working-group"`, no runnables. |
| P10 (supply-chain position paper) | Miss (legitimate) | Charter mentions ws1 but doesn't contain technical content. |
| P11 (builds_on reverse-traversal) | **Hit (strong)** | This is the prompt's *strongest possible test* — oasis-open-project is the most-pointed-at upstream in the workspace. Eight downstream projects (project-codeguard, codeguard-cli, secure-ai-tooling, ws1, ws2, ws3, ws4, cosai-tsc) point at it for governance via `builds_on` (relationship: `cites` or, more accurately, a *governance* relationship). **Second clean validation of P11**: cosai-tsc validated the upstream-only mechanic; oasis-open-project stress-tests it with many simultaneous incoming relationships. |

**Score:** 1 Hit / 1 Partial / 8 Miss (all legitimate). Plus the P11 reverse-traversal hit, which is structurally significant.

#### Candidate field evidence
- **C1 `canonical_source`:** **no new evidence.** All content is original governance. Stays 1/2 — the rule-snapshot pattern remains unique to codeguard-cli.
- **C8 `builds_on`:** **Strongest validation yet.** With 8 downstream projects pointing at oasis-open-project, the field's reverse-traversal capability is doing real work. A query *"what governs the CoSAI workstreams?"* should return oasis-open-project from `builds_on` traversal, not from semantic match alone (semantic match on "governance" would surface it, but the *structured* relationship makes the connection unambiguous).
- **The `relationship` enum is stretched here.** Each workstream's relationship to oasis-open-project is *governance* — they operate under its rules. None of the existing enum values (`extends | implements | consumes | cites | donated_from`) perfectly fit. The closest is `cites`, but it under-describes a *governance* relationship. **This is a real shape-level finding** — see below.
- **Other candidates:** no new evidence across C3-C7.

#### Schema changes proposed
- **Possible new `relationship` value: `governed_by`.** Every CoSAI workstream is *governed by* oasis-open-project — that's a stronger and more specific relationship than "cites." A workstream isn't merely citing the governance doc; it operates under it. `consumes` is also wrong (the workstream doesn't ingest governance as data). `governed_by` would be the honest answer.

  **Evidence count:** 8 simultaneous cases in this single walk (every workstream + every tool project points at oasis-open-project). Strongest evidence-density for any enum addition we've seen.

  **Sub-question:** is `governed_by` a v0.0.5 inclusion or is it scope creep? The case is strong (8 cases), but the relationship is *workspace-meta* rather than technical. Every project in *any* workspace built on a governance umbrella has the same structure. Recommend **adding to v0.0.5** alongside `devcontainer-feature` — both are real, both have strong evidence.

- **No schema field changes beyond enum extensions.** Manifest field for `builds_on` already handles the data shape.

#### Long-form analysis
- *(None — compact format only.)*
