"""Stage 2a: Per-package fact gathering and LLM summarization.

Consumes the entry_plan_packages from Stage 1 and produces full Package entries
with deterministic facts (version, entrypoints, install command) plus LLM-generated
summary, public_api, and tags.

Implemented as a LangGraph fan-out: one graph node per package, all sharing a
SQLite checkpoint database for resume/cache.
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

from . import manifest as m
from .planner import DEFAULT_CHECKPOINT_DB, EntryPlanPackage
from .scan import ProjectScan
from .types import Package

DEFAULT_MODEL = "claude-haiku-4-5"

# -------- Prompts --------

_PROMPT_DIR = files("cdx_indexer.prompts")
SYSTEM_PROMPT = _PROMPT_DIR.joinpath("stage2a_system.md").read_text(encoding="utf-8")
_USER_TEMPLATE = _PROMPT_DIR.joinpath("stage2a_user.md.tmpl").read_text(encoding="utf-8")


# -------- Deterministic fact gathering --------


@dataclass
class PackageFacts:
    """Deterministic facts extracted from a manifest + scan."""

    project: str
    name: str
    manifest_path: str
    language: str
    ecosystem: str
    version: str | None
    entrypoints: list[str]
    install: str
    path: str
    content_hash: str
    # For LLM context:
    readme_excerpt: str  # First 2–3 sentences of README
    ecosystem_hint: str  # "Installable X from PyPI"


def gather_package_facts(plan_entry: EntryPlanPackage, scan: ProjectScan, project_path: Path) -> PackageFacts:
    """Extract deterministic facts from a plan entry and the project's manifests.

    Returns facts needed to populate a Package entry: version, entrypoints,
    install command, path, and content_hash.
    """
    project_path = project_path.resolve()
    manifest_path = project_path / plan_entry.manifest_path
    manifest_dir = manifest_path.parent
    rel_manifest_dir = str(manifest_dir.relative_to(project_path))

    # Parse the manifest to get version and entrypoints.
    version, entrypoints = _extract_manifest_facts(manifest_path, plan_entry.ecosystem)

    # Compose install command by ecosystem.
    install = _install_command(plan_entry.name, plan_entry.ecosystem)

    # Content hash: SHA-256 of the inputs that produced summary.
    # Used to skip unchanged packages on re-run.
    hash_inputs = {
        "manifest_path": plan_entry.manifest_path,
        "name": plan_entry.name,
        "language": plan_entry.language,
        "ecosystem": plan_entry.ecosystem,
        "version": version,
        "entrypoints": entrypoints,
    }
    content_hash = "sha256:" + hashlib.sha256(
        json.dumps(hash_inputs, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]

    # Extract README excerpt for LLM context (first 2–3 sentences).
    readme_excerpt = _extract_readme_excerpt(scan.readme_md_content or "")

    # Ecosystem hint for the LLM.
    ecosystem_hints = {
        "pypi": "Installable from PyPI via pip.",
        "npm": "Installable from npm.",
        "go": "Go module available on proxy.golang.org.",
        "cargo": "Published to crates.io.",
        "source": "Installable from source.",
        "vendor": "Meant to be copied into consumer's tree.",
        "claude-plugin": "Claude Code plugin.",
        "mcp-server": "Runnable MCP server.",
        "devcontainer-feature": "VS Code devcontainer feature.",
        "none": "Not meant for external consumption.",
    }
    ecosystem_hint = ecosystem_hints.get(plan_entry.ecosystem, "")

    return PackageFacts(
        project=scan.project_slug,
        name=plan_entry.name,
        manifest_path=plan_entry.manifest_path,
        language=plan_entry.language,
        ecosystem=plan_entry.ecosystem,
        version=version,
        entrypoints=entrypoints,
        install=install,
        path=rel_manifest_dir,
        content_hash=content_hash,
        readme_excerpt=readme_excerpt,
        ecosystem_hint=ecosystem_hint,
    )


def _extract_manifest_facts(manifest_path: Path, ecosystem: str) -> tuple[str | None, list[str]]:
    """Extract version and entrypoints from a manifest file."""
    version = None
    entrypoints = []

    if manifest_path.name == "pyproject.toml":
        data = m.parse_pyproject(manifest_path) or {}
        project = data.get("project", {})
        version = project.get("version")
        scripts = project.get("scripts") or {}
        entrypoints = [str(k) for k in scripts.keys()] if isinstance(scripts, dict) else []

    elif manifest_path.name == "package.json":
        data = m.parse_package_json(manifest_path) or {}
        version = data.get("version")
        # Only `bin` declares CLI entrypoints. `main` is the library import
        # path, not an entrypoint — including it here would mislead the kind
        # inference (an SDK with only `main` would look like a CLI).
        bin_field = data.get("bin")
        if isinstance(bin_field, dict):
            entrypoints = [str(k) for k in bin_field.keys()]
        elif isinstance(bin_field, str):
            # bin: "path/to/cli" → one entrypoint named after the package.
            entrypoints = [data.get("name", "command")] if data.get("name") else []

    elif manifest_path.name == "go.mod":
        # Go modules don't declare versions in go.mod; version comes from git tags.
        version = None
        entrypoints = []

    elif manifest_path.name == "Cargo.toml":
        data = m.parse_cargo(manifest_path) or {}
        package = data.get("package", {})
        version = package.get("version")
        # Check for [[bin]] sections.
        bins = data.get("bin", [])
        if isinstance(bins, list):
            entrypoints = [str(b.get("name", "")) for b in bins if b.get("name")]

    elif manifest_path.name == "plugin.json":
        import json as json_module
        try:
            data = json_module.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        version = data.get("version")
        # Claude plugins don't have traditional entrypoints.
        entrypoints = []

    elif manifest_path.name == "devcontainer-feature.json":
        import json as json_module
        try:
            data = json_module.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        version = data.get("version")
        entrypoints = []

    return version, entrypoints


def _install_command(name: str, ecosystem: str) -> str:
    """Produce a copy-pasteable install command by ecosystem."""
    if ecosystem == "pypi":
        return f"pip install {name}"
    elif ecosystem == "npm":
        return f"npm install {name}"
    elif ecosystem == "go":
        return f"go get {name}"
    elif ecosystem == "cargo":
        return f"cargo add {name}"
    elif ecosystem == "source":
        return "pip install -e . (or equivalent)"
    elif ecosystem == "vendor":
        return f"Copy {name} into your project"
    elif ecosystem == "claude-plugin":
        return f"/plugin install {name} (or via marketplace)"
    elif ecosystem == "mcp-server":
        return f"Configure in mcpServers block"
    elif ecosystem == "devcontainer-feature":
        return f"Add to devcontainer.json features"
    else:
        return ""


def _infer_package_kind(ecosystem: str, entrypoints: list[str]) -> str:
    """Infer the package kind (library, cli, service, etc.) from ecosystem and entrypoints.

    Returns one of the primary_kind enum values.
    """
    # Explicit ecosystem markers.
    if ecosystem == "claude-plugin":
        return "claude-plugin"
    elif ecosystem == "mcp-server":
        return "service"
    elif ecosystem == "devcontainer-feature":
        return "devcontainer-feature"

    # Infer from entrypoints.
    if entrypoints:
        # CLI packages have entrypoints (Python scripts or npm bin commands).
        return "cli"

    # Default: library.
    return "library"


def _extract_readme_excerpt(readme: str) -> str:
    """Extract the first 2–3 sentences from README for LLM context."""
    if not readme:
        return ""
    lines = readme.split("\n")
    # Skip leading headers and boilerplate.
    for line in lines:
        line = line.strip()
        if line.startswith("#"):
            continue
        if line and not line.startswith("!["):  # Skip image alt-text-heavy lines
            # Extract first ~200 chars as excerpt.
            excerpt = (line + " " + " ".join(l.strip() for l in lines[lines.index(line) + 1 : lines.index(line) + 3] if l.strip())).strip()
            return excerpt[:200]
    return ""


# -------- LLM summarization --------


class _PackageState(TypedDict, total=False):
    facts: PackageFacts
    raw_llm_response: str
    parsed: dict[str, Any]
    package: Package


def _build_user_prompt(facts: PackageFacts) -> str:
    """Render the user prompt for a single package."""
    context = {
        "name": facts.name,
        "language": facts.language,
        "ecosystem": facts.ecosystem,
        "version": facts.version,
        "entrypoints": facts.entrypoints,
        "install": facts.install,
        "readme_excerpt": facts.readme_excerpt,
        "ecosystem_hint": facts.ecosystem_hint,
    }
    return _USER_TEMPLATE.replace("{package_facts}", json.dumps(context, indent=2, default=str))


def run_packages(
    scan: ProjectScan,
    plan_entries: list[EntryPlanPackage],
    project_path: Path,
    model: str | None = None,
    checkpoint_db_path: Path | None = None,
) -> list[Package]:
    """Run Stage 2a on all packages in the entry plan.

    Returns a list of Package entries with summary, public_api, and tags filled in
    by the LLM. Each package runs in its own LangGraph thread with checkpoint reuse.
    """
    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY not set. Add to .env or export before running.")

    chosen_model = model or os.environ.get("CDX_MODEL", DEFAULT_MODEL)
    db_path = checkpoint_db_path or Path(DEFAULT_CHECKPOINT_DB).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    project_path = project_path.resolve()
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    packages: list[Package] = []

    try:
        for plan_entry in plan_entries:
            # Gather deterministic facts.
            facts = gather_package_facts(plan_entry, scan, project_path)

            # Thread ID: one per package, keyed on name + content hash.
            thread_id = f"{scan.project_slug}:pkg:{plan_entry.name}@{facts.content_hash[:8]}"

            # Build and invoke the graph.
            graph = _build_graph(chosen_model, checkpointer)
            config = {"configurable": {"thread_id": thread_id}}

            # Check for prior completion (cached).
            existing = graph.get_state(config)
            if existing and existing.values and existing.values.get("package"):
                packages.append(existing.values["package"])
                continue

            # Run the workflow.
            initial_state: _PackageState = {"facts": facts}
            final_state = graph.invoke(initial_state, config=config)
            if "package" in final_state:
                packages.append(final_state["package"])

    finally:
        conn.close()

    return packages


def _build_graph(model: str, checkpointer: SqliteSaver):
    """Build the per-package LangGraph state machine."""
    llm = ChatAnthropic(
        model=model,
        temperature=0,
        max_tokens=1024,
        max_retries=5,
        timeout=120.0,
    )

    def call_llm(state: _PackageState) -> _PackageState:
        facts = state["facts"]
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=_build_user_prompt(facts)),
        ]
        response = llm.invoke(messages)
        text = response.content if isinstance(response.content, str) else str(response.content)
        return {**state, "raw_llm_response": text}

    def parse_response(state: _PackageState) -> _PackageState:
        text = state["raw_llm_response"]
        parsed = _parse_llm_json(text)
        return {**state, "parsed": parsed}

    def shape_output(state: _PackageState) -> _PackageState:
        facts = state["facts"]
        parsed = state["parsed"]

        pkg = Package(
            id=f"pkg:{facts.project}/{facts.name}",
            category="package",
            kind=_infer_package_kind(facts.ecosystem, facts.entrypoints),
            name=facts.name,
            language=facts.language,
            ecosystem=facts.ecosystem,
            version=facts.version,
            entrypoints=facts.entrypoints,
            path=facts.path,
            install=facts.install,
            content_hash=facts.content_hash,
            summary=parsed.get("summary", ""),
            public_api=parsed.get("public_api", []) or [],
            tags=parsed.get("tags", []) or [],
        )
        return {**state, "package": pkg}

    graph = StateGraph(_PackageState)
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

    import re
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Last resort: find first balanced JSON object.
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
