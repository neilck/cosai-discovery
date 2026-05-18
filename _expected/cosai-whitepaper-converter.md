# cosai-whitepaper-converter — index expectations

## Manifest expectations

| Field | Expected value |
|---|---|
| `schema_version` | `"0.1.0"` |
| `project` | `"cosai-whitepaper-converter"` |
| `path` | `"cosai-whitepaper-converter"` |
| `description` | MUST_CONTAIN: `["CoSAI", "whitepaper", "Markdown to PDF", "Pandoc", "LaTeX", "devcontainer feature"]` |
| `languages` | `["python"]` (the `convert.py` script) |
| `primary_kind` | `"cli"` |
| `also` | `["docs"]` (the 5 markdown guides) |
| `license` | `"Apache-2.0"` (probably; the LICENSE.md doesn't specify) — verify against actual file content |
| `status` | `"active"` |
| `tags` | superset of `["cosai", "whitepaper", "pdf", "markdown", "pandoc", "latex", "devcontainer"]` |
| `repo_url` | `"https://github.com/cosai-oasis/cosai-whitepaper-converter"` |
| `default_branch` | `"main"` |
| `builds_on` | likely `[]` — this is a build tool, doesn't build on other COSAI projects. Possibly `[{governed_by: oasis-open-project}]` if all CoSAI projects declare governance. |
| `counts.packages` | exactly `1` |
| `counts.snippets` | `0–2` (`convert.py` is monolithic, ~28KB — depends on whether docstring heuristic surfaces internal functions) |
| `counts.references` | `15–25` |

## Packages — expected entries

| `id` pattern | `name` | `language` | `ecosystem` | `path` |
|---|---|---|---|---|
| `pkg:cosai-whitepaper-converter/whitepaper-converter` | `whitepaper-converter` | `shell` (or `bash` — install script is shell-based) | `devcontainer-feature` | `src/whitepaper-converter` |

**This is the load-bearing test of v0.1.0's `devcontainer-feature` ecosystem value.**

The `devcontainer-feature.json` at `src/whitepaper-converter/devcontainer-feature.json` should be recognised as a package manifest (per the nested-manifest rule extended in v0.1.0). The entry should have:

- `name`: `whitepaper-converter` (from the JSON `id` field)
- `version`: `0.4.0` (from the JSON `version` field)
- `ecosystem`: `devcontainer-feature`
- `install`: MUST_CONTAIN: `["ghcr.io/cosai-oasis/cosai-whitepaper-converter/whitepaper-converter:1", "devcontainer.json", "features"]`
- `summary`: MUST_CONTAIN: `["devcontainer feature", "CoSAI whitepaper", "Markdown to PDF", "Pandoc", "LaTeX", "Mermaid"]`

### Critical: tool-config-only manifests are NOT packages

Per the tightened nested-manifest rule:
- `pyproject.toml` at root has only `[tool.pytest]` and `[tool.coverage]` → **NOT a package**.
- `package.json` at root has only dev-deps (`@mermaid-js/mermaid-cli`, `puppeteer`) and no `name` field → **NOT a package**.

A bug here (treating either as a package) produces false `packages.jsonl` entries.

## Snippets — expected entries

`convert.py` is ~28KB but monolithic. Snippet count depends entirely on docstring-length heuristics on its internal functions. Realistic range: 0–2 entries.

Possible snippet:
| `snip:cosai-whitepaper-converter/markdown-to-pdf-pipeline` | `convert.py` | `python` | If a substantial function (e.g. the main `convert()` function) has a docstring. |

Tests under `tests/` are excluded by baseline.

`scripts/configure-chromium.sh`, `install-deps.sh`, `test-devcontainer.sh`, `verify-deps.sh` — shell scripts. Probably not snippet candidates (shell doesn't have a strong docstring convention). Could be 0 to 2 entries if the heuristic is generous.

## References — expected entries

| Form | Count | Source |
|---|---|---|
| `prose` | `~12` | README chunked per H2 — substantial sections on Installation Options (3 sub-sections), LaTeX Engine Config, Using as a Git Submodule, Comments and Best Practices, Known Issues, Troubleshooting |
| `prose` | `~5` | 5 docs (`configuration.md`, `customization.md`, `installation.md`, `maintainer.md`, `troubleshooting.md`) chunked per H2 |
| `prose` | `~1` | `src/whitepaper-converter/README.md` (the feature's own README) |
| `mixed` | `0–2` | If any chunk has substantial code-block content |

**Assets (PDFs, SVG, PNG, .tex, .sty, .lua):** baseline ignored.

**`converter_config.json.example`:** small JSON file (~33 bytes). Probably produces 1 reference entry if surfaced, but borderline.

## Prompt evaluation expectations

| Prompt | Expected verdict | Should surface | Should NOT surface |
|---|---|---|---|
| P1 | Miss | nothing | — |
| P2 | Miss | nothing | — |
| P3 | Miss | nothing | — |
| P4 | Miss | nothing | — |
| P5 | Miss | nothing | — |
| P6 | Miss | nothing | — |
| P7 | Miss | nothing | — |
| P8 | Miss | nothing | — |
| P9 | **Hit** | `primary_kind: "cli"` + devcontainer-feature package entry makes this surface as a runnable. The newly-added `devcontainer-feature` value in the ecosystem enum is the load-bearing test. | — |
| P10 | Miss | nothing | — |
| P11 | **Miss (legitimate)** | The prompt asks about Project CodeGuard. The converter doesn't `builds_on` Project CodeGuard. Clean Miss. *Design finding (build-tool dependencies are NOT `builds_on`) is recorded in candidate evidence, not in this row.* | — |

### Workspace-tooling discovery (P12-style, hypothetical)

A query like *"I'm writing a CoSAI whitepaper and need to render it to PDF. What tooling exists?"* would surface this project strongly. Test by:
- README chunks "CoSAI Markdown to PDF Converter" overview + "Installation Options" + "Using as a Git Submodule"
- The devcontainer-feature package entry's `install` field

If neither hits, the workspace-discovery angle is broken even though the prompt isn't in the evaluation list. Worth verifying once the indexer exists.

## Known unknowns

- **The exact `name` field** the indexer extracts from `devcontainer-feature.json`. The JSON has `"id": "whitepaper-converter"` and `"name": "CoSAI Whitepaper Converter"`. Either could be used as the package's `name` field.
- **Whether `scripts/*.sh` files produce any entries** — shell scripts have no standard docstring; likely 0 entries.
- **Whether `convert.py` produces 0, 1, or 2 snippets** depends heavily on docstring presence in its internal functions. Range is wide.
- **`assets/*.tex`, `assets/*.sty`, `assets/*.lua` (LaTeX template files)** — should be baseline-ignored (treated as styling assets, not content). But the indexer's baseline list doesn't currently mention these extensions. **Recommend adding to baseline ignore in `indexer-notes.md` if the indexer accidentally surfaces them.**
- **Whether `puppeteerConfig.json.orig`** (backup file) is baseline-ignored. The `.orig` suffix isn't in the current ignore list. Likely a one-off; verify it doesn't produce a spurious entry.
