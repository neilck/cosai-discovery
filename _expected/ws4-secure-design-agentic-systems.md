# ws4-secure-design-agentic-systems — index expectations

## Manifest expectations

| Field | Expected value |
|---|---|
| `schema_version` | `"0.1.0"` |
| `project` | `"ws4-secure-design-agentic-systems"` |
| `path` | `"ws4-secure-design-agentic-systems"` |
| `description` | MUST_CONTAIN: `["CoSAI Workstream 4", "secure design", "agentic systems", "MCP", "agentic identity", "IAM"]` |
| `languages` | `["python"]` (from the Python notebooks + `utils.py`) |
| `primary_kind` | `"working-group"` |
| `also` | superset of `["whitepaper"]` |
| `license` | `"CC-BY-4.0 AND Apache-2.0"` |
| `status` | `"active"` |
| `tags` | superset of `["cosai", "agentic-systems", "mcp", "iam", "agent-identity"]` |
| `repo_url` | `"https://github.com/cosai-oasis/ws4-secure-design-agentic-systems"` |
| `default_branch` | `"main"` |
| `builds_on` | `[{"project": "secure-ai-tooling", "relationship": "implements", "uri": "https://github.com/cosai-oasis/secure-ai-tooling/tree/main/risk-map"}, {"project": "cosai-tsc", "relationship": "cites", "uri": "https://github.com/cosai-oasis/cosai-tsc/blob/main/security-principles-for-agentic-systems.md"}, {"project": "oasis-open-project", "relationship": "governed_by", ...}]` |
| `counts.packages` | exactly `0` |
| `counts.snippets` | `5–8` (the 5 notebooks under `practical-guides/examples/` + possibly `utils.py` if it has substantial docstrings) |
| `counts.references` | `60–100` |

## Packages — expected entries

**None.**

## Snippets — expected entries

Notebook snippets are the load-bearing test of v0.0.4's notebook resolution.

| `id` pattern | `path` | `language` | `depends_on` |
|---|---|---|---|
| `snip:ws4-secure-design-agentic-systems/command-obfuscation` | `practical-guides/examples/command_obfuscation/command_obfuscation.ipynb` | `python` | should include `["dummy_sql.json"]` (same-directory fixture) |
| `snip:ws4-secure-design-agentic-systems/direct-guardrails` | `practical-guides/examples/direct_guardrails/direct_guardrails.ipynb` | `python` | — |
| `snip:ws4-secure-design-agentic-systems/detached-defence` | `practical-guides/examples/detached_defence/*` | `python` | — |
| `snip:ws4-secure-design-agentic-systems/function-hijacking` | `practical-guides/examples/function_hijacking/function_hijacking.ipynb` | `python` | should include `["utils.py", "run_1.json"]` |
| `snip:ws4-secure-design-agentic-systems/output-filtering` | `practical-guides/examples/output_filtering/output_filtering.ipynb` | `python` | — |

Summaries MUST_CONTAIN concepts:
- command-obfuscation: `["prompt injection", "command", "guardrail"]`
- direct-guardrails: `["guardrail", "LLM defence"]`
- function-hijacking: `["function", "agent", "hijacking"]`
- output-filtering: `["output", "filter", "data loss"]`

**Critical test:** the indexer must extract code cells + leading markdown for the summary, NOT include cell outputs.

## References — expected entries

| Form | Count | Source |
|---|---|---|
| `prose` | `~25–35` | "Agentic Identity and Access Management" whitepaper (~51KB md), chunked per H2/H3. Deep TOC (sections 0–7). |
| `prose` | `~30–50` | "Model Context Protocol (MCP) Security" whitepaper (~76KB md). Even deeper structure — Threats (MCP-T1 through MCP-T11), Controls (3.2.1–3.2.11), Deployment Patterns. |
| `prose` or `mixed` | `~5–10` | `practical-guides/Input and Data Sanitization and Filtering.md` chunked per principle |
| `prose` or `mixed` | `~5–10` | `practical-guides/mcp-secure-tool-design.md` chunked per section |
| `prose` | `~1–3` | README + `whitepaper-template.md` (template likely produces low-relevance entries) |

**PDFs (`agentic-identity-and-access-control.pdf`, `model-context-protocol-security.pdf`):** baseline ignored.

**Frontmatter `status: Approved`:** the agentic-identity whitepaper has explicit `status: Approved` in frontmatter. The indexer should lift `tags: ["approved"]`. MCP Security paper's approval is in prose ("Approved by the CoSAI Project Governing Board on 8 January 2026") — less reliable to detect.

**SVG (`assets/risk-triangle.svg`):** baseline ignored.

### "Approved" tag lift — critical test

ws4 is the **only project so far** with explicit `status: Approved` frontmatter. The indexer should:
1. Detect the frontmatter `status` field.
2. Add `tags: ["approved"]` to entries derived from that document.

Per the indexer-notes rule. This is the test of that rule.

## Prompt evaluation expectations

| Prompt | Expected verdict | Should surface | Should NOT surface |
|---|---|---|---|
| P1 | Miss | nothing | — |
| P2 | **Hit** | MCP Security whitepaper chunks + `mcp-secure-tool-design.md` chunks. Pairs with project-codeguard's `codeguard-mcp` for "how to build" + "what to consider" | — |
| P3 | Miss | nothing | — |
| P4 | Miss | nothing | — |
| P5 | Miss | nothing | — |
| P6 | Partial | Whitepaper sections on "Capability-impact risk framing" and "Risks and failure modes for agents" | should NOT outrank secure-ai-tooling's structured risk-map |
| P7 | **Hit (strong)** | MCP Security whitepaper covers prompt injection, input/instruction boundary failures, tool poisoning. Practical guide on input sanitization. Notebooks `direct_guardrails` and `output_filtering`. | — |
| P8 | Partial | Agentic IAM "Authorization and delegation" section | should NOT outrank project-codeguard or ws3 |
| P9 | **Hit (correctly excluded)** | `primary_kind: "working-group"`, no `library`/`cli` in `also`. The `.ipynb` notebooks are snippets, not packages. | — |
| P10 | Miss | nothing | — |
| P11 | **Hit (strongest)** | `builds_on` has 3 entries with 3 different relationship types (`implements`, `cites`, `governed_by`). Reverse traversal from queries about secure-ai-tooling, cosai-tsc, or oasis-open-project should all return this. **Most relationship-type diversity** in any single manifest. | — |

## Known unknowns

- **Whether the indexer detects the `detached_defence/` subdir as a notebook example.** I haven't verified its contents — may or may not contain a `.ipynb`.
- **MCP Security whitepaper chunking** — the deep numbered structure (MCP-T1 through MCP-T11) could produce ~22 chunks just for the threats section. Total whitepaper chunks could be 50+ if sub-splitting is aggressive.
- **Frontmatter detection robustness.** The `status: Approved` lift depends on parsing YAML frontmatter. If the indexer's frontmatter parser fails (e.g. on whitepapers without a clean `---` opening), the lift doesn't happen. Verify this works on the agentic-identity paper specifically.
- **The `utils.py` file under `function_hijacking/`** — may or may not produce its own snippet entry depending on whether it has substantial docstrings or just helper code. Probably gets absorbed into the notebook snippet's `depends_on`.
