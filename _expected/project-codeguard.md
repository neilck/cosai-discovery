# project-codeguard — index expectations

## Manifest expectations

| Field | Expected value |
|---|---|
| `schema_version` | `"0.1.0"` |
| `project` | `"project-codeguard"` |
| `path` | `"project-codeguard"` |
| `description` | MUST_CONTAIN: `["Project CodeGuard", "AI coding agent", "security", "skills", "rules"]` |
| `languages` | `["python"]` (markdown is content, not implementation) |
| `primary_kind` | `"ruleset"` |
| `also` | superset of `["library", "cli", "service", "claude-plugin", "docs"]` (order-insensitive) |
| `license` | `"CC-BY-4.0"` |
| `status` | `"active"` |
| `tags` | superset of `["cosai", "security", "rules", "skills"]` |
| `repo_url` | `"https://github.com/cosai-oasis/project-codeguard"` |
| `default_branch` | `"main"` |
| `builds_on` | `[]` (canonical upstream; nothing else points at it from this project's side) |
| `counts.packages` | exactly `2` |
| `counts.snippets` | `5–10` (per-format converter modules) |
| `counts.references` | `110–140` (110 rule files + ~5 skill/agent files + README chunks + docs chunks) |

## Packages — expected entries

| `id` pattern | `name` | `language` | `ecosystem` | `version` | Notes |
|---|---|---|---|---|---|
| `pkg:project-codeguard/project-codeguard` (or similar) | `project-codeguard` | `python` | `source` | `1.3.1` | Top-level converter tool. NOT on PyPI. |
| `pkg:project-codeguard/codeguard-mcp` | `codeguard-mcp` | `python` | `mcp-server` | `0.1.0` | The MCP server sub-package. **Critical that nested-manifest rule picks this up.** |

Each package's `summary` MUST_CONTAIN:
- top-level: `["unified", "convert", "AI coding agent", "rules"]`
- codeguard-mcp: `["MCP server", "CodeGuard", "rules", "tools", "streamable HTTP"]`

Each package's `install` field embedded — top-level should reference `uv` or `pip`; codeguard-mcp should reference `fastmcp` or `mcpServers` config.

## Snippets — expected entries

`5–10` entries, primarily from `src/formats/`. Each converter module (`claude.py`, `cursor.py`, `copilot.py`, `codex.py`, `windsurf.py`, `agentskills.py`, `antigravity.py`, `hermes.py`, `openclaw.py`, `opencode.py`) is a snippet candidate via the "function/class with substantial docstring" heuristic, NOT via `examples/` (none exists).

| `id` pattern | `language` | Expected match |
|---|---|---|
| `snip:project-codeguard/*-converter` (per format) | `python` | One snippet per agent-specific format converter. |

Summaries MUST_CONTAIN: `["convert", "unified rule", "<target format>"]` where target format is the specific agent (Claude, Cursor, etc.).

**Possible miss:** if the indexer's docstring-length heuristic doesn't trigger on these (they may have short or no docstrings), snippet count drops to 0–2.

## References — expected entries

| Form | Count | Source |
|---|---|---|
| `structured` | `~110` | One per rule file in `sources/rules/core/` (24) + `sources/rules/owasp/` (~86). |
| `structured` | `~5` | Skill bundles (`sources/skills/security-review/`, `sources/skills/memory-safe-migration/`) + agent definitions (`sources/agents/codeguard-reviewer/`) + packaged skill (`skills/software-security/SKILL.md`). |
| `prose` | `~10` | README chunks (chunk-per-heading). |
| `prose` | `~10–20` | `docs/*.md` chunks (`getting-started.md`, `faq.md`, `claude-code-skill-plugin.md`, etc.). |
| `mixed` | `0–2` | If any docs page has heavy code/config embedded. |

### Each rule reference entry

| Field | Expected |
|---|---|
| `id` pattern | `ref:project-codeguard/rules/<rule-slug>` or `ref:project-codeguard/sources/rules/<core\|owasp>/<rule-slug>` |
| `form` | `"structured"` |
| `structure_description` | MUST_CONTAIN: `["Project CodeGuard unified rule", "frontmatter", "languages", "alwaysApply"]` |
| `summary` | MUST_CONTAIN: the rule's `description` field from frontmatter, paraphrased. |
| `tags` | MUST include rule's language list from frontmatter + the rule's category (`core` or `owasp`). |

### Each skill reference entry

| Field | Expected |
|---|---|
| `id` pattern | `ref:project-codeguard/skills/<skill-slug>` |
| `form` | `"structured"` |
| `structure_description` | MUST_CONTAIN: `["claude-code skill", "frontmatter"]` |

## Prompt evaluation expectations

| Prompt | Expected verdict | Should surface | Should NOT surface |
|---|---|---|---|
| P1 | Miss | nothing | — |
| P2 | Hit | `pkg:project-codeguard/codeguard-mcp` package entry; possibly README chunk about MCP server | LLM-wrapper-related snippets |
| P3 | Miss | nothing | — |
| P4 | Partial | possibly `convert_to_ide_formats.py`-related snippet if it surfaces; weakly | should NOT outrank codeguard-cli's `updater.py` |
| P5 | Miss | nothing | — |
| P6 | Partial | rule entries tagged with broad concepts (auth, crypto, supply-chain) | should NOT outrank secure-ai-tooling's risk-map for "high-level risks" |
| P7 | Hit | `ref:project-codeguard/rules/.../codeguard-0-input-validation-injection`, `ref:project-codeguard/rules/.../codeguard-0-mcp-security` | unrelated rules (e.g. crypto-specific ones) should rank lower |
| P8 | Hit | rule corpus broadly, `ref:project-codeguard/skills/security-review`, `ref:project-codeguard/agents/codeguard-reviewer` | — |
| P9 | Hit | manifest with `also: [..., "library", "cli", "service", "claude-plugin"]` makes this surface via `list_projects` | — |
| P10 | Hit | `ref:project-codeguard/rules/.../codeguard-0-supply-chain-security`, related rules | unrelated rules |
| P11 | Hit | reverse traversal from downstream projects (codeguard-cli `consumes`, ws3 `donated_from`, ws4 `cites`) should return this project as the upstream | — |

## Known unknowns

- **Exact snippet count** depends on docstring-length heuristic threshold. Could be 0 if format-converter docstrings are sparse.
- **MkDocs site chunking** — whether `docs/index.md` overlaps too heavily with README is something only retrieval testing reveals.
- **Whether `.claude-plugin/marketplace.json` produces its own package entry**, or just supports the existing `claude-plugin` ecosystem value on another entry. Likely the latter, but unconfirmed.
- **PDF skip** — there are no `.pdf` files in this project, so the markdown-over-PDF rule isn't exercised here.
