# Vector Search Implementation Guide

Step-by-step guide on how to switch from in-memory keyword search to vector database search.

## Why Vector Search?

| Metric | Keyword Search | Vector Search |
|--------|----------------|---------------|
| **Semantic Understanding** | ❌ No | ✅ Yes |
| **Handles Synonyms** | ❌ No ("secure" ≠ "safety") | ✅ Yes |
| **Memory Usage** | ❌ High (all entries loaded) | ✅ Low (just DB connection) |
| **Speed (scale to 1M entries)** | ❌ O(n) = slow | ✅ O(log n) = fast |
| **Requires Pre-processing** | ❌ No | ✅ Yes (build --embed) |
| **API Calls Per Query** | ❌ None | ✅ 1 (Voyage) |

**Summary:** Vector search scales better, understands meaning, and handles flexible queries. Keyword search is simpler but limited.

---

## Implementation Steps

### Step 1: Define the VectorSearcher Class

**File: `chat.py`**

```python
from voyageai import Client as VoyageClient
from .vectorstore import VectorStore

class VectorSearcher:
    """Search indexed projects using Voyage vector embeddings."""
    
    def __init__(self, db_path: Path, indexes_dir: Path, 
                 project_slugs: list[str] | None = None):
        """Open vector store and initialize Voyage client."""
        # Validate DB exists
        if not db_path.exists():
            raise ClickException(
                f"Vector store not found at {db_path}. "
                "Run 'cdx-index build --embed' first."
            )
        
        # Load API keys from .env
        load_dotenv()
        
        # Open pre-computed vector store
        self.store = VectorStore.open(db_path)
        self.indexes_dir = indexes_dir
        self.project_slugs = project_slugs or self.store.list_projects()
        
        # Initialize Voyage client (reads VOYAGE_API_KEY from env)
        self.voyage_client = VoyageClient()
    
    def close(self):
        self.store.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *exc):
        self.close()
```

### Step 2: Implement the Search Method

```python
def search(self, query: str, limit: int = 5) -> list[dict]:
    """
    Vector search: embed query and find nearest neighbors.
    
    1. Embed user query via Voyage
    2. Search vector store for nearest 1024-dim vectors
    3. Filter to requested projects
    4. Fetch metadata for top results
    """
    # Step 1: Embed the query
    response = self.voyage_client.embed(
        [query],
        model="voyage-3",
        input_type="query"  # Optimized for search queries
    )
    query_vector = response.embeddings[0]  # 1024 floats
    
    # Step 2: KNN search in vector store
    hits = self.store.search(
        query_vector,
        k=limit * 2  # Over-fetch for filtering
    )
    
    # Step 3: Filter to requested projects and load metadata
    results = []
    for hit in hits:
        # Filter by project if specific ones requested
        if self.project_slugs and hit.project not in self.project_slugs:
            continue
        
        # Load full entry metadata from DB or JSONL
        metadata = self._get_entry_metadata(
            hit.project, hit.kind, hit.entry_id
        )
        if metadata:
            results.append({
                "project": hit.project,
                "kind": hit.kind,
                "entry_id": hit.entry_id,
                "distance": hit.distance,
                **metadata  # title, summary, path, tags
            })
        
        if len(results) >= limit:
            break
    
    return results
```

### Step 3: Add Metadata Loading

```python
def _get_entry_metadata(self, project: str, kind: str, 
                        entry_id: str) -> dict | None:
    """
    Load entry metadata from vector store or JSONL.
    
    Primary: Fast path via entries table (embedded_text field)
    Fallback: Read from JSONL if not in DB
    """
    # Try entries table first
    cur = self.store._conn.execute(
        "SELECT embedded_text FROM entries "
        "WHERE project = ? AND kind = ? AND entry_id = ?",
        (project, kind, entry_id)
    )
    row = cur.fetchone()
    if row and row[0]:
        try:
            return json.loads(row[0])  # embedded_text is JSON
        except json.JSONDecodeError:
            pass
    
    # Fallback: read from JSONL
    return self._load_from_jsonl(project, kind, entry_id)

def _load_from_jsonl(self, project: str, kind: str, 
                     entry_id: str) -> dict | None:
    """Load entry from JSONL file."""
    kind_to_file = {
        "package": "packages.jsonl",
        "snippet": "snippets.jsonl",
        "reference": "references.jsonl",
    }
    
    jsonl_file = kind_to_file.get(kind)
    if not jsonl_file:
        return None
    
    file_path = self.indexes_dir / project / jsonl_file
    if not file_path.exists():
        return None
    
    # Search JSONL for matching entry_id
    try:
        with file_path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    if entry.get("id") == entry_id:
                        return {
                            "id": entry["id"],
                            "title": entry.get("title", ""),
                            "summary": entry.get("summary", ""),
                            "path": entry.get("path", ""),
                            "tags": entry.get("tags", []),
                        }
    except (IOError, json.JSONDecodeError):
        pass
    
    return None
```

### Step 4: Update chat_loop()

Change from `IndexSearcher` to `VectorSearcher`:

```python
def chat_loop(searcher: VectorSearcher):  # Changed type
    """Interactive chat loop with vector search."""
    load_dotenv()
    client = anthropic.Anthropic()
    conversation_history = []
    
    # Show vector store stats
    total_vectors = searcher.store.count_vectors()
    click.echo(
        f"\nVector store: {total_vectors} embeddings across "
        f"{len(searcher.project_slugs)} project(s).",
        err=True
    )
    click.echo("Searching via semantic vector search.\n", err=True)
    
    while True:
        user_input = click.prompt("You").strip()
        if user_input.lower() in ("quit", "exit"):
            break
        if not user_input:
            continue
        
        # Vector search (will call Voyage API)
        try:
            search_results = searcher.search(user_input, limit=5)
        except Exception as e:
            click.echo(f"Search error: {e}", err=True)
            continue
        
        context = searcher.format_results(search_results)
        
        # Build system prompt with context from vector search
        system_prompt = f"""You are a helpful assistant.
INDEXED PROJECTS: {', '.join(sorted(searcher.project_slugs))}

RELEVANT ENTRIES (found via semantic vector search):
{context}

Answer based on these entries."""
        
        conversation_history.append({"role": "user", "content": user_input})
        
        # Get Claude response
        try:
            response = client.messages.create(
                model="claude-opus-4-7",
                max_tokens=1024,
                system=system_prompt,
                messages=conversation_history,
            )
            assistant_response = response.content[0].text
            conversation_history.append(
                {"role": "assistant", "content": assistant_response}
            )
            click.echo(f"\nAssistant: {assistant_response}\n")
        except Exception as e:
            click.echo(f"Error: {e}", err=True)
```

### Step 5: Update CLI Integration

In `cli.py`:

```python
# Change import
from .chat import VectorSearcher, chat_loop

# Update chat command
@cli.command()
@click.argument("projects", nargs=-1, type=str)
@click.pass_context
def chat(ctx: click.Context, projects: tuple[str, ...]):
    """Chat via vector search."""
    cfg: CdxConfig = ctx.obj["config"]
    project_list = list(projects) if projects else None
    
    try:
        # Use context manager for proper cleanup
        with VectorSearcher(
            cfg.vectors_db, 
            cfg.indexes_dir, 
            project_slugs=project_list
        ) as searcher:
            chat_loop(searcher)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
```

---

## Key Design Decisions

### 1. Why use `embedded_text` field?

When embedding entries, we store the combined text:
```python
# During indexing (embed.py)
embedded_text = json.dumps({
    "id": entry["id"],
    "title": entry["title"],
    "summary": entry["summary"],
    "path": entry["path"],
    "tags": entry["tags"],
})
store.upsert(..., embedded_text=embedded_text, ...)
```

Then during search, we fetch it:
```python
# During chat (chat.py)
cur.execute(
    "SELECT embedded_text FROM entries WHERE project = ? AND kind = ? AND entry_id = ?",
    (project, kind, entry_id)
)
metadata = json.loads(row[0])
```

**Why?**
- Avoids re-reading JSONL files for top results
- Fast metadata fetch (one DB query)
- Keeps JSONL as source of truth for all entries

### 2. Why lazy-load metadata?

Vector search returns only the nearest 5-10 hits. We only fetch metadata for those few, not for all 1000 entries.

```python
# We DON'T do this:
all_entries = [load_from_jsonl(p, k, e) for p, k, e in all_entries]
results = filter_by_distance(all_entries, query_vector)

# We DO this:
hits = store.search(query_vector, k=5)  # KNN on 1000 vectors
results = [load_from_jsonl(p, k, e) for p, k, e in hits[:5]]  # Load only 5
```

**Why?**
- Much faster: Load 5 items instead of 1000
- Lower memory: Only top results in memory
- Scales: Works with millions of entries

### 3. Why context manager?

```python
with VectorSearcher(...) as searcher:
    chat_loop(searcher)
# Automatically closes DB connection
```

**Why?**
- Ensures `store.close()` is called even if error occurs
- Prevents resource leaks
- Standard Python practice

---

## Data Flow Diagram

```
User Question
    │
    ├─→ Voyage API: embed(question)
    │       ↓
    │   1024-dim vector
    │       ↓
    ├─→ VectorStore.search(vector, k=5)
    │       ↓
    │   SQLite + sqlite-vec KNN
    │       ↓
    │   5 × SearchHit(project, kind, entry_id, distance)
    │       ↓
    ├─→ For each hit:
    │   │
    │   ├─→ entries table: SELECT embedded_text
    │   │       ↓
    │   │   json.loads() → {title, summary, path, tags}
    │   │   
    │   └─→ OR fallback: _load_from_jsonl()
    │       
    ├─→ format_results([metadata, metadata, ...])
    │       ↓
    │   "[1] Title\n    Project: ...\n    Summary: ...\n"
    │       ↓
    ├─→ Build system prompt with context
    │       ↓
    ├─→ Claude API: messages.create(system, messages)
    │       ↓
    └─→ Response → Save to history → Display
```

---

## Configuration

### pyproject.toml

Ensure these are in dependencies:
```toml
dependencies = [
    "voyageai>=0.3",        # For embeddings
    "sqlite-vec>=0.1",      # For KNN
    "anthropic>=0.40",      # For Claude
    ...
]
```

### .env

```
ANTHROPIC_API_KEY=sk-ant-...
VOYAGE_API_KEY=pa-...
```

### cdx-config.yaml

```yaml
data:
  vectors_db: .cdx/vectors.db
```

---

## Workflow

```bash
# 1. Build indexes (creates JSONL files)
./_scripts/test-build.sh project-codeguard

# 2. Build embeddings (creates vectors in .cdx/vectors.db)
./_scripts/test-build.sh project-codeguard --embed

# 3. Chat (queries vectors via VectorSearcher)
cdx-index chat project-codeguard

# Each query flow:
#   1. User types question
#   2. Voyage embeds it (~500ms)
#   3. sqlite-vec KNN search (~50ms)
#   4. Load 5 metadata from DB (~10ms)
#   5. Claude generates response (~2-3s)
#   Total: ~3s per query
```

---

## Testing

```python
# Unit test example
def test_vector_search():
    searcher = VectorSearcher(
        db_path=Path(".cdx/vectors.db"),
        indexes_dir=Path(".cosai-indexes"),
        project_slugs=["project-codeguard"]
    )
    
    results = searcher.search("What security rules exist?", limit=5)
    
    assert len(results) <= 5
    assert all("project" in r for r in results)
    assert all("distance" in r for r in results)
    assert all(r["distance"] >= 0 for r in results)
    
    searcher.close()
```

---

## Common Issues & Solutions

### Issue: "No API key provided"

**Cause:** `.env` not loaded or key not set

**Solution:**
```bash
# Check .env exists
cat .env | grep VOYAGE_API_KEY

# Load manually in code
load_dotenv()  # Called in __init__
```

### Issue: "Vector store not found"

**Cause:** Haven't run `--embed` flag yet

**Solution:**
```bash
./_scripts/test-build.sh your-project --embed
```

### Issue: "Search returns empty results"

**Cause:** Query vector is far from all indexed vectors (normal)

**Solution:**
→ Try rephrasing the question

### Issue: "Voyage API rate limited"

**Cause:** Free tier limits (~3 requests/minute)

**Solution:**
→ Wait a moment or add payment method to Voyage account

---

## Next Steps

This implementation is production-ready for a local chat app. The MCP server will reuse the `VectorSearcher` class:

```python
# MCP server usage (future)
class CodeguardMCPServer:
    def __init__(self):
        self.searcher = VectorSearcher(
            db_path=Path(".cdx/vectors.db"),
            indexes_dir=Path(".cosai-indexes")
        )
    
    @tool("search_codeguard")
    def search(self, query: str) -> list[dict]:
        """MCP tool wrapping VectorSearcher."""
        return self.searcher.search(query, limit=5)
```

The search logic is abstracted; the interface is all that changes.
