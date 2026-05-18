# ws3-ai-risk-governance — index expectations

## Manifest expectations

| Field | Expected value |
|---|---|
| `schema_version` | `"0.1.0"` |
| `project` | `"ws3-ai-risk-governance"` |
| `path` | `"ws3-ai-risk-governance"` |
| `description` | MUST_CONTAIN: `["CoSAI Workstream 3", "AI Security Risk Governance", "risk", "controls", "taxonomy"]` |
| `languages` | `[]` |
| `primary_kind` | `"working-group"` |
| `also` | `[]` (no whitepapers yet; deliverables are planned) |
| `license` | `"CC-BY-4.0 AND Apache-2.0"` |
| `status` | `"draft"` (deliverables are in planning state — *NOT* `active`) |
| `tags` | superset of `["cosai", "ai-risk", "governance", "ai-security"]` |
| `repo_url` | `"https://github.com/cosai-oasis/ws3-ai-risk-governance"` |
| `default_branch` | `"main"` |
| `builds_on` | likely `[{"project": "project-codeguard", "relationship": "donated_from", "uri": "..."}, {"project": "oasis-open-project", "relationship": "governed_by", "uri": "..."}]` |
| `counts.packages` | exactly `0` |
| `counts.snippets` | exactly `0` |
| `counts.references` | `5–10` |

## Packages — expected entries

**None.**

## Snippets — expected entries

**None.**

## References — expected entries

The smallest reference corpus in the workspace.

| Form | Count | Source |
|---|---|---|
| `prose` | `1–3` | README's Description section + Key Areas of Focus |
| `prose` | `~4` | `SIG-Security-AI-Assisted-Code-Development/Scope-and-Deliverables.md` chunked per H2 (MISSION STATEMENT, CORE CHALLENGE, KEY ASSUMPTIONS, DELIVERABLES) |
| `prose` | `~2` | Meeting outlines `meetings/SIG1-outline.md` + `meetings/sig-kickoff.md` |
| `structured` or `prose` | `1` | `rfc-template.md` |

**`status: "draft"` at manifest level is load-bearing here.** A user filtering for "active workstreams" should exclude ws3; a user wanting to see all in-progress work should include it.

## Prompt evaluation expectations

| Prompt | Expected verdict | Should surface | Should NOT surface |
|---|---|---|---|
| P1 | Miss | nothing | — |
| P2 | Miss | nothing | — |
| P3 | Miss | nothing | — |
| P4 | Miss | nothing | — |
| P5 | Miss | nothing | — |
| P6 | Partial | SIG scope-doc chunks naming "CISO / Security Leadership" + describing a control framework — but as *planned* work, not delivered guidance | — |
| P7 | Miss | nothing | — |
| P8 | **Hit** | SIG scope doc surfaces directly — the SIG is literally about "Security of AI-Assisted Code Development" | — |
| P9 | **Hit (correctly excluded)** | `primary_kind: "working-group"`, no installable. | — |
| P10 | Miss | nothing | — |
| P11 | **Hit (load-bearing)** | `builds_on: [{donated_from: project-codeguard}]` makes reverse-traversal "what builds on Project CodeGuard?" return this. Distinct from codeguard-cli's `consumes` relationship — the *type* matters. | — |

## Known unknowns

- **Whether the README's Description+Key-Areas chunks combine into one or split into two reference entries.** Tiny stub sections may collapse per the 200-char minimum.
- **Whether the SIG's `Scope-and-Deliverables.md` is treated as structured or prose.** It has section headings (MISSION STATEMENT, CORE CHALLENGE, DELIVERABLES) but reads as prose. Expected `form: "prose"`; `form: "mixed"` defensible if deliverable bullet lists count as structured.
- **Meeting outlines are short.** `sig-kickoff.md` is ~1KB; if it doesn't have substantial structure it may produce 0 reference entries (collapsing into the workstream's nothing-here baseline).
- **The `2025/` subdirectory under meetings does not exist here**, but if it does for archival, it adds entries.
