# cosai-tsc — index expectations

## Manifest expectations

| Field | Expected value |
|---|---|
| `schema_version` | `"0.1.0"` |
| `project` | `"cosai-tsc"` |
| `path` | `"cosai-tsc"` |
| `description` | MUST_CONTAIN: `["CoSAI Technical Steering Committee", "TSC", "principles", "agentic systems"]` |
| `languages` | `[]` |
| `primary_kind` | `"working-group"` |
| `also` | `["whitepaper"]` |
| `license` | `"CC-BY-4.0 AND Apache-2.0"` |
| `status` | `"active"` |
| `tags` | superset of `["cosai", "tsc", "governance", "agentic-systems"]` |
| `repo_url` | `"https://github.com/cosai-oasis/cosai-tsc"` |
| `default_branch` | `"main"` |
| `builds_on` | `[{"project": "oasis-open-project", "relationship": "governed_by", ...}]` likely; otherwise `[]` |
| `counts.packages` | exactly `0` |
| `counts.snippets` | exactly `0` |
| `counts.references` | `90–140` |

## Packages — expected entries

**None.**

## Snippets — expected entries

**None.** `scripts/prompts/` may contain markdown prompt content but not code that meets snippet heuristics.

## References — expected entries

| Form | Count | Source |
|---|---|---|
| `prose` | `~5` | "CoSAI Principles for Secure-by-Design Agentic Systems" (~4KB) — small enough to chunk into ~3–5 entries |
| `prose` | `~10` | "Introduction to the CoSAI Principles" (~13KB) chunked per H2 |
| `prose` | `~30–40` | "The Future of Agentic Security" (~40KB whitepaper) chunked per H2/H3 |
| `prose` | `~40–60` | 20 TSC meeting minutes (each ~1–3KB → typically 2–3 chunks each) |
| `prose` | `~5` | Top-level governance / process docs (MAINTAINERS, ONBOARDING) |
| `prose` | `~2` | `whitepaper_templates/whitepaper-template.md` + README |
| `prose` | `~1` | `working-documents/workstreams-brief.md` |

**PDFs (`the-future-of-agentic-security.pdf`):** baseline ignored.

**DOT + SVG diagram pairs (5 pairs under `diagrams/`):** both baseline ignored.

### Critical entry: the Principles doc

The `security-principles-for-agentic-systems.md` is **the doc ws4 cites in its `builds_on`**. Test for:
- Reference entries from this file should surface for the P11 reverse-traversal test.
- The Principles doc's chunks should have summaries that semantically match queries about "agentic security principles," "human governance of AI agents," etc.

### Meeting minutes chunking

Each meeting minutes file is small. Chunking should produce 2–3 entries per file, not 1. If the minutes have only a single H2 (or none), they collapse into a single chunk per file.

## Prompt evaluation expectations

| Prompt | Expected verdict | Should surface | Should NOT surface |
|---|---|---|---|
| P1 | Miss | nothing | — |
| P2 | Miss | nothing | — |
| P3 | Miss | nothing | — |
| P4 | Miss | nothing | — |
| P5 | Miss | nothing | — |
| P6 | Partial | "Future of Agentic Security" chunks on executive-level concerns ("semantic mosaic effect," etc.) | should NOT outrank secure-ai-tooling for structured risk taxonomy |
| P7 | Partial | "Future of Agentic Security" covers agent-to-agent attacks, prompt injection at scale | should NOT outrank ws4 or ws2 |
| P8 | Partial | Principles doc + Intro discuss agentic code generation lightly | should NOT outrank project-codeguard |
| P9 | **Hit (correctly excluded)** | `primary_kind: "working-group"`, `also: ["whitepaper"]`. No runnables. | — |
| P10 | Miss | nothing | — |
| P11 | **Hit (load-bearing)** | cosai-tsc is *upstream*. Empty `builds_on` (or only `governed_by: oasis-open-project`). Reverse-traversal from ws4's `builds_on: [{project: "cosai-tsc", relationship: "cites"}]` should return this. **First validation of `builds_on` upstream-only mechanic.** | — |

## Known unknowns

- **Meeting minutes count and chunking** — exact count depends on each file's structure. 20 files at 2–3 chunks each = 40–60. Could be 20 if minutes are mostly single-H2.
- **The `2025/` subdirectory under `tsc-meeting-minutes/`** — likely contains older minutes. Adds an unknown number of entries.
- **`scripts/prompts/`** — folder name suggests prompt templates. Content may or may not produce reference entries. Could be 0 to 5.
- **`AI-USAGE-GUIDELINES.md`** is at the root — actually that's in oasis-open-project, not cosai-tsc. cosai-tsc's policy guidance lives in its `intro-agentic-security-principles.md` and the Principles doc.
- **Whether the indexer correctly identifies the Principles doc as the canonical reference** for ws4's `cites` relationship. The semantic match should be strong because the doc is *small* (~4KB) and ws4 deep-links specifically to its anchor.
