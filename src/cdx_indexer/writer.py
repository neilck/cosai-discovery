"""Writers for .cosai-index/ files, with sidecar resolution.

Spec: ../../_docs/index-file-format-0.1.0.md
Plan: ../../_docs/indexer-build-plan.md
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any

from .types import Manifest, Package, Snippet


@dataclass
class ResolvedOutput:
    """The chosen output directory plus context for reporting."""

    output_dir: Path
    used_sidecar: bool
    reason: str  # human-readable explanation for the chosen location


def resolve_output_dir(
    project_path: Path,
    output: Path | None,
    sidecar: bool,
    workspace_root: Path | None,
) -> ResolvedOutput:
    """Resolve where index files should be written.

    Order:
    1. If `output` is supplied, use it directly (no .cosai-index/ subdir added).
    2. If `sidecar=True`, use the sidecar location.
    3. Try `project_path/.cosai-index/`; if not writable, fall back to sidecar.
    """
    project_path = project_path.resolve()

    if output is not None:
        output = output.resolve()
        output.mkdir(parents=True, exist_ok=True)
        return ResolvedOutput(
            output_dir=output, used_sidecar=False, reason="explicit --output"
        )

    if not sidecar:
        in_repo = project_path / ".cosai-index"
        if _can_write_to(in_repo):
            in_repo.mkdir(parents=True, exist_ok=True)
            return ResolvedOutput(
                output_dir=in_repo, used_sidecar=False, reason="in-repo .cosai-index/"
            )
        # Fall through to sidecar resolution.

    # Sidecar path.
    root = workspace_root.resolve() if workspace_root else project_path.parent
    slug = project_path.name
    sidecar_dir = root / ".cosai-indexes" / slug
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    why = "forced sidecar (--sidecar)" if sidecar else "project not writable; sidecar fallback"
    return ResolvedOutput(output_dir=sidecar_dir, used_sidecar=True, reason=why)


def _can_write_to(target_dir: Path) -> bool:
    """Best-effort: try to create the directory and a tempfile inside it."""
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    try:
        # Make sure we can actually write a file there.
        with tempfile.NamedTemporaryFile(
            mode="w", dir=target_dir, prefix=".cdx-probe-", delete=True
        ):
            pass
        return True
    except OSError:
        return False


def write_manifest(output_dir: Path, manifest: Manifest) -> Path:
    """Atomically write manifest.json into output_dir. Returns the path."""
    target = output_dir / "manifest.json"
    _write_json_atomic(target, manifest.to_dict())
    return target


def write_empty_jsonl(output_dir: Path, name: str) -> Path:
    """Write a zero-length JSONL file (overwriting any existing content)."""
    target = output_dir / name
    target.write_bytes(b"")
    return target


def write_packages_jsonl(output_dir: Path, packages: list[Package]) -> Path:
    """Atomically write packages.jsonl from a list of Package entries."""
    return _write_jsonl_atomic(output_dir / "packages.jsonl", [p.to_dict() for p in packages])


def write_snippets_jsonl(output_dir: Path, snippets: list[Snippet]) -> Path:
    """Atomically write snippets.jsonl from a list of Snippet entries."""
    return _write_jsonl_atomic(output_dir / "snippets.jsonl", [s.to_dict() for s in snippets])


def _write_jsonl_atomic(target: Path, rows: list[dict]) -> Path:
    """Atomically write a list of JSON-encodable dicts as JSONL."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=target.name + ".",
        suffix=".tmp",
        dir=target.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, target)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    return target


def write_stage1_state(output_dir: Path, scan: Any, plan: Any, thread_id: str) -> Path:
    """Write the Stage 1 state to `_stage1.json` for human inspection and audit.

    Contains the deterministic ProjectScan input, the structured PlannerOutput,
    the raw LLM response, and the LangGraph thread_id used for checkpoint reuse.
    The leading underscore in the filename flags this as indexer-internal state;
    the MCP server should ignore it.
    """
    target = output_dir / "_stage1.json"
    payload = {
        "thread_id": thread_id,
        "scan": _to_jsonable(scan),
        "plan": _to_jsonable(plan),
    }
    _write_json_atomic(target, payload)
    return target


def _to_jsonable(value: Any) -> Any:
    """Convert dataclasses / nested structures into JSON-friendly primitives."""
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    return value


def _write_json_atomic(target: Path, data: dict) -> None:
    """Write JSON via tmp + rename, so partial writes never appear on disk."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=target.name + ".",
        suffix=".tmp",
        dir=target.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, target)
    except Exception:
        # Best-effort cleanup.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
