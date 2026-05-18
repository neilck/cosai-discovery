# ws1-supply-chain — index expectations

## Manifest expectations

| Field | Expected value |
|---|---|
| `schema_version` | `"0.1.0"` |
| `project` | `"ws1-supply-chain"` |
| `path` | `"ws1-supply-chain"` |
| `description` | MUST_CONTAIN: `["CoSAI Workstream 1", "supply chain", "AI", "model signing", "provenance"]` |
| `languages` | `[]` (no implementation code) |
| `primary_kind` | `"whitepaper"` |
| `also` | `["working-group"]` |
| `license` | `"CC-BY-4.0 AND Apache-2.0"` |
| `status` | `"active"` |
| `tags` | superset of `["cosai", "supply-chain", "provenance", "model-signing", "ml"]` |
| `repo_url` | `"https://github.com/cosai-oasis/ws1-supply-chain"` |
| `default_branch` | `"main"` |
| `builds_on` | likely `[{"project": "oasis-open-project", "relationship": "governed_by", ...}]` |
| `counts.packages` | exactly `0` |
| `counts.snippets` | exactly `0` |
| `counts.references` | `40–70` |

## Packages — expected entries

**None.** No code, no manifests of any kind. A clean whitepaper repo.

## Snippets — expected entries

**None.** No code files.

## References — expected entries

| Form | Count | Source |
|---|---|---|
| `prose` | `~25–35` | "Establish Risks and Controls for the AI Supply Chain V1.0" — ~111KB markdown, deeply structured TOC. Chunked per H2/H3 with sub-splitting for sections >1500 tokens. |
| `prose` | `~10–15` | "Signing ML Artifacts" — ~43KB markdown. Chunked similarly. |
| `prose` | `~5–10` | README + ROADMAP chunks |
| `structured` or `prose` | `1` | RFC template at `rfcs/00-rfc-template.md` |
| `prose` | `~3` | Drafts under `contributions/q1-25/` (`draft.md`, `outline.md`, `Release-Notes.md`) — surface but rank low |

**PDFs (`risks-and-controls-for-the-ai-supply-chain-v1.pdf`, `signing-ml-artifacts.pdf`):** baseline ignored.

**Excalidraw + PNG pairs (`assets/drawings/*.excalidraw`, `assets/img/*.png`):** both baseline ignored.

### Whitepaper frontmatter

The two whitepapers have YAML frontmatter:
```yaml
title: "..."
author: "Workstream 1: ..."
date: ...
```
The indexer should:
- Use `title` as the source for the document's overall identity in the first chunk's `title` field.
- Treat `author` as a hint for `tags`.

Neither paper has `status:` frontmatter directly, but the approval line *"Approved by the CoSAI Project Governing Board on..."* appears immediately after — the indexer could optionally lift `tags: ["approved"]` from this prose pattern.

## Prompt evaluation expectations

| Prompt | Expected verdict | Should surface | Should NOT surface |
|---|---|---|---|
| P1 | Miss | nothing | — |
| P2 | Miss | nothing | — |
| P3 | Miss | nothing | — |
| P4 | Miss | nothing | — |
| P5 | Miss | nothing | — |
| P6 | Hit | "Risks and Controls" chunks on AI-specific supply-chain risks; high-level enough for a CISO | — |
| P7 | Partial | "Risks and Controls" covers RAG context enrichment and broader supply-chain risk; less granular than secure-ai-tooling or ws2-defenders | — |
| P8 | Miss | nothing | should NOT outrank project-codeguard |
| P9 | **Hit (correctly excluded)** | `primary_kind: "whitepaper"`, no `library`/`cli` in `also`. | should NOT appear in runnable-filter queries |
| P10 | **Hit (strongest)** | Both whitepapers' chunks are *directly cited material*. This workstream's reason for existing. | — |
| P11 | Hit if `builds_on: [{governed_by: oasis-open-project}]`. ws1 is upstream-of nothing in workspace. | — | — |

## Known unknowns

- **Exact reference count from "Risks and Controls"** — the document is ~111KB and has a deep TOC (section 3.1.1.1+ nesting). Chunking depends on max-chunk-size settings. Could be 25 or 50 depending on sub-split aggressiveness.
- **Whether drafts produce reference entries or are silently skipped.** Per R7 rejection, no per-entry `status` filter exists — drafts go in `references.jsonl` like everything else, just rank low.
- **Whether ROADMAP.md issues links create cross-project signals.** The ROADMAP links to GitHub issues; the indexer doesn't follow URLs, so no entries from issue content.
- **Whether `contributions/q1-25/` is the only drafts folder.** Other folders may exist or be added.
