"""Terminal chat application for querying indexed projects via vector search.

Uses Voyage embeddings + SQLite vector store for semantic search.
Claude can call a `search_projects` tool with optional filters.

Usage:
    cdx-index chat [PROJECT_SLUG...]

Examples:
    cdx-index chat                    # chat across all indexed projects
    cdx-index chat project-codeguard  # chat with one project
"""

from __future__ import annotations

from pathlib import Path

import anthropic
import click
import voyageai
from dotenv import load_dotenv

from .config import CdxConfig
from .vectorstore import VectorStore


class VectorSearcher:
    """Search indexed projects using Voyage vector embeddings.

    Metadata is queried from the vector store database, not from JSONL files.
    """

    def __init__(self, db_path: Path, project_slugs: list[str] | None = None):
        """Open the vector store and discover projects.

        Args:
            db_path: Path to vectors.db
            project_slugs: Optional list of projects to filter. If None, all in DB are used.
        """
        if not db_path.exists():
            raise click.ClickException(
                f"Vector store not found at {db_path}. "
                "Run 'cdx-index build --embed' first to create vectors."
            )

        load_dotenv()

        self.store = VectorStore.open(db_path)
        self.project_slugs = project_slugs or self.store.list_projects()
        self.voyage_client = voyageai.Client()

    def close(self):
        """Close the vector store connection."""
        self.store.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):  # noqa: ARG002
        self.close()

    def search(
        self,
        query: str,
        limit: int = 5,
        project: str | None = None,
        kind: str | None = None,
    ) -> list[dict]:
        """Vector search with optional project/kind filters.

        Args:
            query: User's question
            limit: Number of results to return
            project: Optional project slug to filter
            kind: Optional kind (package|snippet|reference|manifest) to filter

        Returns:
            List of dicts with project, kind, entry_id, distance, title, summary, path, tags
        """
        response = self.voyage_client.embed([query], model="voyage-3", input_type="query")
        query_vector = response.embeddings[0]

        # Respect requested projects; apply kind filter if provided
        proj_filter = project if project and project in self.project_slugs else None
        if proj_filter is None and self.project_slugs and len(self.project_slugs) < len(
            self.store.list_projects()
        ):
            # Filter to requested project list only if a subset was passed to __init__
            proj_list = self.project_slugs
            hits = self.store.search(query_vector, k=limit * 2, kind=kind)
            results = []
            for hit in hits:
                if hit.project in proj_list:
                    meta = self.store.get_entry_metadata(hit.project, hit.kind, hit.entry_id)
                    if meta:
                        results.append(
                            {
                                "project": hit.project,
                                "kind": hit.kind,
                                "entry_id": hit.entry_id,
                                "distance": hit.distance,
                                **meta,
                            }
                        )
                if len(results) >= limit:
                    break
            return results

        # No project filter; just apply kind and limit
        hits = self.store.search(query_vector, k=limit, project=proj_filter, kind=kind)
        results = []
        for hit in hits:
            meta = self.store.get_entry_metadata(hit.project, hit.kind, hit.entry_id)
            if meta:
                results.append(
                    {
                        "project": hit.project,
                        "kind": hit.kind,
                        "entry_id": hit.entry_id,
                        "distance": hit.distance,
                        **meta,
                    }
                )
        return results

    def format_results(self, results: list[dict]) -> str:
        """Format search results as context for the LLM."""
        if not results:
            return "(No matching entries found)"

        lines = []
        for i, result in enumerate(results, 1):
            lines.append(f"[{i}] {result.get('title', result.get('entry_id', 'untitled'))}")
            lines.append(f"    Project: {result['project']}")
            lines.append(f"    Type: {result['kind']}")
            distance = result['distance']
            relevance_score = max(0, 1 - distance)  # Clamp to [0, 1] for display
            lines.append(f"    Match: {relevance_score:.2%}")
            if result.get("summary"):
                summary = result["summary"]
                if len(summary) > 150:
                    summary = summary[:150] + "..."
                lines.append(f"    Summary: {summary}")
            if result.get("path"):
                lines.append(f"    Path: {result['path']}")
            lines.append("")

        return "\n".join(lines)


def _build_system_prompt(searcher: VectorSearcher) -> str:
    """Build static system prompt with project summaries."""
    project_lines = []
    for slug in sorted(searcher.project_slugs):
        meta = searcher.store.get_entry_metadata(slug, "manifest", slug)
        if meta:
            summary = meta.get("summary", "")
            tags = ", ".join(meta.get("tags", []))
            if tags:
                project_lines.append(f"- **{slug}**: {summary}\n  Tags: {tags}")
            else:
                project_lines.append(f"- **{slug}**: {summary}")

    projects_overview = "\n".join(project_lines)

    return f"""You are a helpful assistant answering questions about CoSAI OASIS projects.

## Indexed Projects

{projects_overview}

## How to Search

Use the `search_projects` tool to find relevant entries. You can filter by:
- `project`: limit to one project slug (e.g. "project-codeguard")
- `kind`: one of package | snippet | reference | manifest
- `limit`: number of results (default 5, max 10)

Call the tool as many times as needed. If your first search misses something, try a different query or filter.
When results are not relevant to the question, say so clearly."""


SEARCH_TOOL = {
    "name": "search_projects",
    "description": "Semantic search across indexed CoSAI project entries.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search for"},
            "project": {
                "type": "string",
                "description": "Optional: filter to one project slug (e.g. 'project-codeguard')",
            },
            "kind": {
                "type": "string",
                "enum": ["package", "snippet", "reference", "manifest"],
                "description": "Optional: filter to one entry type",
            },
            "limit": {
                "type": "integer",
                "default": 5,
                "maximum": 10,
                "description": "Number of results to return",
            },
        },
        "required": ["query"],
    },
}


def chat_loop(searcher: VectorSearcher):
    """Interactive chat loop with tool-use search."""
    load_dotenv()
    client = anthropic.Anthropic()
    conversation_history: list[dict] = []
    system_prompt = _build_system_prompt(searcher)

    total_vectors = searcher.store.count_vectors()
    click.echo(
        f"\nVector store: {total_vectors} embeddings across {len(searcher.project_slugs)} project(s).",
        err=True,
    )
    click.echo("Tool-enabled search. Type 'quit' or 'exit' to leave.\n", err=True)

    while True:
        try:
            user_input = click.prompt("You").strip()
        except EOFError:
            break

        if user_input.lower() in ("quit", "exit"):
            break

        if not user_input:
            continue

        # Add user message to conversation
        conversation_history.append({"role": "user", "content": user_input})

        # Agentic loop: handle tool calls until stop_reason != "tool_use"
        while True:
            try:
                response = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=1024,
                    system=system_prompt,
                    tools=[SEARCH_TOOL],
                    messages=conversation_history,
                )
            except Exception as e:  # noqa: BLE001
                click.echo(f"Error: {e}", err=True)
                break

            # Collect text and tool_use blocks
            text_content = []
            tool_calls = []
            for block in response.content:
                if block.type == "text":
                    text_content.append(block.text)
                elif block.type == "tool_use":
                    tool_calls.append(block)

            # Show any text response immediately
            if text_content:
                full_text = "\n".join(text_content)
                click.echo(f"\nAssistant: {full_text}\n")

            # Add assistant response to history (before tool results)
            conversation_history.append({"role": "assistant", "content": response.content})

            # If no tool calls, we're done with this turn
            if response.stop_reason != "tool_use" or not tool_calls:
                break

            # Process tool calls
            tool_results = []
            for tool_call in tool_calls:
                if tool_call.name == "search_projects":
                    inp = tool_call.input
                    try:
                        results = searcher.search(
                            query=inp["query"],
                            limit=inp.get("limit", 5),
                            project=inp.get("project"),
                            kind=inp.get("kind"),
                        )
                        content = searcher.format_results(results)
                    except Exception as e:  # noqa: BLE001
                        content = f"Search error: {e}"

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_call.id,
                            "content": content,
                        }
                    )

            # Add tool results to conversation and loop
            if tool_results:
                conversation_history.append({"role": "user", "content": tool_results})


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
        with VectorSearcher(cfg.vectors_db, project_slugs=project_list) as searcher:
            chat_loop(searcher)
    except Exception as e:  # noqa: BLE001
        raise click.ClickException(str(e)) from e


if __name__ == "__main__":
    main()
