# oasis-open-project — index expectations

## Manifest expectations

| Field | Expected value |
|---|---|
| `schema_version` | `"0.1.0"` |
| `project` | `"oasis-open-project"` |
| `path` | `"oasis-open-project"` |
| `description` | MUST_CONTAIN: `["CoSAI", "OASIS Open Project", "governance", "charter", "workstreams"]` |
| `languages` | `[]` (no code) |
| `primary_kind` | `"working-group"` |
| `also` | `[]` |
| `license` | `"CC-BY-4.0 AND Apache-2.0"` |
| `status` | `"active"` |
| `tags` | superset of `["cosai", "oasis", "governance", "charter", "umbrella"]` |
| `repo_url` | `"https://github.com/cosai-oasis/oasis-open-project"` |
| `default_branch` | `"main"` |
| `builds_on` | `[]` (top-of-stack — governs everything else, nothing above it) |
| `counts.packages` | exactly `0` |
| `counts.snippets` | exactly `0` |
| `counts.references` | `60–120` |

## Packages — expected entries

**None.**

## Snippets — expected entries

**None.**

## References — expected entries

| Form | Count | Source |
|---|---|---|
| `prose` | `~3–5` | CHARTER.md chunks (the "Statement of Purpose," "Business Benefits," "Normative Scope," "Milestones and Deliverables," "Relationship to Other Projects" sections) |
| `prose` | `~10–15` | GOVERNANCE.md chunks (substantial doc, ~20KB) |
| `prose` | `~3–4` | WORKSTREAMS.md chunks (per-workstream descriptions) |
| `prose` | `~3–4` | ONBOARDING.md chunks |
| `prose` | `~5–8` | TSC-WS-GOVERNANCE.md chunks (substantial, ~13KB) |
| `prose` | `~3–5` | MARKETING-COMMITTEE-GUIDELINES.md chunks |
| `prose` | `~1–3` | STANDING-RULES.md, AI-USAGE-GUIDELINES.md, IPR-STATEMENT.md, MAINTAINERS, CONTRIBUTING |
| `prose` | `~30` | 30 PGB meeting minutes (each likely 1 chunk — short docs) |
| `prose` | `~14` | 14 ESC meeting minutes |
| `prose` | `~5` | 5 PSC meeting minutes |
| `prose` | `1` | README chunked |

**Logo PNG, GitHub Pages `_config.yml`:** baseline ignored.

### Critical entry: WORKSTREAMS.md

`WORKSTREAMS.md` is the **canonical source** describing each CoSAI workstream. Test for:
- Each workstream-description section (ws1, ws2, ws3, ws4) produces a reference entry.
- The entries should semantically describe what each workstream does and what it's delivered.
- Reverse-traversal: ws1, ws2, ws3, ws4's manifests' `builds_on: [{governed_by: oasis-open-project}]` should make THIS doc surface when querying "what governs ws1?"

## Prompt evaluation expectations

| Prompt | Expected verdict | Should surface | Should NOT surface |
|---|---|---|---|
| P1 | Miss | nothing | — |
| P2 | Miss | nothing | — |
| P3 | Miss | nothing | — |
| P4 | Miss | nothing | — |
| P5 | Miss | nothing | — |
| P6 | Miss | nothing | governance, not security taxonomy |
| P7 | Miss | nothing | — |
| P8 | Partial | `AI-USAGE-GUIDELINES.md` chunks (CoSAI's policy on AI-assisted contributions) | should NOT outrank project-codeguard |
| P9 | **Hit (correctly excluded)** | `primary_kind: "working-group"`, no runnables | — |
| P10 | Miss | charter mentions ws1 but doesn't have technical content | — |
| P11 | **Hit (strongest validation)** | **Eight downstream projects point at this** via `builds_on: [{governed_by: oasis-open-project}]`: project-codeguard, codeguard-cli, secure-ai-tooling, ws1, ws2, ws3, ws4, cosai-tsc. **Highest density of reverse-`builds_on` relationships in the workspace.** The `governed_by` relationship type is the discriminating signal vs. semantic match on "governance." | — |

### P11 validation specifics

For P11 to pass on this project, the indexer must:
1. Have `governed_by` in its `relationship` enum (per v0.1.0).
2. Have ≥3 downstream manifests declaring `builds_on: [{project: "oasis-open-project", relationship: "governed_by"}]`.
3. The MCP server's reverse-traversal must correctly find these.

If only some workstreams declare it (e.g. only ws3 and ws4), the test still passes but the density is lower. **Recommend: confirm ALL CoSAI projects in the workspace declare this governance relationship.**

## Known unknowns

- **Whether each meeting minute file produces 1 or 2 chunks** depends on file structure. Older minutes (2024-09-27, 2024-10-08) may differ from newer ones.
- **Whether the `docs/` GitHub Pages config (`_config.yml` + `cosai-logo.png` + `index.md`) produces any reference entries.** The `index.md` is minimal — probably 0–1 entries.
- **The `2025/` subdirectory under `pgb-meeting-minutes/`** — adds an unknown count.
- **Whether all CoSAI projects' indexers correctly identify and declare the `governed_by` relationship.** Tests across all manifests will reveal this. If they're inconsistent, the `governed_by` field is doing partial work.
- **Whether `LICENSE.md` is baseline-skipped or produces a tiny reference entry.** Per the licensing-from-LICENSE-file rule, the file's *content* is parsed for license detection but doesn't necessarily become a reference entry. Likely no entry.
