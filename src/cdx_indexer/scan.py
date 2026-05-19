"""Stage 0: deterministic project scan.

Walks the project filesystem and parses recognised manifest files, producing a
ProjectScan dataclass of structural facts. No interpretation — that's the LLM's
job in Stage 1.

The output is designed to be JSON-serialisable and small enough to fit in an
LLM context window.
"""

from __future__ import annotations

import datetime as dt
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import manifest as m

# Files at the project root that the LLM should see in full text.
ROOT_DOC_FILES = (
    "README.md",
    "ROADMAP.md",
    "CHARTER.md",
    "ONBOARDING.md",
    "GOVERNANCE.md",
    "CONTRIBUTING.md",
    "MAINTAINERS.md",
    "WORKSTREAMS.md",
    "AI-USAGE-GUIDELINES.md",
)

# Files at the project root that are typically just legal text or generic
# templates. The LLM doesn't need their content — only the filename matters.
ROOT_DOC_BOILERPLATE = (
    "LICENSE",
    "LICENSE.md",
    "LICENSE.txt",
    "CODE-OF-CONDUCT.md",
    "CODE_OF_CONDUCT.md",
    "IPR-STATEMENT.md",
)

# Cap on README content sent to the LLM. Most CoSAI READMEs are <15KB; truncate
# longer ones from the end since the leading content is usually most informative.
README_MAX_CHARS = 20_000

# Cap on the file tree size sent to the LLM. Beyond this, we summarise.
FILE_TREE_MAX_ENTRIES = 1000


@dataclass
class ParsedPyProject:
    path: str  # relative to project root
    declares_package: bool
    name: str | None = None
    version: str | None = None
    description: str | None = None
    scripts: dict[str, str] = field(default_factory=dict)
    has_tool_table: bool = False
    requires_python: str | None = None
    license_field: Any = None  # may be str or dict per PEP 621

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "declares_package": self.declares_package,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "scripts": self.scripts,
            "has_tool_table": self.has_tool_table,
            "requires_python": self.requires_python,
            "license_field": self.license_field,
        }


@dataclass
class ParsedPackageJson:
    path: str
    declares_package: bool
    name: str | None = None
    version: str | None = None
    description: str | None = None
    private: bool = False
    has_bin: bool = False
    bin: dict[str, str] | str | None = None
    main: str | None = None
    license: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "declares_package": self.declares_package,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "private": self.private,
            "has_bin": self.has_bin,
            "bin": self.bin,
            "main": self.main,
            "license": self.license,
        }


@dataclass
class ParsedGoMod:
    path: str
    module: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "module": self.module}


@dataclass
class ParsedCargoToml:
    path: str
    declares_package: bool
    name: str | None = None
    version: str | None = None
    description: str | None = None
    is_workspace: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "declares_package": self.declares_package,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "is_workspace": self.is_workspace,
        }


@dataclass
class ParsedClaudePlugin:
    path: str
    name: str | None = None
    version: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "version": self.version,
            "description": self.description,
        }


@dataclass
class ParsedDevcontainerFeature:
    path: str
    id: str | None = None
    name: str | None = None
    version: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
        }


@dataclass
class ProjectScan:
    """Structural facts about a project, suitable for handing to an LLM."""

    project_slug: str
    project_path: str  # absolute
    workspace_root: str  # absolute
    workspace_project_slugs: list[str]

    # File tree (paths relative to project root).
    file_tree: list[str]
    file_tree_truncated: bool
    file_tree_full_count: int

    # Manifests.
    pyproject_tomls: list[ParsedPyProject]
    package_jsons: list[ParsedPackageJson]
    go_mods: list[ParsedGoMod]
    cargo_tomls: list[ParsedCargoToml]
    claude_plugins: list[ParsedClaudePlugin]
    devcontainer_features: list[ParsedDevcontainerFeature]

    # Root-level documents the LLM should reason over.
    readme_md_content: str | None
    other_root_docs: dict[str, str]
    root_doc_boilerplate_present: list[str]  # filenames only

    # License signal (filename only — no content).
    license_filename: str | None

    # Git metadata.
    repo_url: str | None
    default_branch: str
    last_commit_sha: str | None
    last_commit_date: str | None

    # When the scan ran.
    scanned_at: str  # ISO-8601

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_slug": self.project_slug,
            "project_path": self.project_path,
            "workspace_root": self.workspace_root,
            "workspace_project_slugs": self.workspace_project_slugs,
            "file_tree": self.file_tree,
            "file_tree_truncated": self.file_tree_truncated,
            "file_tree_full_count": self.file_tree_full_count,
            "manifests": {
                "pyproject_toml": [p.to_dict() for p in self.pyproject_tomls],
                "package_json": [p.to_dict() for p in self.package_jsons],
                "go_mod": [p.to_dict() for p in self.go_mods],
                "cargo_toml": [p.to_dict() for p in self.cargo_tomls],
                "claude_plugin": [p.to_dict() for p in self.claude_plugins],
                "devcontainer_feature": [p.to_dict() for p in self.devcontainer_features],
            },
            "readme_md_content": self.readme_md_content,
            "other_root_docs": self.other_root_docs,
            "root_doc_boilerplate_present": self.root_doc_boilerplate_present,
            "license_filename": self.license_filename,
            "repo_url": self.repo_url,
            "default_branch": self.default_branch,
            "last_commit_sha": self.last_commit_sha,
            "last_commit_date": self.last_commit_date,
            "scanned_at": self.scanned_at,
        }


# -------- Public entry point --------


def scan_project(
    project_path: Path,
    workspace_root: Path | None = None,
) -> ProjectScan:
    """Produce a ProjectScan of structural facts."""
    project_path = project_path.resolve()
    if workspace_root is None:
        workspace_root = project_path.parent
    else:
        workspace_root = workspace_root.resolve()

    workspace_peers = _list_workspace_peers(workspace_root, project_path)

    file_tree, truncated, full_count = _collect_file_tree(project_path)

    pyproject_tomls = [_parse_pyproject(p, project_path) for p in m.find_files(project_path, "pyproject.toml")]
    package_jsons = [_parse_package_json(p, project_path) for p in m.find_files(project_path, "package.json")]
    go_mods = [_parse_go_mod(p, project_path) for p in m.find_files(project_path, "go.mod")]
    cargo_tomls = [_parse_cargo(p, project_path) for p in m.find_files(project_path, "Cargo.toml")]
    claude_plugins = [_parse_claude_plugin(p, project_path) for p in m.find_files(project_path, "plugin.json", under=".claude-plugin")]
    devcontainer_features = [_parse_devcontainer_feature(p, project_path) for p in m.find_files(project_path, "devcontainer-feature.json")]

    readme_md = _read_text(project_path / "README.md", limit=README_MAX_CHARS)
    other_docs = _collect_other_root_docs(project_path)
    boilerplate_present = [name for name in ROOT_DOC_BOILERPLATE if (project_path / name).is_file()]

    repo_url, default_branch, sha, sha_date = _git_metadata(project_path)

    return ProjectScan(
        project_slug=project_path.name,
        project_path=str(project_path),
        workspace_root=str(workspace_root),
        workspace_project_slugs=workspace_peers,
        file_tree=file_tree,
        file_tree_truncated=truncated,
        file_tree_full_count=full_count,
        pyproject_tomls=pyproject_tomls,
        package_jsons=package_jsons,
        go_mods=go_mods,
        cargo_tomls=cargo_tomls,
        claude_plugins=claude_plugins,
        devcontainer_features=devcontainer_features,
        readme_md_content=readme_md,
        other_root_docs=other_docs,
        root_doc_boilerplate_present=boilerplate_present,
        license_filename=_license_filename(project_path),
        repo_url=repo_url,
        default_branch=default_branch or "main",
        last_commit_sha=sha,
        last_commit_date=sha_date,
        scanned_at=dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
    )


# -------- Parsers --------


def _parse_pyproject(path: Path, root: Path) -> ParsedPyProject:
    rel = str(path.relative_to(root))
    data = m.parse_pyproject(path) or {}
    project_table = data.get("project", {})
    scripts = project_table.get("scripts") or {}
    if not isinstance(scripts, dict):
        scripts = {}
    return ParsedPyProject(
        path=rel,
        declares_package=bool(project_table.get("name")),
        name=project_table.get("name"),
        version=project_table.get("version"),
        description=project_table.get("description"),
        scripts={str(k): str(v) for k, v in scripts.items()},
        has_tool_table=bool(data.get("tool")),
        requires_python=project_table.get("requires-python"),
        license_field=project_table.get("license"),
    )


def _parse_package_json(path: Path, root: Path) -> ParsedPackageJson:
    rel = str(path.relative_to(root))
    data = m.parse_package_json(path) or {}
    name = data.get("name")
    private = bool(data.get("private"))
    bin_value = data.get("bin")
    return ParsedPackageJson(
        path=rel,
        declares_package=bool(name) and not private,
        name=name,
        version=data.get("version"),
        description=data.get("description"),
        private=private,
        has_bin=bool(bin_value),
        bin=bin_value,
        main=data.get("main"),
        license=data.get("license"),
    )


def _parse_go_mod(path: Path, root: Path) -> ParsedGoMod:
    rel = str(path.relative_to(root))
    module: str | None = None
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[:30]:
            line = line.strip()
            if line.startswith("module "):
                module = line[len("module ") :].strip()
                break
    except OSError:
        pass
    return ParsedGoMod(path=rel, module=module)


def _parse_cargo(path: Path, root: Path) -> ParsedCargoToml:
    rel = str(path.relative_to(root))
    data = m.parse_cargo(path) or {}
    pkg = data.get("package") if isinstance(data, dict) else None
    return ParsedCargoToml(
        path=rel,
        declares_package=bool(pkg and pkg.get("name")),
        name=pkg.get("name") if pkg else None,
        version=pkg.get("version") if pkg else None,
        description=pkg.get("description") if pkg else None,
        is_workspace=bool(data.get("workspace")),
    )


def _parse_claude_plugin(path: Path, root: Path) -> ParsedClaudePlugin:
    rel = str(path.relative_to(root))
    import json

    data: dict = {}
    try:
        with path.open() as f:
            data = json.load(f) or {}
    except (OSError, ValueError):
        pass
    return ParsedClaudePlugin(
        path=rel,
        name=data.get("name"),
        version=data.get("version"),
        description=data.get("description"),
    )


def _parse_devcontainer_feature(path: Path, root: Path) -> ParsedDevcontainerFeature:
    rel = str(path.relative_to(root))
    import json

    data: dict = {}
    try:
        with path.open() as f:
            data = json.load(f) or {}
    except (OSError, ValueError):
        pass
    return ParsedDevcontainerFeature(
        path=rel,
        id=data.get("id"),
        name=data.get("name"),
        version=data.get("version"),
        description=data.get("description"),
    )


# -------- File tree + content --------


def _collect_file_tree(project_path: Path) -> tuple[list[str], bool, int]:
    """Walk the project, returning relative file paths.

    Paths are sorted for stable output. Returns (tree, truncated, full_count).
    """
    paths: list[str] = []
    for p in project_path.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(project_path)
        if any(part in m.BASELINE_SKIP_DIRS for part in rel.parts):
            continue
        paths.append(str(rel))
    paths.sort()
    full_count = len(paths)
    if full_count > FILE_TREE_MAX_ENTRIES:
        return paths[:FILE_TREE_MAX_ENTRIES], True, full_count
    return paths, False, full_count


def _read_text(path: Path, limit: int) -> str | None:
    if not path.is_file():
        return None
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if len(content) > limit:
        # Truncate but flag explicitly so the LLM doesn't think the doc ended naturally.
        return content[:limit] + f"\n\n[... truncated; full document is {len(content)} chars ...]\n"
    return content


def _collect_other_root_docs(project_path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for name in ROOT_DOC_FILES:
        if name == "README.md":
            continue  # handled separately
        path = project_path / name
        text = _read_text(path, limit=README_MAX_CHARS)
        if text is not None:
            out[name] = text
    return out


def _license_filename(project_path: Path) -> str | None:
    for candidate in ("LICENSE", "LICENSE.md", "LICENSE.txt"):
        if (project_path / candidate).is_file():
            return candidate
    return None


# -------- Workspace peers --------


def _list_workspace_peers(workspace_root: Path, project_path: Path) -> list[str]:
    """List sibling project slugs in the workspace (excluding the current project)."""
    peers: list[str] = []
    if not workspace_root.is_dir():
        return peers
    for child in sorted(workspace_root.iterdir()):
        if not child.is_dir():
            continue
        if child == project_path:
            continue
        if child.name.startswith("."):
            continue
        peers.append(child.name)
    return peers


# -------- Git --------


def _git_metadata(project_path: Path) -> tuple[str | None, str | None, str | None, str | None]:
    """Return (repo_url, default_branch, last_commit_sha, last_commit_date)."""
    repo_url = _git_remote(project_path)
    default_branch = _git_default_branch(project_path)
    sha, sha_date = _git_last_commit_parts(project_path)
    return repo_url, default_branch, sha, sha_date


def _git_remote(project_path: Path) -> str | None:
    import re

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
        ssh = re.match(r"git@github\.com:(.+?)(?:\.git)?$", url)
        if ssh:
            return f"https://github.com/{ssh.group(1)}"
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


def _git_last_commit_parts(project_path: Path) -> tuple[str | None, str | None]:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H %aI"],
            cwd=project_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None, None
        parts = result.stdout.strip().split(" ", 1)
        if len(parts) != 2:
            return None, None
        return parts[0][:12], parts[1]
    except (OSError, subprocess.SubprocessError):
        return None, None
