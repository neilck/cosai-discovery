# _scripts/

Development workflow scripts for the indexer. Thin wrappers around the `cdx-index` CLI; all logic lives there.

## Scripts

| Script | Purpose |
|---|---|
| `test-build.sh` | Run `cdx-index build` against one project or all walked projects. Output goes to `<repo>/.cosai-indexes/<project>/`. |
| `test-embed.sh` | Build, embed via Voyage, verify status, then clean up (for end-to-end embed testing). |

For checkpoint/index management, use the CLI directly:

| Command | Purpose |
|---|---|
| `cdx-index reset PROJECT_SLUG` | Delete checkpoints for one project (forces fresh LLM calls on next build). |
| `cdx-index reset --all` | Wipe all checkpoints. |
| `cdx-index purge PROJECT_SLUG` | Delete index files for one project. |
| `cdx-index purge --all` | Delete all index files. |
| `cdx-index drop PROJECT_SLUG` | Delete vectors for one project. |

## Typical workflows

**Iterate on a prompt change:**
```bash
cdx-index reset codeguard-cli
./_scripts/test-build.sh codeguard-cli -v
```

**Re-run a single project from scratch:**
```bash
cdx-index purge codeguard-cli
cdx-index reset codeguard-cli
cdx-index drop codeguard-cli
./_scripts/test-build.sh codeguard-cli
```

**Re-run all 10 walked projects:**
```bash
cdx-index purge --all
cdx-index reset --all
./_scripts/test-build.sh --all
```

**Build and embed all projects:**
```bash
CDX_EMBED=1 ./_scripts/test-build.sh --all
```
