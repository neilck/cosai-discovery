"""Stage 2b: Per-snippet fact gathering and LLM summarization.

Consumes entry_plan_snippets from Stage 1 and produces Snippet entries with:
- Deterministic facts: line range, symbol (top function/class), depends_on (imports)
- LLM-generated: title, summary, tags

Symbol/import extraction uses lightweight regex for Python, TypeScript, and Go
(see `_extract_*` helpers). Notebooks (.ipynb) extract code-cell text and treat
sibling files in the same directory as depends_on.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any, TypedDict

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from .planner import DEFAULT_CHECKPOINT_DB, EntryPlanSnippet
from .scan import ProjectScan
from .types import Snippet

DEFAULT_MODEL = "claude-haiku-4-5"

# Max snippet content sent to the LLM. Most snippets are <5KB.
SNIPPET_CONTENT_MAX_CHARS = 8_000


# -------- Prompts --------

_PROMPT_DIR = files("cdx_indexer.prompts")
SYSTEM_PROMPT = _PROMPT_DIR.joinpath("stage2b_system.md").read_text(encoding="utf-8")
_USER_TEMPLATE = _PROMPT_DIR.joinpath("stage2b_user.md.tmpl").read_text(encoding="utf-8")


# -------- Deterministic fact gathering --------


@dataclass
class SnippetFacts:
    """Deterministic facts extracted from a snippet file."""

    project: str
    slug: str  # used in the id and as a fallback title
    path: str
    language: str
    depends_on: list[str]
    content_hash: str
    # For LLM context:
    content_excerpt: str  # the file content (trimmed)


def gather_snippet_facts(plan_entry: EntryPlanSnippet, scan: ProjectScan, project_path: Path) -> SnippetFacts | None:
    """Extract deterministic facts from a plan entry.

    Returns None if the file can't be read.
    """
    project_path = project_path.resolve()
    file_path = project_path / plan_entry.path

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    language = (plan_entry.language or "").lower()
    depends_on = _extract_depends_on(content, language, file_path, project_path)

    # Slug for id: filename without extension, with path segments joined by '-'.
    rel = Path(plan_entry.path)
    slug = "/".join(rel.with_suffix("").parts)

    # Trim content for LLM context.
    excerpt = content if len(content) <= SNIPPET_CONTENT_MAX_CHARS else (
        content[:SNIPPET_CONTENT_MAX_CHARS] + f"\n\n[... truncated; full file is {len(content)} chars ...]"
    )

    hash_inputs = {
        "path": plan_entry.path,
        "language": language,
        # Hash the content too so re-runs after edits get fresh summaries.
        "content_len": len(content),
        "content_head": content[:1024],
    }
    content_hash = "sha256:" + hashlib.sha256(
        json.dumps(hash_inputs, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]

    return SnippetFacts(
        project=scan.project_slug,
        slug=slug,
        path=plan_entry.path,
        language=plan_entry.language,
        depends_on=depends_on,
        content_hash=content_hash,
        content_excerpt=excerpt,
    )


# -------- Imports / depends_on --------


_RE_PY_IMPORT = re.compile(r"^(?:from\s+([A-Za-z_][\w.]*)\s+import|import\s+([A-Za-z_][\w.]*))", re.MULTILINE)
_RE_TS_IMPORT = re.compile(r"""^import\s+(?:.+?\s+from\s+)?['"]([^'"]+)['"]""", re.MULTILINE)
_RE_GO_IMPORT_SINGLE = re.compile(r'^\s*import\s+"([^"]+)"', re.MULTILINE)
_RE_GO_IMPORT_BLOCK = re.compile(r"import\s*\(\s*([^)]+)\)", re.DOTALL)
_RE_GO_IMPORT_LINE = re.compile(r'"([^"]+)"')


def _extract_depends_on(content: str, language: str, file_path: Path, project_path: Path) -> list[str]:
    """Return a deduplicated list of imports the snippet actually uses.

    For notebooks, also include sibling files in the same directory.
    """
    deps: list[str] = []

    if file_path.suffix == ".ipynb":
        # Notebook: include sibling files (utils, fixtures) in the same dir.
        try:
            parent = file_path.parent
            for sib in sorted(parent.iterdir()):
                if sib == file_path or sib.is_dir():
                    continue
                if sib.name.startswith("."):
                    continue
                rel = sib.relative_to(project_path)
                deps.append(str(rel))
        except OSError:
            pass
        # Also pull imports from concatenated cell source code.
        deps.extend(_extract_py_imports(content))
        return _dedupe(deps)

    if language in ("python", "py"):
        deps.extend(_extract_py_imports(content))
    elif language in ("typescript", "ts", "javascript", "js"):
        deps.extend(m.group(1) for m in _RE_TS_IMPORT.finditer(content))
    elif language in ("go",):
        # Single-line imports.
        deps.extend(m.group(1) for m in _RE_GO_IMPORT_SINGLE.finditer(content))
        # Block imports.
        for block in _RE_GO_IMPORT_BLOCK.findall(content):
            deps.extend(_RE_GO_IMPORT_LINE.findall(block))

    return _dedupe(deps)


def _extract_py_imports(content: str) -> list[str]:
    """Extract top-level imported modules from Python source."""
    out: list[str] = []
    for m in _RE_PY_IMPORT.finditer(content):
        out.append(m.group(1) or m.group(2))
    return out


def _dedupe(items: list[str]) -> list[str]:
    """Order-preserving dedupe; drops empty strings."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


# -------- LLM summarization --------


class _SnippetState(TypedDict, total=False):
    facts: SnippetFacts
    raw_llm_response: str
    parsed: dict[str, Any]
    snippet: Snippet


def _build_user_prompt(facts: SnippetFacts) -> str:
    """Render the user prompt for a single snippet."""
    context = {
        "path": facts.path,
        "language": facts.language,
        "depends_on": facts.depends_on,
        "content": facts.content_excerpt,
    }
    return _USER_TEMPLATE.replace("{snippet_facts}", json.dumps(context, indent=2, default=str))


def run_snippets(
    scan: ProjectScan,
    plan_entries: list[EntryPlanSnippet],
    project_path: Path,
    model: str | None = None,
    checkpoint_db_path: Path | None = None,
) -> list[Snippet]:
    """Run Stage 2b on all snippets in the entry plan."""
    if not plan_entries:
        return []

    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY not set. Add to .env or export before running.")

    chosen_model = model or os.environ.get("CDX_MODEL", DEFAULT_MODEL)
    db_path = checkpoint_db_path or Path(DEFAULT_CHECKPOINT_DB).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    project_path = project_path.resolve()
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    snippets: list[Snippet] = []

    try:
        for plan_entry in plan_entries:
            facts = gather_snippet_facts(plan_entry, scan, project_path)
            if facts is None:
                continue

            thread_id = f"{scan.project_slug}:snip:{facts.slug}@{facts.content_hash[:8]}"
            graph = _build_graph(chosen_model, checkpointer)
            config = {"configurable": {"thread_id": thread_id}}

            existing = graph.get_state(config)
            if existing and existing.values and existing.values.get("snippet"):
                snippets.append(existing.values["snippet"])
                continue

            initial_state: _SnippetState = {"facts": facts}
            final_state = graph.invoke(initial_state, config=config)
            if "snippet" in final_state:
                snippets.append(final_state["snippet"])

    finally:
        conn.close()

    return snippets


def _build_graph(model: str, checkpointer: SqliteSaver):
    """Build the per-snippet LangGraph state machine."""
    llm = ChatAnthropic(
        model=model,
        temperature=0,
        max_tokens=1024,
        max_retries=5,
        timeout=120.0,
    )

    def call_llm(state: _SnippetState) -> _SnippetState:
        facts = state["facts"]
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=_build_user_prompt(facts)),
        ]
        response = llm.invoke(messages)
        text = response.content if isinstance(response.content, str) else str(response.content)
        return {**state, "raw_llm_response": text}

    def parse_response(state: _SnippetState) -> _SnippetState:
        text = state["raw_llm_response"]
        parsed = _parse_llm_json(text)
        return {**state, "parsed": parsed}

    def shape_output(state: _SnippetState) -> _SnippetState:
        facts = state["facts"]
        parsed = state["parsed"]

        snip = Snippet(
            id=f"snip:{facts.project}/{facts.slug}",
            category="snippet",
            kind="library",  # placeholder — revisit after seeing real output
            title=parsed.get("title", "") or facts.slug,
            path=facts.path,
            language=facts.language,
            summary=parsed.get("summary", ""),
            tags=parsed.get("tags", []) or [],
            depends_on=facts.depends_on,
            content_hash=facts.content_hash,
        )
        return {**state, "snippet": snip}

    graph = StateGraph(_SnippetState)
    graph.add_node("call_llm", call_llm)
    graph.add_node("parse_response", parse_response)
    graph.add_node("shape_output", shape_output)
    graph.add_edge(START, "call_llm")
    graph.add_edge("call_llm", "parse_response")
    graph.add_edge("parse_response", "shape_output")
    graph.add_edge("shape_output", END)
    return graph.compile(checkpointer=checkpointer)


def _parse_llm_json(text: str) -> dict[str, Any]:
    """Parse the LLM's JSON response, tolerating fences and surrounding text."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    if start == -1:
        raise ValueError(f"LLM response did not contain JSON: {text[:200]!r}")
    depth = 0
    for i in range(start, len(cleaned)):
        if cleaned[i] == "{":
            depth += 1
        elif cleaned[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(cleaned[start : i + 1])
    raise ValueError(f"LLM response had unbalanced braces: {text[:200]!r}")
