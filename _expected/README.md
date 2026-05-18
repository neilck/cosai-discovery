# Index Output Tests

Ground-truth expectations for what the indexer should produce for each project in the workspace. Used to diff actual indexer output against anticipated values once the indexer exists.

**These files describe what we expect, not what currently is.** No indexer has run yet; these expectations come from the walkthrough analyses captured in `_docs/project-walkthrough-log.md` and `_docs/archive/`.

## One file per walked project

Each file in this directory covers one project. The file name matches the project slug.

### Why split by project

Per-project files let us:
- Update one project's expectations independently when its repo evolves.
- Run focused diffs (e.g. "did the indexer get codeguard-cli right after we changed snippet heuristics?").
- Add new projects without touching existing files.

## File structure

Each project test file follows the same template:

```
# <project-slug> — index expectations

## Manifest expectations
  (Concrete values for filterable fields; loose expectation for embed/store fields.)

## Packages — expected entries
  (Filterable values per entry; ranges for count.)

## Snippets — expected entries
  (Filterable values per entry; ranges for count.)

## References — expected entries
  (Counts by form, expected tag coverage, expected structured/prose split.)

## Prompt evaluation expectations
  (For each of the 11 prompts: expected verdict, what entries should surface, what should NOT match.)

## Known unknowns
  (Things we can't predict without seeing the indexer run.)
```

## What we're optimistic about getting right

**Filter values.** These are the highest-confidence predictions:

- Manifest `primary_kind`, `also`, `languages`, `status`, `license`, `builds_on.project`, `builds_on.relationship`.
- Per-entry `kind`, `language`, `ecosystem`, `form`.
- Counts within a reasonable range (e.g. references between N and 2N).

When the indexer is wrong about a filter value, it's almost always a bug or a missing heuristic. These are the diffs worth investigating first.

## What we're less optimistic about

**Embed-side text.** Summaries are LLM-generated and will vary across runs. Tests don't pin exact wording — they pin the *concepts that must appear* (e.g. "the summary for the codeguard-mcp package must contain or paraphrase 'MCP server exposing CodeGuard rules as tools'").

**Exact entry counts.** Chunking rules produce ranges, not exact counts. A README with 12 H2s might chunk to 12 or 11 if one section collapses below the 200-char minimum. We bound counts; we don't pin them.

**Snippet selection.** Our heuristics flag candidates but don't guarantee exact extraction. The indexer might surface 3 or 5 snippets where we predict ~4.

**IDs.** We give example IDs but the indexer's slug generation may differ in minor ways (kebab vs. snake, abbreviations). Tests check ID *patterns* (`pkg:<project>/...`), not literal values.

## How to use these tests

Once the indexer exists:

1. Run `build_index` on a project.
2. Compare the resulting `.cosai-index/*` files to the corresponding test file.
3. Diffs in **filter-side fields** are bugs or schema misunderstandings — fix or update the spec.
4. Diffs in **embed-side text** are usually fine — sanity check the concepts appear, then move on.
5. Diffs in **counts** are bugs if outside the stated range, expected variance if inside.

Project files are markdown rather than JSON because they're meant to be human-read and human-maintained, not machine-parsed. A future iteration may add a structured `expected.json` alongside each `.md` for automated diffing.

## Test files

| Project | Status |
|---|---|
| project-codeguard | [project-codeguard.md](project-codeguard.md) |
| codeguard-cli | [codeguard-cli.md](codeguard-cli.md) |
| secure-ai-tooling | [secure-ai-tooling.md](secure-ai-tooling.md) |
| ws2-defenders | [ws2-defenders.md](ws2-defenders.md) |
| ws1-supply-chain | [ws1-supply-chain.md](ws1-supply-chain.md) |
| ws3-ai-risk-governance | [ws3-ai-risk-governance.md](ws3-ai-risk-governance.md) |
| ws4-secure-design-agentic-systems | [ws4-secure-design-agentic-systems.md](ws4-secure-design-agentic-systems.md) |
| cosai-tsc | [cosai-tsc.md](cosai-tsc.md) |
| cosai-whitepaper-converter | [cosai-whitepaper-converter.md](cosai-whitepaper-converter.md) |
| oasis-open-project | [oasis-open-project.md](oasis-open-project.md) |
| cosai-discovery (self) | _not yet walked_ |

## Notation

- `~N` — expected approximately N, with reasonable variance.
- `N–M` — count must fall in this range.
- `MUST_CONTAIN: ["term1", "term2"]` — embed-side text must contain or paraphrase these concepts.
- `MUST_MATCH: pattern` — value must match a regex or shape.
- `Expected entries — manifest fields` — focus on the filter values.

Spec reference: [`../_docs/index-file-format-0.1.0.md`](../_docs/index-file-format-0.1.0.md).
Prompt reference: [`../_docs/evaluation-prompts.md`](../_docs/evaluation-prompts.md).
