# Vector Search Architecture

Detailed explanation of how the chat application switched from in-memory keyword search to vector-database search.

## The Change: Before and After

### Before: In-Memory Keyword Search

```python
class IndexSearcher:
    def __init__(self, indexes_dir):
        # Load ALL JSONL files into memory
        for project in projects:
            for jsonl_file in ["packages.jsonl", "snippets.jsonl", "references.jsonl"]:
                for line in file:
                    self.entries.append(json.loads(line))
        # self.entries = [300 entries in memory]
    
    def search(self, query):
        # Linear scan: O(n) per query
        for entry in self.entries:
            score = count_matching_terms(query, entry)
        return sorted_results
```

**Problems:**
- Memory overhead: 300+ entries × JSON size = several MB
- No semantic understanding (just keyword matching)
- Slow with many entries (O(n) per query)
- Can't distinguish between "secure" and "security" even though they're related

### After: Vector Search

```python
class VectorSearcher:
    def __init__(self, db_path):
        # Open SQLite connection to pre-computed vectors
        self.store = VectorStore.open(db_path)
        # No entries in memory; just a DB connection
    
    def search(self, query):
        # Embed query
        query_vector = voyage_client.embed(query)
        
        # KNN search: O(log n) with sqlite-vec
        hits = self.store.search(query_vector, k=5)
        
        # Lazy load metadata for top 5 only
        return [fetch_metadata(hit) for hit in hits]
```

**Advantages:**
- No memory overhead (just DB connection)
- Semantic understanding (embeddings capture meaning)
- Fast KNN via sqlite-vec indexing
- "Secure" and "security" map to nearby vectors

---

## How Vector Search Works: Step-by-Step

### Step 1: Preparation (During Indexing)

When you run `cdx-index build --embed`:

1. **Scan entries** — Read all JSONL files
2. **Select fields to embed** — For each entry, combine fields:
   ```python
   # For packages: summary + install → voyage-code-3
   # For snippets: title + summary → voyage-code-3
   # For references: title + summary + structure_description → voyage-3
   embedded_text = entry["title"] + " " + entry["summary"]
   ```
3. **Call Voyage API** — Batch send text to Voyage for embedding
   ```
   POST https://api.voyageai.com/v1/embeddings
   {
     "input": [text1, text2, ...],
     "model": "voyage-3",
     "input_type": "document"
   }
   ```
4. **Get vectors** — Receive 1024-dim float vectors
5. **Store in SQLite**:
   ```sql
   INSERT INTO entries VALUES (
     project='project-codeguard',
     kind='reference',
     entry_id='ref:README',
     embedded_text='{...json...}',
     content_hash='sha256:...'
   )
   INSERT INTO vec_entries VALUES (embedding=<1024 floats>)
   INSERT INTO entry_vec VALUES (rowid=123)
   ```

**Result:** `.cdx/vectors.db` now contains 300 entries with 1024-dim embeddings.

### Step 2: User Asks a Question

```
User: "What security rules does CodeGuard have?"
```

### Step 3: Embed the Query

```python
def search(self, query: str):
    # Embed user's question
    response = voyageai.Client().embed(
        [query],
        model="voyage-3",
        input_type="query"  # Key: "query" not "document"
    )
    query_vector = response.embeddings[0]  # 1024 floats
```

**Important:** The `input_type="query"` tells Voyage this is a search query (not a document). Voyage optimizes embeddings for this context.

### Step 4: K-Nearest Neighbor Search

```python
# Query vector store for nearest neighbors
hits = self.store.search(query_vector, k=5)

# SQL executed:
# SELECT ev.project, ev.kind, ev.entry_id, distance
# FROM vec_entries v
# JOIN entry_vec ev ON ev.rowid = v.rowid
# WHERE v.embedding MATCH <query_blob>
# AND k = 5
# ORDER BY distance
```

What happens:
1. **sqlite-vec plugin** converts the query vector to binary blob format
2. **Virtual table** `vec_entries` runs KNN algorithm:
   - Computes cosine distance from query to all 1024-dim vectors
   - Returns 5 closest matches (smallest distance)
3. **Join with metadata** through `entry_vec` bridge table

**Result:** 5 `SearchHit` objects:
```python
SearchHit(
    project="project-codeguard",
    kind="reference",
    entry_id="ref:software-security-skill",
    distance=0.25  # Lower = more similar
)
```

### Step 5: Load Entry Metadata

For each top hit, fetch the full entry:

```python
def _get_entry_metadata(self, project, kind, entry_id):
    # Option 1: Fast path - fetch from entries table
    cur = store._conn.execute(
        "SELECT embedded_text FROM entries WHERE ...",
        (project, kind, entry_id)
    )
    metadata = json.loads(row[0])  # embedded_text is JSON
    return metadata

    # Option 2: Fallback - read from JSONL
    # Only if embedded_text not available (shouldn't happen)
```

**Why two approaches?**
- **entries table**: Pre-computed during embedding phase, instant fetch
- **JSONL fallback**: For entries in JSONL but not yet embedded, or if DB is corrupted

### Step 6: Format for Claude

```python
# Convert search results to readable context string
def format_results(self, results):
    output = ""
    for i, result in enumerate(results, 1):
        output += f"[{i}] {result['title']}\n"
        output += f"    Project: {result['project']}\n"
        output += f"    Type: {result['kind']}\n"
        output += f"    Relevance: {1 - result['distance']:.2%}\n"
        output += f"    Summary: {result['summary']}\n"
        output += "\n"
    return output
```

**Example output:**
```
[1] Software Security Skill
    Project: project-codeguard
    Type: reference
    Relevance: 89%
    Summary: Defines 3 always-apply rules and context-triggered rules...

[2] Claude Code Plugin
    Project: project-codeguard
    Type: reference
    Relevance: 87%
    Summary: Integration of 23 CodeGuard security rules as Claude tools...
```

### Step 7: Call Claude with Context

```python
system_prompt = f"""You are a helpful assistant answering about CoSAI.

INDEXED PROJECTS: project-codeguard, secure-ai-tooling

RELEVANT ENTRIES (found via semantic vector search):
{formatted_results}

If the question cannot be answered from these entries, say so."""

response = client.messages.create(
    model="claude-opus-4-7",
    system=system_prompt,
    messages=[
        {"role": "user", "content": query},
        ...previous messages...
    ]
)
```

Claude sees:
- The system prompt (instructions + search results)
- The user's question
- Previous conversation messages
- Can generate a response based on the retrieved context

---

## Key Differences from Keyword Search

### Semantic Understanding

**Keyword Search:**
```python
query = "how to secure code"
# Looks for exact words: "secure", "code"
# Misses: "safety", "hardening", "protection"
```

**Vector Search:**
```python
query = "how to secure code"
# Embeds to high-dimensional vector
# Finds semantically similar vectors:
#   - "securing software" ✓
#   - "cryptographic hardening" ✓
#   - "attack surface reduction" ✓
#   - "authentication mechanisms" ✓
# Because in embedding space, these concepts cluster together
```

### Performance Implications

| Operation | Keyword | Vector |
|-----------|---------|--------|
| Search 300 entries | ~1ms | ~50ms (just KNN) |
| + Voyage API call | N/A | ~400-500ms |
| Memory usage | ~2MB (all entries) | ~10KB (just connection) |
| Requires pre-processing | No | Yes (build --embed) |

### Quality Trade-offs

**Keyword search is good for:**
- Navigation (exact word searches: "manifest", "api key")
- Fast exploration (live results, no API calls)
- Unknown projects (no embeddings needed)

**Vector search is good for:**
- Understanding (semantic queries: "how do I configure security?")
- Discovering relationships (connecting concepts across projects)
- Ambiguous queries (handles synonyms, paraphrasing)

---

## Implementation: VectorSearcher Class

### Opening the Store

```python
class VectorSearcher:
    def __init__(self, db_path, indexes_dir, project_slugs=None):
        # Validate DB exists
        if not db_path.exists():
            raise ClickException("Run 'cdx-index build --embed' first")
        
        # Load API keys
        load_dotenv()
        
        # Open vector store (initializes sqlite-vec)
        self.store = VectorStore.open(db_path)
        
        # Discover projects in DB
        self.project_slugs = project_slugs or self.store.list_projects()
        
        # Initialize Voyage client (auto-reads VOYAGE_API_KEY)
        self.voyage_client = voyageai.Client()
```

### Searching

```python
def search(self, query: str, limit: int = 5) -> list[dict]:
    # 1. Embed query
    response = self.voyage_client.embed(
        [query],
        model="voyage-3",
        input_type="query"
    )
    query_vector = response.embeddings[0]
    
    # 2. Vector KNN search
    hits = self.store.search(query_vector, k=limit * 2)
    
    # 3. Filter by project if specific ones requested
    results = []
    for hit in hits:
        if self.project_slugs and hit.project not in self.project_slugs:
            continue
        
        # 4. Lazy-load metadata for top results
        metadata = self._get_entry_metadata(
            hit.project, hit.kind, hit.entry_id
        )
        if metadata:
            results.append({
                "project": hit.project,
                "kind": hit.kind,
                "entry_id": hit.entry_id,
                "distance": hit.distance,
                **metadata
            })
        
        if len(results) >= limit:
            break
    
    return results
```

### Metadata Loading

```python
def _get_entry_metadata(self, project, kind, entry_id):
    # Try entries table first (fast path)
    cur = self.store._conn.execute(
        "SELECT embedded_text FROM entries WHERE project = ? AND kind = ? AND entry_id = ?",
        (project, kind, entry_id)
    )
    row = cur.fetchone()
    if row:
        try:
            return json.loads(row[0])  # embedded_text is JSON
        except json.JSONDecodeError:
            pass
    
    # Fallback: read from JSONL
    return self._load_from_jsonl(project, kind, entry_id)

def _load_from_jsonl(self, project, kind, entry_id):
    # Map kind to JSONL filename
    kind_to_file = {
        "package": "packages.jsonl",
        "snippet": "snippets.jsonl",
        "reference": "references.jsonl",
    }
    
    file_path = self.indexes_dir / project / kind_to_file[kind]
    if not file_path.exists():
        return None
    
    # Search JSONL for matching entry_id
    with file_path.open() as f:
        for line in f:
            entry = json.loads(line)
            if entry["id"] == entry_id:
                # Extract searchable fields
                return {
                    "id": entry["id"],
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", ""),
                    "path": entry.get("path", ""),
                    "tags": entry.get("tags", []),
                }
    
    return None
```

---

## Configuration & Dependencies

### Required packages
- `voyageai>=0.3` — For embeddings
- `sqlite-vec>=0.1` — For KNN search
- `anthropic>=0.40` — For Claude API

Already in `pyproject.toml` under `embed` optional dependencies.

### API Keys
- `VOYAGE_API_KEY` — For Voyage embeddings (set in `.env`)
- `ANTHROPIC_API_KEY` — For Claude responses (set in `.env`)

### Vector DB Path
Set in `cdx-config.yaml`:
```yaml
data:
  vectors_db: .cdx/vectors.db
```

---

## Workflow: From Zero to Chat

```bash
# 1. Build indexes (Stage 0-2c, deterministic)
./_scripts/test-build.sh project-codeguard

# 2. Embed indexed entries (Stage 3, calls Voyage API)
./_scripts/test-build.sh project-codeguard --embed

# Result: .cdx/vectors.db populated with 30 embeddings
sqlite3 .cdx/vectors.db "SELECT COUNT(*) FROM entries;"
# Output: 30

# 3. Chat (queries vector DB, calls Claude API)
cdx-index chat project-codeguard

# Each query:
#   Query vector: Voyage API (~500ms)
#   KNN search: sqlite-vec (~50ms)
#   Metadata fetch: JSONL fallback (<10ms)
#   Claude response: API (~2-3s)
#   Total: ~3s per query
```

---

## Comparison with MCP Server

The chat app is a **prototype**. The MCP server will build on this foundation:

| Aspect | Chat App | MCP Server |
|--------|----------|-----------|
| **Interface** | Terminal stdin/stdout | HTTP/Protocol |
| **Caller** | Human at terminal | Claude in another context |
| **Query types** | Free-form questions | Tools with structured args |
| **Filtering** | None | project, kind, language filters |
| **Caching** | None | Result caching via Redis |
| **Concurrency** | Single user | Multi-user via HTTP |
| **Scaling** | One project at a time | Workspace-wide queries |

The vector search logic will be identical; the MCP server just adds:
- Structured tool interface
- Request/response serialization
- Concurrency & caching
- Integration with Claude's tool-use system

---

## Future Optimizations

1. **Query result caching** — Cache common queries (e.g., "What is CodeGuard?")
2. **Embedding batching** — Batch multiple queries for Voyage API efficiency
3. **Approximate nearest neighbor** — Use IVF or other approximate algorithms for large scale
4. **Domain-specific embeddings** — Fine-tune on CoSAI documentation for better relevance
5. **Multi-modal embeddings** — Include code snippets, diagrams, not just text
6. **Reranking** — Use a cross-encoder to rerank top-k results before returning to Claude

---

## Troubleshooting

**Q: "No vector store found"**
A: Run `cdx-index build --embed` to create vectors

**Q: "Invalid input_type"**
A: Use `input_type="query"` for searches, `"document"` for indexing

**Q: "Search returns no results"**
A: Normal — the query's embedding is far from all indexed vectors. Try rephrasing.

**Q: "Voyage API rate limited"**
A: Free tier has limits (~10 requests/min). Wait a moment and retry.

**Q: "embeddin_text is None"**
A: Fallback to JSONL; indicates an entry was in JSONL but not yet embedded. Run `--embed` again.
