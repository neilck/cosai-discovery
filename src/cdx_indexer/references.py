"""Stage 2c: Per-file fact gathering and LLM summarization for references.

Consumes entry_plan_references from Stage 1 and produces Reference entries with:
- Deterministic facts: form detection, frontmatter extraction, content hash
- LLM-generated: title, summary, structure_description (for structured form), tags

Granularity: one entry per file the planner selected. Markdown is NOT chunked
into per-heading entries — the importer (Phase 6) owns chunking for embedding.
YAML files containing a list of items (each with an `id` field) decompose into
one entry per item.

Skips:
- PDF files when an adjacent .md exists (markdown wins).
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

import yaml
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from .planner import DEFAULT_CHECKPOINT_DB, EntryPlanReference
from .scan import ProjectScan
from .types import Reference

DEFAULT_MODEL = "claude-haiku-4-5"

# Max file content sent to the LLM. Most docs are well under this.
REFERENCE_CONTENT_MAX_CHARS = 12_000

# Minimum item size to decompose a YAML item into its own entry.
YAML_ITEM_MIN_CHARS = 100


# -------- Prompts --------

_PROMPT_DIR = files("cdx_indexer.prompts")
SYSTEM_PROMPT = _PROMPT_DIR.joinpath("stage2c_system.md").read_text(encoding="utf-8")
_USER_TEMPLATE = _PROMPT_DIR.joinpath("stage2c_user.md.tmpl").read_text(encoding="utf-8")


# -------- Deterministic fact gathering --------


@dataclass
class ReferenceFacts:
    """Deterministic facts extracted from a reference file (or YAML item)."""

    project: str
    slug: str  # used in the id
    path: str
    doc: str
    form: str  # prose | structured | mixed
    frontmatter_tags: list[str]
    content_hash: str
    # For LLM context:
    content_excerpt: str
    # Optional: when this entry is a YAML item, the item's id.
    yaml_item_id: str | None = None


def _detect_form(content: str, path: Path) -> str:
    """Detect form: prose | structured | mixed.

    YAML files are always structured. Markdown is classified by counting
    list/table/code signals — multiple signals → structured; some signals
    mixed with prose → mixed; otherwise prose.
    """
    if path.suffix in (".yaml", ".yml"):
        return "structured"

    has_frontmatter = content.lstrip().startswith("---\n") or content.lstrip().startswith("---\r\n")
    has_bullet = bool(re.search(r"^\s*[-*+]\s", content, re.MULTILINE))
    has_numbered = bool(re.search(r"^\s*\d+\.\s", content, re.MULTILINE))
    has_table = bool(re.search(r"^\|", content, re.MULTILINE))
    has_code = bool(re.search(r"```|^    \S", content, re.MULTILINE))

    structured_signals = [has_frontmatter, has_bullet, has_numbered, has_table]
    n_structured = sum(structured_signals)

    if n_structured >= 2:
        return "structured"
    if n_structured >= 1 or has_code:
        return "mixed"
    return "prose"


def _extract_frontmatter(content: str) -> tuple[dict[str, Any] | None, str]:
    """Extract YAML frontmatter from a markdown document.

    Returns (frontmatter_dict_or_None, content_without_frontmatter).
    """
    stripped = content.lstrip()
    if not (stripped.startswith("---\n") or stripped.startswith("---\r\n")):
        return None, content

    # Find the closing ---.
    lines = content.split("\n")
    # Find the first non-empty line index.
    start_idx = next((i for i, ln in enumerate(lines) if ln.strip()), 0)
    if not lines[start_idx].strip() == "---":
        return None, content
    end_idx = None
    for i in range(start_idx + 1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return None, content

    try:
        fm = yaml.safe_load("\n".join(lines[start_idx + 1 : end_idx])) or {}
    except yaml.YAMLError:
        return None, content

    if not isinstance(fm, dict):
        return None, content

    body = "\n".join(lines[end_idx + 1 :])
    return fm, body


def _frontmatter_tags(frontmatter: dict[str, Any]) -> list[str]:
    """Lift filter-worthy frontmatter values into kebab-case tags."""
    tags: list[str] = []
    for key in ("languages", "language", "categories", "category", "tags", "type", "types"):
        value = frontmatter.get(key)
        if not value:
            continue
        if isinstance(value, list):
            tags.extend(str(v).lower().strip().replace(" ", "-") for v in value)
        else:
            tags.append(str(value).lower().strip().replace(" ", "-"))
    # Dedupe, preserve order.
    seen: set[str] = set()
    out: list[str] = []
    for t in tags:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _path_slug(rel_path: str) -> str:
    """Build a stable slug from a relative path (strip suffix, normalise)."""
    p = Path(rel_path)
    # Drop the suffix; keep directory structure as path segments.
    parts = list(p.with_suffix("").parts)
    return "/".join(parts)


def _trim_content(content: str) -> str:
    """Trim content to a size sensible for an LLM context window."""
    if len(content) <= REFERENCE_CONTENT_MAX_CHARS:
        return content
    return content[:REFERENCE_CONTENT_MAX_CHARS] + f"\n\n[... truncated; full file is {len(content)} chars ...]"


def gather_file_facts(
    plan_entry: EntryPlanReference, scan: ProjectScan, project_path: Path
) -> ReferenceFacts | None:
    """Gather deterministic facts for one markdown/text reference file."""
    file_path = (project_path / plan_entry.path).resolve()
    try:
        raw = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    if len(raw.strip()) < 50:
        return None

    frontmatter, body = _extract_frontmatter(raw)
    fm_tags = _frontmatter_tags(frontmatter) if frontmatter else []

    form = _detect_form(raw, file_path)

    hash_inputs = {
        "path": plan_entry.path,
        "form": form,
        "content_len": len(raw),
        "content_head": raw[:1024],
    }
    content_hash = "sha256:" + hashlib.sha256(
        json.dumps(hash_inputs, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]

    return ReferenceFacts(
        project=scan.project_slug,
        slug=_path_slug(plan_entry.path),
        path=plan_entry.path,
        doc=plan_entry.path,
        form=form,
        frontmatter_tags=fm_tags,
        content_hash=content_hash,
        content_excerpt=_trim_content(raw),
    )


def _find_item_list(data: Any) -> list[dict] | None:
    """Find the list-of-items inside a parsed YAML document.

    Accepts two shapes:
      1. Top-level list of dicts: `[{id: ...}, ...]`
      2. Top-level dict with one or more list-of-dicts-with-id values:
         `{risks: [...]}` or `{categories: [...], controls: [...]}`.
         All such lists are concatenated — every item with an `id` becomes an
         entry. Scalar/empty keys (title, description, etc.) are ignored.

    Returns the merged list of dicts, or None if no decomposable list is found.
    """
    if isinstance(data, list):
        if data and all(isinstance(x, dict) for x in data) and any("id" in x for x in data):
            return data
        return None
    if isinstance(data, dict):
        merged: list[dict] = []
        for v in data.values():
            if isinstance(v, list) and v and all(isinstance(x, dict) for x in v) and any("id" in x for x in v):
                merged.extend(v)
        return merged if merged else None
    return None


def gather_yaml_item_facts(
    plan_entry: EntryPlanReference,
    scan: ProjectScan,
    project_path: Path,
) -> list[ReferenceFacts]:
    """Decompose a YAML file with a list-of-items into one ReferenceFacts per item.

    Accepts two YAML shapes (see `_find_item_list`):
      - Top-level list: `[{id: ...}, ...]`
      - Top-level dict containing the items under a single key: `{risks: [...]}`

    Only items with an `id` field become entries. Returns empty list if no
    decomposable items are found.
    """
    file_path = (project_path / plan_entry.path).resolve()
    try:
        raw = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError:
        return []

    items = _find_item_list(data)
    if items is None:
        return []

    facts_list: list[ReferenceFacts] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        if not item_id:
            continue
        item_yaml = yaml.dump(item, default_flow_style=False, sort_keys=False)
        if len(item_yaml) < YAML_ITEM_MIN_CHARS:
            continue

        slug = f"{_path_slug(plan_entry.path)}/{item_id}"

        hash_inputs = {
            "path": plan_entry.path,
            "item_id": item_id,
            "content_len": len(item_yaml),
            "content_head": item_yaml[:1024],
        }
        content_hash = "sha256:" + hashlib.sha256(
            json.dumps(hash_inputs, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:16]

        facts_list.append(
            ReferenceFacts(
                project=scan.project_slug,
                slug=slug,
                path=plan_entry.path,
                doc=plan_entry.path,
                form="structured",
                frontmatter_tags=[],
                content_hash=content_hash,
                content_excerpt=_trim_content(item_yaml),
                yaml_item_id=str(item_id),
            )
        )

    return facts_list


# -------- LLM summarization --------


class _ReferenceState(TypedDict, total=False):
    facts: ReferenceFacts
    raw_llm_response: str
    parsed: dict[str, Any]
    reference: Reference


def _build_user_prompt(facts: ReferenceFacts) -> str:
    """Render the user prompt for a single reference file (or YAML item)."""
    context = {
        "path": facts.path,
        "doc": facts.doc,
        "form": facts.form,
        "frontmatter_tags": facts.frontmatter_tags,
        "yaml_item_id": facts.yaml_item_id,
        "content": facts.content_excerpt,
    }
    return _USER_TEMPLATE.replace("{reference_facts}", json.dumps(context, indent=2, default=str))


_KIND_BY_PATH_HINTS = (
    # Order matters: most specific first.
    ("rules/", "ruleset"),
    ("skills/", "ruleset"),
    ("agents/", "ruleset"),
    ("whitepaper", "whitepaper"),
    ("charter", "working-group"),
    ("workstream", "working-group"),
)


def _infer_kind(path: str, form: str) -> str:
    """Default kind, refined by path/form hints. LLM may override."""
    p = path.lower()
    for needle, kind in _KIND_BY_PATH_HINTS:
        if needle in p:
            return kind
    if p.endswith(".yaml") or p.endswith(".yml"):
        return "dataset"
    return "docs"


def run_references(
    scan: ProjectScan,
    plan_entries: list[EntryPlanReference],
    project_path: Path,
    model: str | None = None,
    checkpoint_db_path: Path | None = None,
) -> list[Reference]:
    """Run Stage 2c on all references in the entry plan.

    One LLM call per file (or per YAML item). PDFs adjacent to markdown are
    skipped.
    """
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

    references: list[Reference] = []

    try:
        graph = _build_graph(chosen_model, checkpointer)

        for plan_entry in plan_entries:
            file_path = (project_path / plan_entry.path).resolve()

            # Skip PDFs that have an adjacent .md sibling.
            if file_path.suffix.lower() == ".pdf":
                if file_path.with_suffix(".md").exists():
                    continue

            # Gather facts: YAML files first try item decomposition.
            facts_batch: list[ReferenceFacts] = []
            if file_path.suffix.lower() in (".yaml", ".yml"):
                yaml_items = gather_yaml_item_facts(plan_entry, scan, project_path)
                if yaml_items:
                    facts_batch = yaml_items
                else:
                    one = gather_file_facts(plan_entry, scan, project_path)
                    if one:
                        facts_batch = [one]
            else:
                one = gather_file_facts(plan_entry, scan, project_path)
                if one:
                    facts_batch = [one]

            for facts in facts_batch:
                thread_id = f"{scan.project_slug}:ref:{facts.slug}@{facts.content_hash[:8]}"
                config = {"configurable": {"thread_id": thread_id}}

                existing = graph.get_state(config)
                if existing and existing.values and existing.values.get("reference"):
                    references.append(existing.values["reference"])
                    continue

                initial_state: _ReferenceState = {"facts": facts}
                final_state = graph.invoke(initial_state, config=config)
                if "reference" in final_state:
                    references.append(final_state["reference"])
    finally:
        conn.close()

    return references


def _build_graph(model: str, checkpointer: SqliteSaver):
    """Build the per-reference LangGraph state machine."""
    llm = ChatAnthropic(
        model=model,
        temperature=0,
        max_tokens=1024,
        max_retries=5,
        timeout=120.0,
    )

    def call_llm(state: _ReferenceState) -> _ReferenceState:
        facts = state["facts"]
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=_build_user_prompt(facts)),
        ]
        response = llm.invoke(messages)
        text = response.content if isinstance(response.content, str) else str(response.content)
        return {**state, "raw_llm_response": text}

    def parse_response(state: _ReferenceState) -> _ReferenceState:
        text = state["raw_llm_response"]
        parsed = _parse_llm_json(text)
        return {**state, "parsed": parsed}

    def shape_output(state: _ReferenceState) -> _ReferenceState:
        facts = state["facts"]
        parsed = state["parsed"]

        # Merge frontmatter + LLM tags, preserving order, deduped.
        merged_tags: list[str] = []
        seen: set[str] = set()
        for t in list(facts.frontmatter_tags) + list(parsed.get("tags") or []):
            if not t:
                continue
            t_norm = str(t).strip().lower().replace(" ", "-")
            if t_norm and t_norm not in seen:
                seen.add(t_norm)
                merged_tags.append(t_norm)

        # structure_description only meaningful when form != prose.
        sd_raw = parsed.get("structure_description")
        structure_description = sd_raw if (sd_raw and facts.form != "prose") else None

        kind = parsed.get("kind") or _infer_kind(facts.path, facts.form)
        title = parsed.get("title") or Path(facts.path).stem.replace("-", " ").replace("_", " ").title()

        ref = Reference(
            id=f"ref:{facts.project}/{facts.slug}",
            kind=kind,
            title=title,
            doc=facts.doc,
            path=facts.path,
            form=facts.form,
            summary=parsed.get("summary", "") or "",
            tags=merged_tags,
            content_hash=facts.content_hash,
            structure_description=structure_description,
        )
        return {**state, "reference": ref}

    graph = StateGraph(_ReferenceState)
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
    end_pos = -1
    for i in range(start, len(cleaned)):
        if cleaned[i] == "{":
            depth += 1
        elif cleaned[i] == "}":
            depth -= 1
            if depth == 0:
                end_pos = i + 1
                break
    if end_pos == -1:
        raise ValueError(f"LLM response had unbalanced braces: {text[:200]!r}")

    json_str = cleaned[start:end_pos]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Last-ditch: escape stray newlines inside quoted strings.
        def escape_newlines(match: re.Match) -> str:
            s = match.group(1)
            return '"' + s.replace("\n", "\\n").replace("\r", "\\r") + '"'

        repaired = re.sub(r'"((?:[^"\\]|\\.)*?)"', escape_newlines, json_str, flags=re.DOTALL)
        return json.loads(repaired)
