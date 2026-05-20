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

1. **Vector Search** — When you ask a question, the app embeds it using Voyage AI (`voyage-3` model).

2. **Semantic Similarity** — Searches the vector store (SQLite + sqlite-vec) to find the 5 most semantically similar indexed entries.

3. **Context Window** — The matching entries are formatted and passed to Claude as context.

4. **Response** — Claude generates an answer based on the indexed data.

5. **Multi-turn Conversation** — Conversation history is maintained for follow-up questions.

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

- **VectorSearcher** (`chat.py:VectorSearcher`) — Opens vector store, queries embeddings, fetches entry metadata from JSONL files.
- **chat_loop** (`chat.py:chat_loop`) — Interactive loop that:
  1. Embeds user query via Voyage
  2. Searches vector store for nearest neighbors
  3. Formats results as context for Claude
  4. Calls Claude with system prompt + context + conversation history
  5. Displays response and saves to history
- **CLI Integration** (`cli.py:chat`) — Entry point wired to main CLI.

### Data Flow

```
User Question
    ↓
Voyage Embedding (query_vector)
    ↓
VectorStore.search(query_vector, k=5)
    ↓
[SearchHit, SearchHit, SearchHit, ...]  (distances from sqlite-vec KNN)
    ↓
Load entry metadata from JSONL (fallback to entries table)
    ↓
Format as context string
    ↓
Claude API call with system prompt + context + conversation history
    ↓
Response → Display & save to history
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
