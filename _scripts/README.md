# _scripts/

Development workflow scripts for the indexer. Use these instead of running raw `cdx-index` commands by hand — they keep `--workspace-root` and other flags consistent.

## Scripts

| Script | Purpose |
|---|---|
| `test-build.sh` | Run `cdx-index build` against one project or all walked projects. Output goes to `<repo>/.cosai-indexes/<project>/`. |
| `clear-checkpoints.sh` | Wipe the LangGraph checkpoint database at `<repo>/.data/checkpoints.db`. Forces fresh LLM calls on next build. |
| `clear-indexes.sh` | Remove generated `.cosai-indexes/` content (all projects, or named projects). Does not touch checkpoints. |

## Typical workflows

**Iterate on a prompt change:**
```bash
./_scripts/clear-checkpoints.sh
./_scripts/test-build.sh codeguard-cli -v
```

**Re-run a single project from scratch:**
```bash
./_scripts/clear-indexes.sh codeguard-cli
./_scripts/clear-checkpoints.sh
./_scripts/test-build.sh codeguard-cli
```

**Re-run all 10 walked projects:**
```bash
./_scripts/clear-indexes.sh
./_scripts/clear-checkpoints.sh
./_scripts/test-build.sh --all
```
