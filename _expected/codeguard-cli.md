# codeguard-cli — index expectations

## Manifest expectations

| Field | Expected value |
|---|---|
| `schema_version` | `"0.1.0"` |
| `project` | `"codeguard-cli"` |
| `path` | `"codeguard-cli"` |
| `description` | MUST_CONTAIN: `["CLI", "Project CodeGuard", "LLM", "check", "security rules"]` |
| `languages` | `["python"]` |
| `primary_kind` | `"cli"` |
| `also` | `[]` (single-purpose tool — though `also: ["library"]` would be defensible if codeguard package is also library-importable) |
| `license` | **field omitted** — no LICENSE file in repo, no `license` in `pyproject.toml` |
| `status` | `"draft"` (README explicitly says "99% AI-written, currently fails its own checks") |
| `tags` | superset of `["cosai", "codeguard", "security", "llm", "code-review"]` |
| `repo_url` | `"https://github.com/neilck/codeguard-cli"` |
| `default_branch` | `"main"` |
| `builds_on` | `[{"project": "project-codeguard", "relationship": "consumes", "uri": "https://github.com/cosai-oasis/project-codeguard"}]` |
| `counts.packages` | exactly `1` |
| `counts.snippets` | `2–4` |
| `counts.references` | `35–55` (12 README sections + 23 bundled rules + example config + tests README) |

## Packages — expected entries

| `id` pattern | `name` | `language` | `ecosystem` | `version` | Notes |
|---|---|---|---|---|---|
| `pkg:codeguard-cli/codeguard-cli` (or `codeguard`) | `codeguard-cli` | `python` | `source` | `1.0.0` | Single Python package. Console script: `codeguard`. |

`install` MUST_CONTAIN: `["pip install", "editable", "venv"]` (per README install instructions).
`summary` MUST_CONTAIN: `["CLI", "Project CodeGuard rules", "LLM", "check", "Anthropic", "OpenAI", "Google"]` (or paraphrases of multi-provider).

## Snippets — expected entries

| `id` pattern | `path` | `language` | Concept |
|---|---|---|---|
| `snip:codeguard-cli/llm-provider-abstraction` | `codeguard/llm.py` | `python` | Multi-provider LLM dispatch. |
| `snip:codeguard-cli/file-hash-skip` | `codeguard/checker.py` or `codeguard/commands/recheck.py` | `python` | SHA256-based skip-unchanged-files pattern. |
| `snip:codeguard-cli/cached-rules-version-manager` | `codeguard/updater.py` | `python` | Fetch versioned rules from GitHub, cache locally, switch active. |

Summaries MUST_CONTAIN concepts:
- llm: `["multi-provider", "Anthropic", "OpenAI", "Google", "abstraction"]`
- file-hash: `["SHA256", "skip", "unchanged"]`
- updater: `["GitHub", "rules version", "cache", "switch"]`

**Possible miss:** if docstring-length heuristic doesn't fire on these files, snippet count drops. Functions in this codebase are mid-size — borderline for the ~200-char threshold.

## References — expected entries

| Form | Count | Source |
|---|---|---|
| `prose` | `~12` | README chunked per H2 — Installation, Configuration, Usage/check, Usage/scan, Usage/recheck, Usage/rules, Output/text, Output/json, Requirements, Development, About, Lack of Warranty. |
| `structured` | `23` | Rule files in `rules/` — byte-identical snapshots of project-codeguard's rules. Each gets a reference entry with `form: "structured"`. |
| `prose` | `1–2` | `.codeguard.yaml.example` (if surfaced), tests/README. |

### The 23 bundled rule entries

| Field | Expected |
|---|---|
| `id` pattern | `ref:codeguard-cli/rules/<rule-slug>` |
| `form` | `"structured"` |
| `structure_description` | MUST_CONTAIN: `["Project CodeGuard unified rule", "frontmatter", "languages"]` — same form as project-codeguard's own rule entries |
| `tags` | should include rule's language list + indicator that this is a bundled snapshot (e.g. `["bundled", "snapshot"]`) — though this is loose; we rejected `canonical_source` field |

**These duplicate project-codeguard's rule entries semantically.** Diff against project-codeguard's index: same rule slugs should appear in both, with very similar summaries. This is expected behaviour — duplicate hits surfaced are model-handleable per R8 rejection.

### The 12 README chunks

Each ~1–3KB. Summary should describe the section's content (e.g. "How to install codeguard-cli using pip and venv").

## Prompt evaluation expectations

| Prompt | Expected verdict | Should surface | Should NOT surface |
|---|---|---|---|
| P1 | **Hit** | `snip:codeguard-cli/llm-provider-abstraction` + package entry. Filter `language: "python", ecosystem: "source"` works correctly. | — |
| P2 | Miss | nothing | — |
| P3 | **Hit** | `snip:codeguard-cli/file-hash-skip` ranked highly. | unrelated snippets |
| P4 | **Hit** | `snip:codeguard-cli/cached-rules-version-manager`. Semantic match on functionality (not keywords). | — |
| P5 | Miss | nothing | — |
| P6 | Miss | nothing | — |
| P7 | Partial | bundled rules surface; duplicate-hit pattern with project-codeguard (model handles by inspection) | — |
| P8 | **Hit** | Package entry + README "About" chunk surface directly. | — |
| P9 | **Hit** | manifest with `primary_kind: "cli"`, `status: "draft"`. User can filter out by status if they want production-ready only. | — |
| P10 | Partial | Bundled `codeguard-0-supply-chain-security` rule surfaces — same duplicate-hit caveat. | — |
| P11 | **Hit (load-bearing)** | `builds_on.project: "project-codeguard"` makes reverse-traversal "what builds on Project CodeGuard?" return this. `relationship: "consumes"` is the discriminating signal. | — |

## Known unknowns

- **Snippet count.** Heavily depends on docstring presence. The three flagged are the *most likely* candidates; could be 0 if heuristics are strict.
- **Whether `codeguard/commands/*` subdirectory** produces additional snippets or is absorbed into the package entry's `entrypoints`/`public_api`. Probably the latter per granularity rule (same language, same ecosystem).
- **Whether `rules/` snapshot tags include any signal** that they're snapshots vs. canonical. We rejected `canonical_source` — the indexer has no way to detect this without cross-project awareness. Likely no special tagging.
- **`results.josn` in `codeguard/`** (sic — note the typo) — probably should be in baseline ignore (looks like a build artifact / test fixture). The indexer should NOT produce a reference entry for it.
