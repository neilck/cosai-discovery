"""Terminal chat application for querying indexed projects via vector search.

Uses Voyage embeddings + SQLite vector store for semantic search.
No JSONL files loaded into memory; all queries hit the vector DB.

Usage:
    cdx-index chat [PROJECT_SLUG...]

Examples:
    cdx-index chat                    # chat across all indexed projects
    cdx-index chat project-codeguard  # chat with one project
"""

from __future__ import annotations

import json
from pathlib import Path

import anthropic
import click
import voyageai
from dotenv import load_dotenv

from .config import CdxConfig
from .vectorstore import VectorStore


class VectorSearcher:
    """Search indexed projects using Voyage vector embeddings.

    Queries the vector store directly; no JSONL files loaded into memory.
    """

    def __init__(self, db_path: Path, indexes_dir: Path, project_slugs: list[str] | None = None):
        """Open the vector store and discover projects.

        Args:
            db_path: Path to vectors.db
            indexes_dir: Path to .cosai-indexes/ (used to read manifest files for metadata)
            project_slugs: Optional list of projects to filter. If None, all in DB are used.
        """
        if not db_path.exists():
            raise click.ClickException(
                f"Vector store not found at {db_path}. "
                "Run 'cdx-index build --embed' first to create vectors."
            )

        # Ensure API keys are loaded
        load_dotenv()

        self.store = VectorStore.open(db_path)
        self.indexes_dir = indexes_dir
        self.project_slugs = project_slugs or self.store.list_projects()
        self.voyage_client = voyageai.Client()

        # Load manifest files for metadata (title, description, etc.)
        self.manifests: dict[str, dict] = {}
        for slug in self.project_slugs:
            manifest_path = indexes_dir / slug / "manifest.json"
            if manifest_path.exists():
                try:
                    self.manifests[slug] = json.loads(manifest_path.read_text())
                except (json.JSONDecodeError, IOError):
                    pass

    def close(self):
        """Close the vector store connection."""
        self.store.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """Vector search: embed query and find nearest neighbors.

        Args:
            query: User's question
            limit: Number of results to return

        Returns:
            List of dicts with project, kind, entry_id, distance, metadata
        """
        # Embed the query using Voyage
        response = self.voyage_client.embed(
            [query],
            model="voyage-3",
            input_type="query"
        )
        query_vector = response.embeddings[0]

        # Vector search in store with optional project filtering
        filters = {}
        if self.project_slugs and len(self.project_slugs) < len(self.store.list_projects()):
            # Only filter if specific projects were requested
            filters["projects"] = self.project_slugs

        # Search all projects in DB, filter results post-query
        hits = self.store.search(query_vector, k=limit * 2)  # Over-fetch to filter

        # Filter to requested projects
        results = []
        for hit in hits:
            if self.project_slugs and hit.project not in self.project_slugs:
                continue

            # Fetch full entry metadata from JSONL
            entry_metadata = self._get_entry_metadata(hit.project, hit.kind, hit.entry_id)
            if entry_metadata:
                results.append({
                    "project": hit.project,
                    "kind": hit.kind,
                    "entry_id": hit.entry_id,
                    "distance": hit.distance,
                    **entry_metadata,  # title, summary, path, tags, etc.
                })

            if len(results) >= limit:
                break

        return results

    def _get_entry_metadata(self, project: str, kind: str, entry_id: str) -> dict | None:
        """Load entry metadata from JSONL file.

        Uses the vector store's embedded_text field if available, or reads from JSONL.
        """
        # Try to fetch from entries table (has embedded_text field)
        cur = self.store._conn.execute(
            "SELECT embedded_text FROM entries WHERE project = ? AND kind = ? AND entry_id = ?",
            (project, kind, entry_id)
        )
        row = cur.fetchone()
        if row and row[0]:
            # embedded_text is stored as a JSON string for convenience
            try:
                return json.loads(row[0])
            except json.JSONDecodeError:
                pass

        # Fallback: read from JSONL
        return self._load_from_jsonl(project, kind, entry_id)

    def _load_from_jsonl(self, project: str, kind: str, entry_id: str) -> dict | None:
        """Load entry from JSONL file as fallback."""
        kind_to_file = {
            "package": "packages.jsonl",
            "snippet": "snippets.jsonl",
            "reference": "references.jsonl",
            "manifest": "manifest.json",
        }

        jsonl_file = kind_to_file.get(kind)
        if not jsonl_file:
            return None

        file_path = self.indexes_dir / project / jsonl_file
        if not file_path.exists():
            return None

        try:
            if kind == "manifest":
                # manifest.json is a single JSON file
                data = json.loads(file_path.read_text())
                return {
                    "id": f"manifest:{project}",
                    "title": data.get("description", "")[:100],
                    "summary": data.get("description", ""),
                    "path": "manifest.json",
                }

            # JSONL files: search for matching entry_id
            with file_path.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            entry = json.loads(line)
                            if entry.get("id") == entry_id:
                                return {
                                    "id": entry.get("id"),
                                    "title": entry.get("title", ""),
                                    "summary": entry.get("summary", ""),
                                    "path": entry.get("path", ""),
                                    "tags": entry.get("tags", []),
                                }
                        except json.JSONDecodeError:
                            continue
        except (IOError, OSError):
            pass

        return None

    def format_results(self, results: list[dict]) -> str:
        """Format search results as context for the LLM."""
        if not results:
            return "(No matching entries found in vector store)"

        lines = []
        for i, result in enumerate(results, 1):
            lines.append(f"[{i}] {result.get('title', result.get('id', 'untitled'))}")
            lines.append(f"    Project: {result['project']}")
            lines.append(f"    Type: {result['kind']}")
            lines.append(f"    Relevance: {1 - result['distance']:.2%}")  # Convert distance to relevance
            if result.get("summary"):
                summary = result["summary"]
                if len(summary) > 150:
                    summary = summary[:150] + "..."
                lines.append(f"    Summary: {summary}")
            if result.get("path"):
                lines.append(f"    Path: {result['path']}")
            lines.append("")

        return "\n".join(lines)


def chat_loop(searcher: VectorSearcher):
    """Interactive chat loop with vector-search-augmented responses."""
    # Load .env file to ensure API keys are available
    load_dotenv()
    client = anthropic.Anthropic()
    conversation_history: list[dict] = []

    # Count total vectors in store
    total_vectors = searcher.store.count_vectors()
    click.echo(
        f"\nVector store: {total_vectors} embeddings across {len(searcher.project_slugs)} project(s).",
        err=True,
    )
    click.echo("Searching via semantic vector search. Type 'quit' or 'exit' to leave.\n", err=True)

    while True:
        try:
            user_input = click.prompt("You").strip()
        except EOFError:
            break

        if user_input.lower() in ("quit", "exit"):
            break

        if not user_input:
            continue

        # Vector search for relevant entries
        try:
            search_results = searcher.search(user_input, limit=5)
        except Exception as e:  # noqa: BLE001
            click.echo(f"Search error: {e}", err=True)
            continue

        context = searcher.format_results(search_results)

        # Build system prompt with search context
        system_prompt = f"""You are a helpful assistant answering questions about CoSAI projects.
You have access to indexed project documentation and code via vector search.

INDEXED PROJECTS: {', '.join(sorted(searcher.project_slugs))}

When answering questions, reference the relevant indexed entries below.
Be specific about which projects or files you're referencing.

RELEVANT INDEXED ENTRIES (found via semantic search):
{context}

If the question cannot be answered from the indexed entries, say so clearly."""

        # Add user message to conversation
        conversation_history.append({"role": "user", "content": user_input})

        # Get response from Claude
        try:
            response = client.messages.create(
                model="claude-opus-4-7",
                max_tokens=1024,
                system=system_prompt,
                messages=conversation_history,
            )
            assistant_response = response.content[0].text

            # Add assistant response to conversation history
            conversation_history.append(
                {"role": "assistant", "content": assistant_response}
            )

            click.echo(f"\nAssistant: {assistant_response}\n")
        except Exception as e:  # noqa: BLE001
            click.echo(f"Error: {e}", err=True)


@click.command()
@click.argument("projects", nargs=-1, type=str)
@click.option(
    "--config",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to cdx-config.yaml. Auto-discovered by default.",
)
def main(projects: tuple[str, ...], config: Path | None):
    """Chat with indexed CoSAI projects via vector search."""
    cfg = CdxConfig.load(config_path=config)
    project_list = list(projects) if projects else None

    try:
        with VectorSearcher(cfg.vectors_db, cfg.indexes_dir, project_slugs=project_list) as searcher:
            chat_loop(searcher)
    except Exception as e:  # noqa: BLE001
        raise click.ClickException(str(e)) from e


if __name__ == "__main__":
    main()
