# secure-ai-tooling — index expectations

## Manifest expectations

| Field | Expected value |
|---|---|
| `schema_version` | `"0.1.0"` |
| `project` | `"secure-ai-tooling"` |
| `path` | `"secure-ai-tooling"` |
| `description` | MUST_CONTAIN: `["CoSAI Risk Map", "risks", "controls", "components", "personas", "YAML", "framework"]` |
| `languages` | `["python"]` (validator scripts; risk-map data is content not implementation) |
| `primary_kind` | `"dataset"` |
| `also` | `["docs", "working-group"]` (order-insensitive) |
| `license` | `"Apache-2.0"` |
| `status` | `"active"` |
| `tags` | superset of `["cosai", "risk-map", "ai-security", "controls", "personas", "framework"]` |
| `repo_url` | `"https://github.com/cosai-oasis/secure-ai-tooling"` |
| `default_branch` | `"main"` |
| `builds_on` | likely `[]` or includes `[{"project": "oasis-open-project", "relationship": "governed_by", ...}]` if the indexer infers governance from CoSAI-workstream framing |
| `counts.packages` | exactly `0` (no installable Python package; `pyproject.toml` is tool-config-only per the tightened nested-manifest rule) |
| `counts.snippets` | `2–4` |
| `counts.references` | `150–250` (depending on whether generated tables are indexed alongside YAML items) |

## Packages — expected entries

**None.** The `pyproject.toml` at root only configures pytest and coverage — no `[project]` table. The tightened nested-manifest rule excludes it. `package.json` only declares dev-dependencies (mermaid-cli, playwright, puppeteer, prettier). Neither qualifies.

This is a **load-bearing test of the tightened nested-manifest rule.** A bug here (treating tool-config-only manifests as packages) would produce false package entries.

## Snippets — expected entries

| `id` pattern | `path` | `language` | Concept |
|---|---|---|---|
| `snip:secure-ai-tooling/yaml-to-markdown` | `scripts/hooks/yaml_to_markdown.py` | `python` | Render structured YAML into full/summary/xref table formats. |
| `snip:secure-ai-tooling/riskmap-validator` | `scripts/hooks/validate_riskmap.py` | `python` | Validate cross-references between entities in a structured framework. |
| `snip:secure-ai-tooling/framework-reference-validator` | `scripts/hooks/validate_framework_references.py` | `python` | Validate references from a local framework into external frameworks (MITRE ATLAS, NIST AI RMF). |

Summaries MUST_CONTAIN:
- yaml-to-markdown: `["YAML", "markdown", "table", "render", "structured"]`
- riskmap-validator: `["cross-reference", "validate", "risk map", "controls", "risks"]`
- framework-reference-validator: `["external frameworks", "validate", "MITRE", "NIST"]`

## References — expected entries

This is the most demanding test of fine-grained YAML decomposition.

| Form | Count | Source |
|---|---|---|
| `structured` | `28` | One per risk in `risk-map/yaml/risks.yaml` |
| `structured` | `35` | One per control in `risk-map/yaml/controls.yaml` |
| `structured` | `26` | One per component in `risk-map/yaml/components.yaml` |
| `structured` | `10` | One per persona in `risk-map/yaml/personas.yaml` |
| `structured` | `~15–25` | Items from other YAML files (`actor-access.yaml`, `frameworks.yaml`, `impact-type.yaml`, `lifecycle-stage.yaml`, `mermaid-styles.yaml`, `self-assessment.yaml`) — counts vary by file structure |
| `prose` | `~80–100` | 19 docs guides × ~5 sections each = `~95` from `risk-map/docs/` |
| `prose` | `~10` | README chunks (top-level + risk-map README) |
| `mixed` | `0–2` | If docs pages have heavy embedded YAML examples |

**Generated tables (`risk-map/tables/*-full.md`, `*-summary.md`, `*-xref-*.md`):** Per R10 rejection, these are NOT skipped. Each `.md` table file gets chunked normally. This means ~12 additional reference entries from tables, mostly duplicating content already in YAML items. Per Phase 6 finding, this doesn't degrade retrieval — the YAML entries rank higher because their summaries are tighter.

**SVG files (`risk-map/svg/*.svg`):** Baseline ignored.

**Static site (`site/`):** Probably baseline ignored if files are under `site/generated/`; hand-authored HTML may or may not produce reference entries. The indexer's HTML handling is an open question — index expectations say "0–5" entries here.

### Each risk reference entry

| Field | Expected |
|---|---|
| `id` pattern | `ref:secure-ai-tooling/risks/<riskId>` (e.g. `ref:secure-ai-tooling/risks/riskDataPoisoning`) |
| `form` | `"structured"` |
| `structure_description` | MUST_CONTAIN: `["CoSAI Risk Map", "risk", "id", "title", "shortDescription", "longDescription"]` (some indication of the YAML schema structure) |
| `summary` | The risk's `shortDescription` field, paraphrased or used directly. MUST_CONTAIN the risk's title. |
| `tags` | MUST include the risk's category if frontmatter has one, plus broad risk terms. |

### Each control reference entry

| Field | Expected |
|---|---|
| `id` pattern | `ref:secure-ai-tooling/controls/<controlId>` |
| `form` | `"structured"` |
| `structure_description` | MUST_CONTAIN: `["CoSAI Risk Map", "control", "applicable components", "personas", "risks addressed"]` |

### Each persona reference entry

| Field | Expected |
|---|---|
| `id` pattern | `ref:secure-ai-tooling/personas/<personaId>` (e.g. `ref:secure-ai-tooling/personas/modelProvider`) |
| `form` | `"structured"` |

## Prompt evaluation expectations

| Prompt | Expected verdict | Should surface | Should NOT surface |
|---|---|---|---|
| P1 | Miss | nothing | — |
| P2 | Miss | nothing | — |
| P3 | Miss | nothing | — |
| P4 | Miss | nothing | — |
| P5 | **Hit** | `snip:secure-ai-tooling/riskmap-validator`, `snip:secure-ai-tooling/framework-reference-validator`. Semantic match on the pattern, not keywords. | — |
| P6 | **Hit (strongest)** | Per-risk entries (`riskDataPoisoning`, `riskModelEvasion`, etc.) + risk-map README chunks (Components/Risks/Controls/Personas framing) + framework-mappings guide. Multi-entry composition. | — |
| P7 | **Hit** | RAG-related risk entries, RAG-related component entries, related controls. Cross-project with project-codeguard's input-validation rules. | — |
| P8 | Partial | Controls covering code-review and AI-assisted development | should NOT outrank project-codeguard for code-level guidance |
| P9 | **Hit (correctly excluded)** | `primary_kind: "dataset"` excludes it from runnable-filter queries. | should NOT appear when filtering for `library`/`cli`/`service` |
| P10 | **Hit** | Supply-chain risk entries from `risks.yaml`, supply-chain control entries, framework-mappings entries. Multi-form retrieval. | — |
| P11 | Possible Hit | If `builds_on: [{governed_by: oasis-open-project}]` is declared. Otherwise empty. | — |

## Known unknowns

- **Exact YAML item counts** depend on hand-counts of items per file; risks.yaml is the only one I directly counted (28). Controls (35), components (26), personas (10) from `grep`. Other YAML files (`actor-access.yaml`, etc.) were not enumerated.
- **Whether the indexer indexes JSON schemas** (`risk-map/schemas/*.schema.json`). Likely produces reference entries with `form: "structured"` describing each schema. Could add 13 entries.
- **Whether `risk-map/docs/contributing/`, `risk-map/docs/design/` subdirs produce additional chunks.** Probably yes.
- **`AICMv1.0.3-generated_at_2025_11_10.xlsx`** in `risk-map/spec/` — Excel file, should be baseline-ignored. The indexer should NOT attempt to extract content.
- **The static site under `site/`** — HTML files may or may not be indexed. If `site/index.html` is included, it'll likely duplicate content already in the risk-map docs. Expectation: 0–5 entries, treat any count in that range as acceptable.
