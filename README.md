# COSAI Discovery

Makes a workspace of related projects discoverable to AI coding agents.

Each project commits an **index** — a structured, embeddable description of what it contains — to its own repository (or to a sidecar location). An MCP server reads these indexes across the workspace, embeds them, and answers queries from agents working in any one project about what exists in the others.

This repo contains:

- **`cdx-index`** — the CLI indexer (in development). Scans a project and produces its `.cosai-index/` files.
- **The MCP server** (planned). Reads the indexes and serves queries to AI agents.

The system serves four agent goals:

1. Decide whether to write new code or import an existing package.
2. Decide whether to copy an existing pattern instead of writing new code.
3. Load reference material into planning-mode context.
4. Answer user questions about other projects in the workspace.

## Status

Pre-alpha. Schema and tool-surface specs are stable; the CLI indexer is in Phase 1 of implementation. See [`_docs/indexer-build-plan.md`](_docs/indexer-build-plan.md) for the build order.

## Repository layout

```
cosai-discovery/
  src/cdx_indexer/         CLI indexer (Python package)
  tests/                   pytest tests for cdx_indexer
  _docs/                   schema specs, planning docs, process log
  _expected/               per-project indexer-output expectations (eyeball reference)
  _scripts/                one-off dev utilities
```

## Installation

Once the CLI exists:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

Optional extras:

```bash
pip install -e ".[llm]"      # Phase 5: LLM-generated summaries (Anthropic)
pip install -e ".[embed]"    # Phase 6: Embedding + vector store (Voyage, sqlite-vec)
pip install -e ".[dev]"      # pytest, ruff
pip install -e ".[all]"      # everything
```

## Key documents

| Document | Purpose |
|---|---|
| [`_docs/index-file-format-0.1.0.md`](_docs/index-file-format-0.1.0.md) | The index file format spec. Source of truth for what the indexer produces. |
| [`_docs/mcp-tool-surface-0.0.2.md`](_docs/mcp-tool-surface-0.0.2.md) | The MCP server's tool surface. What agents query. |
| [`_docs/indexer-build-plan.md`](_docs/indexer-build-plan.md) | Implementation plan for the CLI indexer. |
| [`_docs/indexer-notes.md`](_docs/indexer-notes.md) | Implementation hints accumulated during workspace walks. |
| [`_docs/evaluation-prompts.md`](_docs/evaluation-prompts.md) | The 11 prompts the system must serve. |
| [`_docs/process.md`](_docs/process.md) | Process log — how the design and walkthroughs happened. |
| [`_docs/candidate-changes.md`](_docs/candidate-changes.md) | Schema changes considered but not adopted (so they're not relitigated). |
| [`_docs/project-walkthrough-log.md`](_docs/project-walkthrough-log.md) | Per-project analysis summaries from the workspace walk. |

## License

Apache-2.0 for source code. See [`LICENSE`](LICENSE).

This repo is part of the [Coalition for Secure AI (CoSAI)](https://www.coalitionforsecureai.org/) ecosystem.
