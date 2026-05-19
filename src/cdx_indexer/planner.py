"""Stage 1: LLM-driven classification + entry planning.

Consumes the deterministic ProjectScan from Stage 0 and produces:
  - Manifest filter-side fields (description, primary_kind, also, status, owners, tags, builds_on, license)
  - An entry plan for Stages 2a/2b/2c (packages/snippets/references)

Implemented as a LangGraph state machine. Stage 1 is currently a single node;
the graph shape leaves room for Stages 2a/2b/2c to fan out in later phases.

The LLM is asked to return strict JSON. Output is validated against a Pydantic
model before being merged into the Manifest.
"""

from __future__ import annotations

import hashlib
import json
import os
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

from .scan import ProjectScan

# Default models, overridable via env.
DEFAULT_MODEL = "claude-haiku-4-5"
DEFAULT_MODEL_STRONG = "claude-sonnet-4-6"

# Default location for the LangGraph checkpoint database, anchored to the
# repo root (the directory containing pyproject.toml). Walking up from this
# file's location avoids creating stray .data/ directories under whatever
# directory the user happened to invoke `cdx-index` from.
def _find_repo_root() -> Path:
    """Walk up from this file to find the directory containing pyproject.toml."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    # Fallback: cwd. Should never hit this in a normal install.
    return Path.cwd()


DEFAULT_CHECKPOINT_DB = str(_find_repo_root() / ".data" / "checkpoints.db")


# -------- Prompts (loaded from package-data files) --------

_PROMPT_DIR = files("cdx_indexer.prompts")
SYSTEM_PROMPT = _PROMPT_DIR.joinpath("stage1_system.md").read_text(encoding="utf-8")
_USER_TEMPLATE = _PROMPT_DIR.joinpath("stage1_user.md.tmpl").read_text(encoding="utf-8")


# -------- State + outputs --------


@dataclass
class EntryPlanPackage:
    manifest_path: str  # relative path to the manifest file (pyproject.toml, package.json, etc.)
    language: str
    ecosystem: str
    name: str
    reason: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EntryPlanPackage":
        return cls(
            manifest_path=d["manifest_path"],
            language=d["language"],
            ecosystem=d["ecosystem"],
            name=d["name"],
            reason=d.get("reason", ""),
        )


@dataclass
class EntryPlanSnippet:
    path: str
    language: str
    reason: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EntryPlanSnippet":
        return cls(path=d["path"], language=d["language"], reason=d.get("reason", ""))


@dataclass
class EntryPlanReference:
    path: str
    form: str  # prose | structured | mixed
    reason: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EntryPlanReference":
        return cls(path=d["path"], form=d["form"], reason=d.get("reason", ""))


@dataclass
class PlannerOutput:
    """Full Stage 1 output: manifest fields + entry plan."""

    description: str
    primary_kind: str
    primary_kind_other: str | None
    also: list[str]
    status: str
    owners: list[str]
    tags: list[str]
    languages: list[str]
    license: str | None
    related_urls: list[str]
    entry_plan_packages: list[EntryPlanPackage]
    entry_plan_snippets: list[EntryPlanSnippet]
    entry_plan_references: list[EntryPlanReference]
    raw_llm_response: str  # kept for debugging / cache


# -------- Internal LangGraph state --------


class _PlannerState(TypedDict, total=False):
    scan: ProjectScan
    raw_llm_response: str
    parsed: dict[str, Any]
    output: PlannerOutput


# -------- Prompt --------


def _build_user_prompt(scan: ProjectScan) -> str:
    """Render the user prompt from the loaded template + the project's facts."""
    facts_json = json.dumps(scan.to_dict(), indent=2, default=str)
    return _USER_TEMPLATE.replace("{project_facts}", facts_json)


# -------- Public entry point --------


@dataclass
class PlannerResult:
    """Outcome of run_planner."""

    output: PlannerOutput
    cached: bool  # True if served from checkpoint, no LLM call made
    thread_id: str


def run_planner(
    scan: ProjectScan,
    model: str | None = None,
    checkpoint_db_path: Path | None = None,
    force: bool = False,
) -> PlannerResult:
    """Run Stage 1 against a ProjectScan with LangGraph checkpointing.

    The thread_id encodes the project slug plus a hash of the scan's content,
    so a checkpoint is reused only when the project's facts are unchanged.

    Behaviour:
      - If `force=False` and a checkpoint exists for this scan, return the
        cached PlannerOutput (no LLM call).
      - If `force=True`, ignore any existing checkpoint and re-run.
    """
    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Add it to .env (see .env.example) "
            "or export it before running."
        )

    chosen_model = model or os.environ.get("CDX_MODEL", DEFAULT_MODEL)
    db_path = checkpoint_db_path or Path(DEFAULT_CHECKPOINT_DB).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    thread_id = _thread_id_for(scan, chosen_model)
    config = {"configurable": {"thread_id": thread_id}}

    # Set up a SQLite checkpointer; reused across runs.
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    try:
        graph = _build_graph(chosen_model, checkpointer)

        if force:
            # Wipe the prior checkpoint for this thread before invoking.
            _clear_checkpoint(conn, thread_id)
            initial_state: _PlannerState = {"scan": scan}
            final_state = graph.invoke(initial_state, config=config)
            return PlannerResult(output=final_state["output"], cached=False, thread_id=thread_id)

        # Otherwise, check whether the thread already has a completed run.
        existing_state = graph.get_state(config)
        completed = (
            existing_state is not None
            and existing_state.values
            and existing_state.values.get("output") is not None
        )
        if completed:
            return PlannerResult(
                output=existing_state.values["output"],
                cached=True,
                thread_id=thread_id,
            )

        # No prior completion → run.
        initial_state = {"scan": scan}
        final_state = graph.invoke(initial_state, config=config)
        return PlannerResult(output=final_state["output"], cached=False, thread_id=thread_id)
    finally:
        conn.close()


def _thread_id_for(scan: ProjectScan, model: str) -> str:
    """Compose a deterministic thread id from the project slug + scan content + model.

    Including the model in the hash means a checkpoint produced with Haiku is
    not reused if the user requests Sonnet (output may differ).

    Ephemeral fields (scanned_at, project_path absolute prefix) are excluded
    so re-running on unchanged content produces the same id.
    """
    facts = scan.to_dict()
    facts.pop("scanned_at", None)
    # Absolute paths are machine-specific; the project_slug + relative file_tree
    # already identifies the project's content.
    facts.pop("project_path", None)
    facts.pop("workspace_root", None)
    payload = json.dumps(facts, sort_keys=True, default=str)
    digest = hashlib.sha256((payload + "|" + model).encode("utf-8")).hexdigest()[:16]
    return f"{scan.project_slug}@{digest}"


def _clear_checkpoint(conn: sqlite3.Connection, thread_id: str) -> None:
    """Remove all checkpoints for the given thread_id. Safe even if the thread
    has no prior checkpoints (DELETE on a missing row is a no-op).
    """
    try:
        with conn:
            for table in ("checkpoints", "writes"):
                try:
                    conn.execute(f"DELETE FROM {table} WHERE thread_id = ?", (thread_id,))
                except sqlite3.OperationalError:
                    # Table doesn't exist yet (first run before any checkpoint written).
                    pass
    except sqlite3.Error:
        # Best-effort; if the wipe fails, the invocation below will still
        # produce a fresh result. The stale checkpoint will simply be
        # overlaid by the new run's final state.
        pass


# -------- Graph nodes --------


def _build_graph(model: str, checkpointer: SqliteSaver):
    """Build the LangGraph state machine with a SQLite checkpointer."""
    # `max_retries` retries on transient API errors (529 overloaded, 503,
    # rate-limit responses, network blips) with exponential backoff. The
    # underlying anthropic SDK handles the delay between retries.
    llm = ChatAnthropic(
        model=model,
        temperature=0,
        max_tokens=4096,
        max_retries=5,
        timeout=120.0,
    )

    def call_llm(state: _PlannerState) -> _PlannerState:
        scan = state["scan"]
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=_build_user_prompt(scan)),
        ]
        response = llm.invoke(messages)
        text = response.content if isinstance(response.content, str) else _stringify(response.content)
        return {**state, "raw_llm_response": text}

    def parse_response(state: _PlannerState) -> _PlannerState:
        text = state["raw_llm_response"]
        parsed = _parse_llm_json(text)
        return {**state, "parsed": parsed}

    def shape_output(state: _PlannerState) -> _PlannerState:
        parsed = state["parsed"]
        manifest_fields = parsed.get("manifest", parsed)  # tolerate flat or nested
        entry_plan = parsed.get("entry_plan", {})

        # Anti-hallucination guard for related_urls: keep only URLs that
        # actually appear in the source README.
        scan = state["scan"]
        readme_text = scan.readme_md_content or ""
        candidate_urls = manifest_fields.get("related_urls") or []
        related_urls = [u for u in candidate_urls if isinstance(u, str) and u in readme_text]

        output = PlannerOutput(
            description=manifest_fields.get("description", ""),
            primary_kind=manifest_fields.get("primary_kind", "other"),
            primary_kind_other=manifest_fields.get("primary_kind_other"),
            also=list(manifest_fields.get("also", []) or []),
            status=manifest_fields.get("status", "active"),
            owners=list(manifest_fields.get("owners", []) or []),
            tags=list(manifest_fields.get("tags", []) or []),
            languages=list(manifest_fields.get("languages", []) or []),
            license=manifest_fields.get("license"),
            related_urls=related_urls,
            entry_plan_packages=[
                EntryPlanPackage.from_dict(p) for p in entry_plan.get("packages", []) or []
            ],
            entry_plan_snippets=[
                EntryPlanSnippet.from_dict(s) for s in entry_plan.get("snippets", []) or []
            ],
            entry_plan_references=[
                EntryPlanReference.from_dict(r) for r in entry_plan.get("references", []) or []
            ],
            raw_llm_response=state["raw_llm_response"],
        )
        return {**state, "output": output}

    graph = StateGraph(_PlannerState)
    graph.add_node("call_llm", call_llm)
    graph.add_node("parse_response", parse_response)
    graph.add_node("shape_output", shape_output)
    graph.add_edge(START, "call_llm")
    graph.add_edge("call_llm", "parse_response")
    graph.add_edge("parse_response", "shape_output")
    graph.add_edge("shape_output", END)
    return graph.compile(checkpointer=checkpointer)


# -------- Helpers --------


def _stringify(content: Any) -> str:
    """Flatten LangChain content blocks into a single string."""
    if isinstance(content, list):
        parts: list[str] = []
        for c in content:
            if isinstance(c, dict) and "text" in c:
                parts.append(c["text"])
            else:
                parts.append(str(c))
        return "".join(parts)
    return str(content)


def _parse_llm_json(text: str) -> dict[str, Any]:
    """Parse the LLM's JSON response. Tolerates markdown code fences and
    surrounding text by extracting the first JSON object found.
    """
    text = text.strip()
    # Direct parse first.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Strip markdown code fences if present.
    import re

    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Last resort: find the first balanced JSON object.
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
                candidate = cleaned[start : i + 1]
                return json.loads(candidate)
    raise ValueError(f"LLM response had unbalanced JSON braces: {text[:200]!r}")
