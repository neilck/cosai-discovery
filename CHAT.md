# Terminal Chat Application

An interactive chat app for querying indexed CoSAI projects using **vector search** and Claude.

## Quick Start

```bash
# Build indexes and embeddings first
./_scripts/test-build.sh project-codeguard --embed

# Chat across all indexed projects
cdx-index chat

# Chat with a specific project
cdx-index chat project-codeguard

# Chat with multiple projects
cdx-index chat project-codeguard secure-ai-tooling
```

## How It Works

1. **Static System Prompt** — Claude is given a system prompt with:
   - Overview of all indexed projects (name, description, tags)
   - Instructions on how to use the `search_projects` tool with optional filters

2. **Tool-Use Search** — When Claude needs information, it calls the `search_projects` tool with:
   - `query` — semantic search string
   - `project` (optional) — filter to one project
   - `kind` (optional) — filter to package | snippet | reference | manifest
   - `limit` (optional) — number of results (default 5, max 10)

3. **Semantic Search** — The tool embeds the query using Voyage AI (`voyage-3` model) and finds nearest neighbors in the vector store (SQLite + sqlite-vec).

4. **Metadata Retrieval** — Matching entry metadata (title, summary, path, tags) is fetched directly from the database.

5. **Claude Response** — Claude sees the search results and generates an answer, or calls `search_projects` again with refined parameters.

6. **Multi-turn Conversation** — Conversation history and tool calls are maintained for follow-up questions and search refinement.

## Examples

```
You: What security rules does CodeGuard have?
Assistant: [Claude responds with semantically related entries about rules and security]

You: How does CodeGuard relate to COSAI risk governance?
Assistant: [Claude connects related concepts across projects using vector similarity]

You: Tell me more about the risk framework
Assistant: [Claude digs into related risk entries from ws3-ai-risk-governance]
```

## Architecture

### Components

- **VectorSearcher** (`chat.py:VectorSearcher`) — Opens vector store, handles semantic search, fetches entry metadata from database.
- **_build_system_prompt()** (`chat.py`) — Builds static system prompt with project summaries loaded from manifest entries in the DB.
- **SEARCH_TOOL** (`chat.py`) — Tool definition for Claude to call with query, optional project/kind filters, and limit.
- **chat_loop** (`chat.py:chat_loop`) — Agentic loop that:
  1. Sends user message + conversation history to Claude with tool definition
  2. If Claude calls `search_projects`, executes the search and returns results
  3. If Claude calls the tool again (refinement), executes again
  4. Returns response when `stop_reason != "tool_use"`
  5. Maintains conversation history for multi-turn context
- **CLI Integration** (`cli.py:chat`) — Entry point wired to main CLI.

### Data Flow

```
User Question
    ↓
Claude sees system prompt (project summaries) + tool definition
    ↓
Claude calls search_projects(query, project?, kind?, limit?)
    ↓
Voyage Embedding (query_vector)
    ↓
VectorStore.search(query_vector, k=limit, project=..., kind=...)
    ↓
[SearchHit, SearchHit, ...] from sqlite-vec KNN
    ↓
Load entry metadata from entries table (title, summary, path, tags)
    ↓
Format results as context
    ↓
Claude sees results, may refine and call search_projects again
    ↓
Claude generates final response → Display & save to history
```

### Vector Store Schema

```
entries                         -- metadata + content_hash
├── project, kind, entry_id    -- composite key
├── embedded_text              -- JSON-serialized entry for quick fetch
├── content_hash               -- sha256 of embedded fields
└── embedded_at                -- when this entry was embedded

vec_entries (virtual table)     -- 1024-dim float vectors
├── embedding                  -- float[1024] for voyage-3 model
└── rowid                       -- matched with entry_vec.rowid

entry_vec (bridge table)        -- links entries to vectors
├── project, kind, entry_id
└── rowid                       -- foreign key to vec_entries.rowid
```

## API Keys Required

The chat app requires:
- `ANTHROPIC_API_KEY` — For Claude responses
- `VOYAGE_API_KEY` — For query embeddings and vector model

Both are auto-loaded from `.env` file.

## Setup & Testing

```bash
# 1. Ensure .env has both keys
cat .env | grep API_KEY

# 2. Build and embed a project
./_scripts/test-build.sh project-codeguard --embed

# 3. Run interactively
cdx-index chat project-codeguard

# 4. Pipe test queries
echo "What security patterns are recommended?" | cdx-index chat
```

## Advantages Over Keyword Search

| Aspect | Keyword | Vector Search |
|--------|---------|---------------|
| **Speed** | <5ms | ~500ms (includes Voyage API call) |
| **Semantics** | No | Yes (understands meaning) |
| **Spelling** | Exact match only | Handles synonyms & paraphrasing |
| **Relevance** | Term frequency | Cosine similarity (embedding space) |
| **Scalability** | O(n) per query | O(log n) with sqlite-vec indexing |
| **Use case** | Navigation | Deep understanding |

## Performance Notes

- **First query per session**: ~500ms (Voyage embedding + KNN search)
- **Subsequent queries**: ~500ms (Voyage is not cached locally)
- **Context window**: ~1500 tokens total (system + results + conversation)
- **Voyage cost**: ~$0.00003 per query at $0.02/M tokens

## Limitations & Future Work

**Current:**
- Vector search requires pre-embedded data (from `--embed` flag)
- Limited to 5 results per query
- No structured filtering (project, kind, language)
- Single semantic model (voyage-3)

**Future improvements (in MCP server):**
- Structured queries: `search(query, project="secure-ai-tooling", kind="reference")`
- Result ranking and deduplication
- Query result caching
- Multiple embedding models (voyage-3, voyage-code-3)
- Cross-project semantic relationships
- Fine-tuned embeddings for CoSAI domain

## Troubleshooting

**"Vector store not found"**
```bash
# Build and embed missing projects
./_scripts/test-build.sh your-project --embed
```

**"API key not found"**
```bash
# Ensure .env is in the repo root
echo "VOYAGE_API_KEY=your-key" >> .env
echo "ANTHROPIC_API_KEY=your-key" >> .env
```

**"Search error: No matching entries"**
→ This is normal; the query didn't find semantic matches. Try rephrasing.

**"Voyage API rate limit"**
→ Wait a few seconds; the free tier has rate limits.
