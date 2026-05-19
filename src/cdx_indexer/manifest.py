"""Manifest assembly from deterministic facts.

This module contains ONLY structural fact extractors — file parsers and git
queries whose output is unambiguous. All judgements (primary_kind, status,
description, owners, etc.) are produced by an LLM stage downstream that
consumes these facts as input.

Spec: ../../_docs/index-file-format-0.1.0.md
Plan: ../../_docs/indexer-build-plan.md
"""

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import tomllib
from pathlib import Path

from .types import Counts, LastCommit, Manifest

SCHEMA_VERSION = "0.1.0"

PLACEHOLDER_PRIMARY_KIND = "other"
PLACEHOLDER_PRIMARY_KIND_OTHER = "TBD-pending-llm-classification"


# -------- Public entry point --------

def build_manifest(project_path: Path, workspace_root: Path | None = None) -> Manifest:
    """Build a Manifest for `project_path` from deterministic facts only.

    Fields that require interpretation (description, primary_kind, status, owners,
    tags, builds_on) are filled with placeholders. The LLM workflow replaces them.
    """
    project_path = project_path.resolve()
    if workspace_root is None:
        workspace_root = project_path.parent
    else:
        workspace_root = workspace_root.resolve()

    slug = project_path.name
    rel_path = _relative_to_workspace(project_path, workspace_root)

    return Manifest(
        schema_version=SCHEMA_VERSION,
        project=slug,
        path=rel_path,
        description="",
        languages=[],
        primary_kind=PLACEHOLDER_PRIMARY_KIND,
        primary_kind_other=PLACEHOLDER_PRIMARY_KIND_OTHER,
        also=[],
        license=_detect_license_filename(project_path),
        status="active",
        owners=[],
        tags=[],
        repo_url=_git_remote(project_path),
        default_branch=_git_default_branch(project_path) or "main",
        related_urls=[],
        last_commit=_git_last_commit(project_path),
        last_indexed=_iso_now(),
        counts=Counts(),
    )


# -------- Fact extractors (used by Stage 0 scanner; LLM consumes their output) --------


def pyproject_declares_package(pyproject_path: Path) -> bool:
    """True if a pyproject.toml has a `[project]` table with a `name`.

    Tool-config-only pyproject.toml files (just `[tool.pytest]`, `[tool.coverage]`,
    etc.) do not declare a package and return False.
    """
    try:
        with pyproject_path.open("rb") as f:
            data = tomllib.load(f)
        return bool(data.get("project", {}).get("name"))
    except (OSError, tomllib.TOMLDecodeError):
        return False


def parse_pyproject(pyproject_path: Path) -> dict | None:
    """Return the parsed pyproject.toml dict, or None on parse failure."""
    try:
        with pyproject_path.open("rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return None


def package_json_declares_package(package_json_path: Path) -> bool:
    """True if a package.json declares a `name` field and isn't `private: true`."""
    try:
        with package_json_path.open() as f:
            data = json.load(f)
    except (OSError, ValueError):
        return False
    if not data.get("name"):
        return False
    if data.get("private") is True:
        return False
    return True


def parse_package_json(package_json_path: Path) -> dict | None:
    """Return the parsed package.json dict, or None on failure."""
    try:
        with package_json_path.open() as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def cargo_declares_package(cargo_path: Path) -> bool:
    """True if a Cargo.toml has a `[package]` table with a `name`."""
    try:
        with cargo_path.open("rb") as f:
            data = tomllib.load(f)
        return "package" in data and bool(data["package"].get("name"))
    except (OSError, tomllib.TOMLDecodeError):
        return False


def parse_cargo(cargo_path: Path) -> dict | None:
    """Return the parsed Cargo.toml dict, or None on failure."""
    try:
        with cargo_path.open("rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return None


def parse_go_mod(go_mod_path: Path) -> dict | None:
    """Return parsed go.mod info. Go.mod doesn't have versions; returns minimal dict."""
    try:
        content = go_mod_path.read_text(encoding="utf-8", errors="replace")
        # Extract module name from first line.
        for line in content.splitlines()[:30]:
            line = line.strip()
            if line.startswith("module "):
                module = line[len("module "):].strip()
                return {"module": module}
    except OSError:
        pass
    return {}


# -------- License (filename only — no content parsing) --------


def _detect_license_filename(project_path: Path) -> str | None:
    """Return the filename of a LICENSE / LICENSE.md / LICENSE.txt at the project root,
    or None if absent. Does NOT parse the file's contents.
    """
    for candidate in ("LICENSE", "LICENSE.md", "LICENSE.txt"):
        if (project_path / candidate).is_file():
            return candidate
    return None


# -------- Git metadata --------


def _git_remote(project_path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=project_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        url = result.stdout.strip()
        if not url:
            return None
        # Normalize SSH-style to HTTPS.
        m = re.match(r"git@github\.com:(.+?)(?:\.git)?$", url)
        if m:
            return f"https://github.com/{m.group(1)}"
        return re.sub(r"\.git$", "", url)
    except (OSError, subprocess.SubprocessError):
        return None


def _git_default_branch(project_path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            cwd=project_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().rsplit("/", 1)[-1]
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=project_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            return branch or None
    except (OSError, subprocess.SubprocessError):
        return None
    return None


def _git_last_commit(project_path: Path) -> LastCommit | None:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H %aI"],
            cwd=project_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(" ", 1)
            if len(parts) == 2:
                return LastCommit(sha=parts[0][:12], date=parts[1])
    except (OSError, subprocess.SubprocessError):
        return None
    return None


# -------- File walking --------


# Directories the indexer must never recurse into.
BASELINE_SKIP_DIRS = frozenset({
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    "bower_components",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    "target",
    "out",
    ".next",
    ".eggs",
    ".tox",
    "coverage",
    "htmlcov",
})


def find_files(root: Path, name: str, under: str | None = None) -> list[Path]:
    """Find all files matching `name` under `root`, skipping baseline-ignored dirs."""
    base = root / under if under else root
    if not base.exists():
        return []
    return [p for p in base.rglob(name) if not _path_is_skipped(p, root)]


def _path_is_skipped(p: Path, root: Path) -> bool:
    try:
        rel = p.relative_to(root)
    except ValueError:
        rel = p
    return any(part in BASELINE_SKIP_DIRS for part in rel.parts)


# -------- Utility --------


def _relative_to_workspace(project_path: Path, workspace_root: Path) -> str:
    try:
        return str(project_path.relative_to(workspace_root))
    except ValueError:
        return project_path.name


def _iso_now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
