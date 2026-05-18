# ws2-defenders — index expectations

## Manifest expectations

| Field | Expected value |
|---|---|
| `schema_version` | `"0.1.0"` |
| `project` | `"ws2-defenders"` |
| `path` | `"ws2-defenders"` |
| `description` | MUST_CONTAIN: `["CoSAI Workstream 2", "defenders", "AI telemetry", "AITF", "incident response", "OpenTelemetry"]` |
| `languages` | `["python", "go", "typescript"]` (derived union from the three SDK package entries) |
| `primary_kind` | `"working-group"` |
| `also` | superset of `["whitepaper", "library", "dataset"]` |
| `license` | `"CC-BY-4.0 AND Apache-2.0"` (dual license declared in README) |
| `status` | `"active"` |
| `tags` | superset of `["cosai", "defenders", "telemetry", "incident-response", "frameworks", "opentelemetry", "ocsf"]` |
| `repo_url` | `"https://github.com/cosai-oasis/ws2-defenders"` |
| `default_branch` | `"main"` |
| `builds_on` | likely `[{"project": "oasis-open-project", "relationship": "governed_by", ...}]`; possibly `cites` of NIST/MITRE/OWASP frameworks but these are NOT COSAI projects so don't qualify |
| `counts.packages` | exactly `3` (Python, Go, TypeScript SDKs) |
| `counts.snippets` | `12–20` (the `telemetry/examples/` directory) |
| `counts.references` | `80–120` |

## Packages — expected entries

| `id` pattern | `name` | `language` | `ecosystem` | `path` |
|---|---|---|---|---|
| `pkg:ws2-defenders/aitf-python` | `aitf` or similar | `python` | `source` (no PyPI publish) | `telemetry/sdk/python` |
| `pkg:ws2-defenders/aitf-go` | `aitf` or similar | `go` | `go` (`go.mod` always qualifies) | `telemetry/sdk/go` |
| `pkg:ws2-defenders/aitf-typescript` | `aitf` or similar | `typescript` | `npm` (if `package.json` declares a `name`) or `source` | `telemetry/sdk/typescript` |

**Critical test of granularity rule:** three sibling SDKs in different languages each get their own entry. A query `search(kind="packages", filters={language: "go"})` returns only the Go SDK.

Each package's `summary` MUST_CONTAIN: `["AITF", "AI Telemetry Framework", "OpenTelemetry", "OCSF"]` plus the language-specific framing.

## Snippets — expected entries

`telemetry/examples/` contains 16+ Python files. Per the snippet selection heuristic ("files under `examples/`"), each becomes a snippet entry.

| `id` pattern | `path` | `language` |
|---|---|---|
| `snip:ws2-defenders/basic-llm-tracing` | `telemetry/examples/basic_llm_tracing.py` | `python` |
| `snip:ws2-defenders/agent-tracing` | `telemetry/examples/agent_tracing.py` | `python` |
| `snip:ws2-defenders/mcp-tracing` | `telemetry/examples/mcp_tracing.py` | `python` |
| `snip:ws2-defenders/rag-pipeline-tracing` | `telemetry/examples/rag_pipeline_tracing.py` | `python` |
| `snip:ws2-defenders/ai-bom-generation` | `telemetry/examples/ai_bom_generation.py` | `python` |
| `snip:ws2-defenders/shadow-ai-discovery-tracing` | `telemetry/examples/shadow_ai_discovery_tracing.py` | `python` |
| `snip:ws2-defenders/agentic-log-tracing` | `telemetry/examples/agentic_log_tracing.py` | `python` |
| `snip:ws2-defenders/dual-pipeline-tracing` | `telemetry/examples/dual_pipeline_tracing.py` | `python` |
| `snip:ws2-defenders/model-ops-tracing` | `telemetry/examples/model_ops_tracing.py` | `python` |
| `snip:ws2-defenders/openrouter-tracing` | `telemetry/examples/openrouter_tracing.py` | `python` |
| `snip:ws2-defenders/skills-tracing` | `telemetry/examples/skills_tracing.py` | `python` |
| `snip:ws2-defenders/vendor-mapping-tracing` | `telemetry/examples/vendor_mapping_tracing.py` | `python` |

Plus 1 notebook snippet:
| `snip:ws2-defenders/aitf-colab-demo` | `telemetry/examples/aitf_colab_demo.ipynb` | `python` |

`attack-detection-demo/`, `detection-rules/`, `siem-forwarding/`, `synthetic-telemetry/` subdirs may produce additional snippets — count depends on their internal structure.

`depends_on` for each snippet MUST include `["opentelemetry", "aitf"]` plus pattern-specific deps.

## References — expected entries

| Form | Count | Source |
|---|---|---|
| `prose` | `~30` | "Preparing Defenders of AI Systems" whitepaper chunked per H2 (14 sections × ~2 chunks each) |
| `prose` | `~30` | "AI Incident Response" framework chunked per H2/H3 (deep TOC) |
| `prose` | `~30–50` | Framework reviews `frameworks/{NIST,MITRE,OWASP,MIT,CISA,OASIS,OCSF}.md` — each ~3-6 sub-sections per framework reviewed |
| `prose` | `~15` | AITF spec `telemetry/spec/overview.md` + semantic-conventions + ocsf-mapping + schema |
| `prose` | `~10` | Telemetry-related docs (`framework_telemetry_requirements.md`, `telemetry_gaps_analysis.md`, `telemetry/docs/`) |
| `prose` | `~10` | Integration READMEs under `telemetry/integrations/` (10 vendor dirs × short README) |
| `mixed` | `0–5` | Possibly `whitepaper-template.md` or draft documents |

**PDFs (`preparing-defenders-of-ai-systems.pdf`, `incident-response/AI-Incident-Response.pdf`):** baseline ignored (markdown-over-PDF rule).

**Excel file (`telemetry/spec/AICMv1.0.3-generated_at_2025_11_10.xlsx`):** baseline ignored.

**Status frontmatter:** ws4's whitepapers had `status: "Approved"` in YAML frontmatter. Check whether ws2's whitepapers also have this — if so, the indexer should lift `tags: ["approved"]` per the indexer-notes rule.

## Prompt evaluation expectations

| Prompt | Expected verdict | Should surface | Should NOT surface |
|---|---|---|---|
| P1 | Partial | Vendor integration READMEs (`telemetry/integrations/anthropic/`, etc.) surface as semantically adjacent | should NOT outrank codeguard-cli's `llm.py` |
| P2 | Partial | `snip:ws2-defenders/mcp-tracing` + AITF MCP-namespace spec chunks | should NOT outrank project-codeguard's `codeguard-mcp` for "how to build" |
| P3 | Miss | nothing | — |
| P4 | Miss | nothing | — |
| P5 | Miss | nothing | — |
| P6 | **Hit (strong)** | Whitepaper chunks on "Growing Attack Surface", "AI Risks in Business Processes" + framework reviews + Grafana dashboards | — |
| P7 | **Hit (strong)** | `snip:ws2-defenders/rag-pipeline-tracing` + AITF RAG spec + incident-response framework chunks on Model/User-Interaction Incidents | — |
| P8 | Partial | Incident-response framework chunks on Pre-Incident Preparation + Detection-and-Analysis | should NOT outrank project-codeguard |
| P9 | **Hit** | `also: ["library", ...]` lets the project surface even though `primary_kind: "working-group"`. **Load-bearing test of `also` array.** | — |
| P10 | **Hit (strong)** | Whitepaper "Secure the supply chain" section + supply-chain framework reviews + `snip:ws2-defenders/ai-bom-generation` | — |
| P11 | Hit if `builds_on: [{governed_by: oasis-open-project}]` declared. Reverse-traversal: ws2 is upstream-of nothing in workspace. | — | — |

## Known unknowns

- **Snippet count from subdirs.** `telemetry/examples/attack-detection-demo/`, `siem-forwarding/`, `synthetic-telemetry/`, `detection-rules/` — these contain files but the indexer's recursion + heuristics may or may not surface them as separate snippets. Range: +0 to +8 entries.
- **Framework review chunking** can vary significantly. NIST.md has 4 frameworks × 6 sub-sections each (~24 chunks just for NIST.md). OWASP.md has 2 sub-frameworks. Counts above are estimates.
- **Whether `telemetry/dashboards/grafana/*.json` produces reference entries.** Probably yes if treated as structured content; possibly no if treated as config (config-only files might be baseline ignored).
- **Whether the AITF Python SDK's `pyproject.toml` declares `[project]`** — if it doesn't (tool-config-only), the Python package entry disappears. Worth checking the actual file.
- **`integrations/__init__.py`** suggests integrations are a sub-package — likely absorbed into the parent Python SDK package entry, not separate entries.
