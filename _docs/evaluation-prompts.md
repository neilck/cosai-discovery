# Evaluation Prompts

Fixed list of representative user prompts used to evaluate each project during the walk-through. Each prompt is phrased in the **user's voice** — what someone building a COSAI-related project would actually type into Claude Code with the MCP server attached.

The prompts are deliberately specific (CISO dashboard, supply-chain MCP server, threat-modeling CLI, etc.) rather than abstract ("find me a package about X"). Specific prompts surface retrieval failures that abstract ones don't.

**How to use this list:** when walking a project, for each prompt note whether the project *would surface as a useful hit* and *what entries it would contribute*. A project that contributes meaningfully to many prompts validates the schema. A project that should contribute but wouldn't surface, surfaces a real gap.

A prompt is mapped to one of the four original user goals:

- **G1** — write new code vs. import existing
- **G2** — cut-and-paste existing code
- **G3** — load reference material for planning
- **G4** — answer questions about projects

---

## Goal 1 — Write new code vs. import existing

### P1 — Wrapping an LLM provider
> "I'm building a CLI that runs prompts against multiple LLM providers (Anthropic, OpenAI, Google). Is there an existing package in the COSAI workspace that abstracts provider selection so I don't have to write the dispatch myself?"

**Expected hit:** codeguard-cli — `codeguard/llm.py` does exactly this. Should surface as a `pkg` or `snip`.
**Tests:** package-discovery via `summary` + tags. The model needs to know `ecosystem: "source"` (installable from repo, not PyPI) and `language: "python"` so it can match a Python project's needs.

### P2 — MCP server scaffolding
> "I need to build an MCP server that exposes a catalog of security guidance over streamable HTTP. Has anyone in COSAI already built an MCP server I could model on, or even reuse?"

**Expected hit:** project-codeguard's `src/codeguard-mcp/` sub-package. Should surface with `ecosystem: "mcp-server"` (or `source`) — the model needs the install command in the entry.
**Tests:** nested-package detection. v0.0.2's nested-manifest rule must produce this as a separate package entry, not bury it inside the parent.

---

## Goal 2 — Cut-and-paste existing code

### P3 — File-hash skip-unchanged pattern
> "I want to re-run an expensive analysis only on files that have changed since the last run. Has anyone written a file-hash based skip pattern I can copy?"

**Expected hit:** codeguard-cli — `recheck.py` + `checker.py`, SHA256-based skip-unchanged. Should be a snippet entry.
**Tests:** snippet selection heuristics. The snippet must exist and its `summary` must describe the pattern, not just the function name.

### P4 — Cached-version manager for external resources
> "I'm fetching versioned content from a GitHub repo and want a 'rules version' style manager — list available, download, switch active, cache locally. Sample code?"

**Expected hit:** codeguard-cli — `codeguard/updater.py` (the `codeguard rules` command's backing logic).
**Tests:** matches on functionality description in `summary`, not on keywords. The user said "rules" because they read codeguard-cli's docs, but a real query might say "policy versions" or "config snapshots."

### P5 — Validating cross-references in a YAML data model
> "I have a YAML data file where some fields reference IDs in other entries. I need a validator. Are there examples in COSAI?"

**Expected hit:** secure-ai-tooling — `scripts/hooks/validate_riskmap.py`, `validate_control_risk_references.py`. Snippet entries.
**Tests:** the model has to recognize the *pattern* — "validate cross-references in structured data" — across slightly different vocabularies.

---

## Goal 3 — Reference material for planning

### P6 — CISO dashboard against high-level AI risks
> "I want to create a dashboard for a CISO that shows known security exceptions against higher-level risks they understand. What AI risk taxonomies exist in COSAI that I could map exceptions to?"

**Expected hit:** secure-ai-tooling — the CoSAI Risk Map (`risks.yaml`, `controls.yaml`, README, framework-mappings doc). The model needs both the *catalog* and the *framework explanation* to write the integration code.
**Tests:** the retrieval has to surface multiple complementary entries — the data files *and* the doc-site framing. The model then composes them. This is the test of `references.jsonl` doing real planning-mode work.

### P7 — Threat-modeling a new AI feature
> "I'm adding a new RAG feature to our product. Before writing code, I want to load any COSAI guidance on RAG-specific risks (prompt injection via retrieved content, etc.) into my planning context."

**Expected hit:** secure-ai-tooling's relevant risk entries (`riskPromptInjection`, RAG-related risks), plus project-codeguard's `codeguard-0-input-validation-injection.md` rule. Possibly ws2-defenders or ws4-secure-design-agentic-systems too.
**Tests:** cross-project retrieval. The model finds material in *two or three* projects, each contributing a different angle. This is the test that `search` without project-scoping works.

### P8 — Hardening an AI-generated codebase before deploying
> "Our team is shipping a feature that was mostly written by an AI coding agent. Before deploy, what COSAI material covers reviewing AI-generated code for security issues?"

**Expected hit:** project-codeguard (the rules + the `security-review` skill), codeguard-cli (the CLI itself), secure-ai-tooling's controls related to "Code Review" and "AI-Assisted Development."
**Tests:** the model has to bridge "AI-generated code" (informal phrasing) to "AI coding agents" (project-codeguard's phrasing) and to formal control names in secure-ai-tooling. Semantic match is doing real work here.

---

## Goal 4 — Answer questions about projects

### P9 — Which projects ship something runnable?
> "Of the COSAI projects in this workspace, which ones ship actual installable tools or services vs. being documentation-only?"

**Expected hit:** `list_projects` with implicit filter on `primary_kind in [library, cli, service, mcp-server]`. Should return project-codeguard, codeguard-cli, and the MCP-server sub-package — not secure-ai-tooling (which is `dataset`, even though it has scripts).
**Tests:** the manifest-level `primary_kind` + `also` reshape is doing its job. This is the simplest end-to-end test of `list_projects`.

### P10 — What's the COSAI position on supply-chain attacks?
> "I'm writing a position paper on AI supply-chain attacks. What's already published across COSAI projects — risks, controls, rules — that I should cite or build on?"

**Expected hit:** ws1-supply-chain (whichever entries exist), secure-ai-tooling's supply-chain risk and control entries, project-codeguard's `codeguard-0-supply-chain-security.md` rule. Cross-project, multi-form (whitepaper + structured + rule).
**Tests:** the most demanding prompt. Requires cross-project retrieval, mixing forms, and the model integrating four+ sources. Tests whether v0.0.2's `form` field + `structure_description` actually help the model pick what to load when context is tight.

### P11 — Which COSAI projects extend Project CodeGuard?
> "I want to understand the COSAI ecosystem around Project CodeGuard — which workstreams and tools build on it, implement its rules, or were donated from it? I need to know what's already been done before I start a new effort in this space."

**Expected hit:** `list_projects` traversal via `manifest.builds_on` declarations. codeguard-cli (consumes), ws3-ai-risk-governance (donated_from), potentially ws4-secure-design-agentic-systems (cites for adjacent work).
**Tests:** the **`builds_on` field** added in v0.0.4. This prompt was added in Phase 8 alongside the adoption of `builds_on` to validate that the field actually serves a real query, not just shape. Specifically tests:
- Reverse traversal — given an upstream project, find all downstream projects.
- Relationship type — the answer should distinguish "consumes" from "donated_from" from "cites" — not just "related."
- Semantic match fallback — *without* `builds_on`, would semantic search across project descriptions surface these relationships cleanly? If yes, `builds_on` is redundant. If no, the field is justified.

This prompt is **load-bearing for C8's promotion case**. If walks of the remaining projects show that semantic match handles it cleanly, the field's promotion was premature; if semantic match misses or misranks, the field is doing real work. Watch closely in cosai-tsc, cosai-whitepaper-converter, and oasis-open-project walks.

---

## How this list will evolve

- **Add a prompt** when a project walk surfaces a user query the current 10 don't cover.
- **Remove a prompt** when it's redundant with another (e.g. two prompts that test the same retrieval mechanic).
- **Mark a prompt as failing** in a walkthrough if the schema can't serve it. Failing prompts are the **evidence** for promoting deferred candidate fields.
- **The list is small on purpose.** Ten is enough to exercise breadth; more and the walkthrough becomes a benchmarking exercise instead of an evaluation.

---

## Mapping to goals

| Prompt | Goal | Primary mechanic tested |
|---|---|---|
| P1 | G1 | Package-discovery with language + ecosystem filter |
| P2 | G1 | Nested-manifest detection; mcp-server ecosystem |
| P3 | G2 | Snippet-discovery; selection heuristics |
| P4 | G2 | Semantic match on functionality (not keywords) |
| P5 | G2 | Cross-project pattern recognition |
| P6 | G3 | Multi-entry composition (data + framing) |
| P7 | G3 | Cross-project planning context |
| P8 | G3 | Vocabulary bridging across projects |
| P9 | G4 | Manifest filters; `primary_kind` reshape |
| P10 | G4 | Hardest case — cross-project, multi-form, integration |
| P11 | G4 | `builds_on` field — reverse traversal, relationship typing, structured vs. semantic |
