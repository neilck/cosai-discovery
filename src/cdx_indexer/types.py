"""Dataclasses for index entities.

Mirrors index-file-format-0.1.0.md. Each dataclass serializes to the entry shape
defined in the spec.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Package:
    """Package entry in packages.jsonl."""

    id: str
    category: str = "package"
    kind: str = "library"
    name: str = ""
    language: str = ""
    ecosystem: str = ""
    version: str | None = None
    entrypoints: list[str] = field(default_factory=list)
    public_api: list[str] = field(default_factory=list)
    path: str = ""
    install: str = ""
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    content_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "category": self.category,
            "kind": self.kind,
            "name": self.name,
            "language": self.language,
            "ecosystem": self.ecosystem,
            "version": self.version,
            "entrypoints": list(self.entrypoints),
            "public_api": list(self.public_api),
            "path": self.path,
            "install": self.install,
            "summary": self.summary,
            "tags": list(self.tags),
            "content_hash": self.content_hash,
        }
        return out


@dataclass
class LastCommit:
    sha: str
    date: str  # ISO-8601

    def to_dict(self) -> dict[str, Any]:
        return {"sha": self.sha, "date": self.date}


@dataclass
class Counts:
    packages: int = 0
    snippets: int = 0
    references: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "packages": self.packages,
            "snippets": self.snippets,
            "references": self.references,
        }


@dataclass
class Manifest:
    """Project manifest. Serializes to manifest.json."""

    schema_version: str
    project: str
    path: str
    description: str
    languages: list[str]
    primary_kind: str
    also: list[str]
    status: str
    owners: list[str]
    tags: list[str]
    default_branch: str
    last_indexed: str  # ISO-8601
    counts: Counts

    # Optional fields (omit when absent rather than emit null).
    primary_kind_other: str | None = None  # required when primary_kind == "other"
    license: str | None = None
    repo_url: str | None = None
    last_commit: LastCommit | None = None
    related_urls: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema_version": self.schema_version,
            "project": self.project,
            "path": self.path,
            "description": self.description,
            "languages": self.languages,
            "primary_kind": self.primary_kind,
            "also": self.also,
            "status": self.status,
            "owners": self.owners,
            "tags": self.tags,
            "default_branch": self.default_branch,
            "related_urls": list(self.related_urls),
            "last_indexed": self.last_indexed,
            "counts": self.counts.to_dict(),
        }
        # Optional fields: include only when present.
        if self.primary_kind_other is not None:
            out["primary_kind_other"] = self.primary_kind_other
        if self.license is not None:
            out["license"] = self.license
        if self.repo_url is not None:
            out["repo_url"] = self.repo_url
        if self.last_commit is not None:
            out["last_commit"] = self.last_commit.to_dict()
        return _reorder_manifest(out)


def _reorder_manifest(d: dict[str, Any]) -> dict[str, Any]:
    """Re-emit manifest fields in the order shown in the spec."""
    spec_order = [
        "schema_version",
        "project",
        "path",
        "description",
        "languages",
        "primary_kind",
        "primary_kind_other",
        "also",
        "license",
        "status",
        "owners",
        "tags",
        "repo_url",
        "default_branch",
        "related_urls",
        "last_commit",
        "last_indexed",
        "counts",
    ]
    return {k: d[k] for k in spec_order if k in d}
