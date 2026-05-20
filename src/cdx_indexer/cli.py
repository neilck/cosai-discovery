"""CLI entry point for cdx-index.

Stage 0 (deterministic scan) → Stage 1 (LLM classification + entry plan)
→ writer. Subsequent stages (per-entry processing, embedding) come later.
"""

from __future__ import annotations

from pathlib import Path

import click

from . import __version__
from .embed import embed_index_files
from .manifest import build_manifest
from .packages import run_packages
from .planner import PlannerOutput, run_planner
from .references import run_references
from .scan import scan_project
from .snippets import run_snippets
from .types import Manifest
from .vectorstore import VectorStore
from .writer import (
    resolve_output_dir,
    write_manifest,
    write_packages_jsonl,
    write_references_jsonl,
    write_snippets_jsonl,
    write_stage1_state,
)


@click.group()
@click.version_option(__version__)
def cli():
    """COSAI Discovery indexer."""


@cli.command()
@click.argument(
    "project_path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=False,
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(file_okay=False, path_type=Path),
    help=(
        "Where to write index files. Defaults to PROJECT_PATH/.cosai-index/ "
        "if writable, else <workspace-root>/.cosai-indexes/<slug>/."
    ),
)
@click.option(
    "--sidecar",
    is_flag=True,
    help="Force sidecar location even when project is writable.",
)
@click.option(
    "--workspace-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Override inferred workspace root. Default: dirname(PROJECT_PATH).",
)
@click.option(
    "--force",
    is_flag=True,
    help=(
        "Ignore any existing Stage 1 checkpoint and re-run the LLM call. "
        "Use when the prompt has changed or the cached output is stale."
    ),
)
@click.option(
    "--model",
    type=str,
    default=None,
    help="Override the model used for Stage 1. Default: claude-haiku-4-5 (or $CDX_MODEL).",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show the raw LLM response for debugging.",
)
@click.option(
    "--embed",
    "do_embed",
    is_flag=True,
    help=(
        "After writing files, embed entries via Voyage and upsert vectors to the "
        "workspace vector store. Requires VOYAGE_API_KEY."
    ),
)
@click.option(
    "--db-path",
    type=click.Path(file_okay=True, dir_okay=False, path_type=Path),
    default=None,
    help=(
        "Override the vector-store path. Default: "
        "<workspace-root>/.cosai-indexes/.data/index.db"
    ),
)
def build(
    project_path: Path | None,
    output_path: Path | None,
    sidecar: bool,
    workspace_root: Path | None,
    force: bool,
    model: str | None,
    verbose: bool,
    do_embed: bool,
    db_path: Path | None,
):
    """Build the index for one project."""
    project_path = (project_path or Path.cwd()).resolve()
    if not project_path.is_dir():
        raise click.BadParameter(f"PROJECT_PATH is not a directory: {project_path}")

    click.echo(f"Building index for: {project_path}")

    # Stage 0: deterministic scan.
    click.echo("Stage 0: scanning project...")
    scan = scan_project(project_path, workspace_root=workspace_root)
    click.echo(
        f"  {scan.file_tree_full_count} files, "
        f"{len(scan.pyproject_tomls)} pyproject.toml, "
        f"{len(scan.package_jsons)} package.json, "
        f"{len(scan.go_mods)} go.mod, "
        f"{len(scan.cargo_tomls)} Cargo.toml, "
        f"{len(scan.claude_plugins)} claude-plugin, "
        f"{len(scan.devcontainer_features)} devcontainer-feature"
    )

    # Start from the manifest skeleton (placeholders + deterministic facts).
    manifest = build_manifest(project_path, workspace_root=workspace_root)

    # Stage 1: LLM classification + entry plan (with checkpoint reuse).
    plan: PlannerOutput | None = None
    thread_id: str | None = None
    click.echo(f"Stage 1: planning via {model or '<default model>'}{' (forced)' if force else ''}...")
    try:
        result = run_planner(scan, model=model, force=force)
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(f"Stage 1 failed: {exc}") from exc
    plan = result.output
    thread_id = result.thread_id
    if result.cached:
        click.echo(f"  [cached] thread_id={thread_id}")
    else:
        click.echo(f"  [fresh]  thread_id={thread_id}")
    _apply_plan_to_manifest(manifest, plan)
    if verbose:
        click.echo("--- raw LLM response ---")
        click.echo(plan.raw_llm_response)
        click.echo("--- end ---")

    # Resolve output and write.
    resolved = resolve_output_dir(
        project_path=project_path,
        output=output_path,
        sidecar=sidecar,
        workspace_root=workspace_root,
    )
    click.echo(f"Output: {resolved.output_dir}  ({resolved.reason})")

    manifest_path = write_manifest(resolved.output_dir, manifest)

    # Stage 2a: packages.
    click.echo("Stage 2a: packages...")
    packages = run_packages(
        scan,
        plan.entry_plan_packages,
        project_path,
        model=model,
    )
    pkg_path = write_packages_jsonl(resolved.output_dir, packages)
    manifest.counts.packages = len(packages)
    click.echo(f"  {len(packages)} package(s)")

    # Stage 2b: snippets.
    click.echo("Stage 2b: snippets...")
    snippets = run_snippets(
        scan,
        plan.entry_plan_snippets,
        project_path,
        model=model,
    )
    snip_path = write_snippets_jsonl(resolved.output_dir, snippets)
    manifest.counts.snippets = len(snippets)
    click.echo(f"  {len(snippets)} snippet(s)")

    # Stage 2c: references.
    click.echo("Stage 2c: references...")
    references = run_references(
        scan,
        plan.entry_plan_references,
        project_path,
        model=model,
    )
    ref_path = write_references_jsonl(resolved.output_dir, references)
    manifest.counts.references = len(references)
    click.echo(f"  {len(references)} reference(s)")

    # Re-write manifest with updated counts.
    write_manifest(resolved.output_dir, manifest)

    stage1_path = write_stage1_state(resolved.output_dir, scan, plan, thread_id or "")

    click.echo("Wrote:")
    click.echo(f"  {manifest_path.relative_to(resolved.output_dir.parent)}")
    click.echo(f"  {pkg_path.relative_to(resolved.output_dir.parent)}  ({len(packages)} package(s))")
    click.echo(f"  {snip_path.relative_to(resolved.output_dir.parent)}  ({len(snippets)} snippet(s))")
    click.echo(f"  {ref_path.relative_to(resolved.output_dir.parent)}  ({len(references)} reference(s))")
    click.echo(f"  {stage1_path.relative_to(resolved.output_dir.parent)}  (Stage 1 state)")
    click.echo()
    _print_summary(manifest, plan)

    # Phase 6: optional embedding.
    if do_embed:
        resolved_db = db_path or _default_db_path(resolved.output_dir, workspace_root)
        click.echo()
        click.echo(f"Embedding via Voyage; DB: {resolved_db}")
        try:
            summary = embed_index_files(
                project_slug=manifest.project,
                index_dir=resolved.output_dir,
                db_path=resolved_db,
                verbose=verbose,
            )
        except Exception as exc:  # noqa: BLE001
            raise click.ClickException(f"Embedding failed: {exc}") from exc
        click.echo(
            f"  embedded: {summary.embedded}, cached: {summary.cached}, "
            f"deleted: {summary.deleted}, tokens: {summary.tokens}, "
            f"est. cost: ${summary.cost_estimate_usd:.4f}"
        )


def _default_db_path(output_dir: Path, workspace_root: Path | None) -> Path:
    """Default vector store: <workspace-root>/.cosai-indexes/.data/index.db.

    When `output_dir` already lives under `.cosai-indexes/<slug>/`, the parent
    is the right anchor. Otherwise fall back to workspace_root or its parent.
    """
    # If output_dir's parent ends with .cosai-indexes, that's the workspace root anchor.
    parent = output_dir.parent
    if parent.name == ".cosai-indexes":
        return parent / ".data" / "index.db"
    if workspace_root is not None:
        return workspace_root.resolve() / ".cosai-indexes" / ".data" / "index.db"
    # Last resort: alongside the output dir.
    return output_dir.parent / ".cosai-indexes" / ".data" / "index.db"


@cli.command()
@click.argument(
    "workspace_path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=False,
)
@click.option(
    "--db-path",
    type=click.Path(file_okay=True, dir_okay=False, path_type=Path),
    default=None,
    help="Override the vector-store path. Default: <workspace>/.cosai-indexes/.data/index.db",
)
@click.option(
    "--project",
    "only_project",
    type=str,
    default=None,
    help="Show status for one project only.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Emit machine-readable JSON.",
)
def status(
    workspace_path: Path | None,
    db_path: Path | None,
    only_project: str | None,
    as_json: bool,
):
    """Show per-project index + vector-store status."""
    import json as _json

    workspace_path = (workspace_path or Path.cwd()).resolve()
    indexes_root = workspace_path / ".cosai-indexes"
    if not indexes_root.exists():
        raise click.ClickException(
            f"No .cosai-indexes/ directory under {workspace_path}. Run a build first."
        )

    db_resolved = db_path or (indexes_root / ".data" / "index.db")

    project_dirs = sorted(
        [p for p in indexes_root.iterdir() if p.is_dir() and p.name != ".data"]
    )
    if only_project is not None:
        project_dirs = [p for p in project_dirs if p.name == only_project]
        if not project_dirs:
            raise click.ClickException(
                f"No index dir for project '{only_project}' under {indexes_root}"
            )

    rows = []
    store: VectorStore | None = None
    if db_resolved.exists():
        store = VectorStore.open(db_resolved)

    try:
        for pdir in project_dirs:
            row = _status_for(pdir, store)
            rows.append(row)
    finally:
        if store is not None:
            store.close()

    if as_json:
        click.echo(_json.dumps({"db": str(db_resolved), "projects": rows}, indent=2))
        return

    if not rows:
        click.echo("No projects indexed.")
        return

    # Human-readable table.
    header = ("project", "schema", "last_indexed", "stale", "M", "P", "S", "R", "vec", "in_sync")
    widths = [
        max(len(header[0]), *(len(r["project"]) for r in rows)),
        len(header[1]),
        len(header[2]) + 8,  # date is 10 chars
        5,
        3,
        3,
        3,
        3,
        4,
        7,
    ]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    click.echo(fmt.format(*header))
    click.echo("  ".join("-" * w for w in widths))
    for r in rows:
        click.echo(
            fmt.format(
                r["project"],
                r["schema_version"] or "?",
                r["last_indexed"] or "<never>",
                f"{r['days_stale']}d" if r["days_stale"] is not None else "?",
                str(r["counts"]["manifest"]),
                str(r["counts"]["packages"]),
                str(r["counts"]["snippets"]),
                str(r["counts"]["references"]),
                str(r["vectors"]),
                "yes" if r["in_sync"] else "no",
            )
        )

    if not db_resolved.exists():
        click.echo()
        click.echo(f"(Vector store does not exist yet at {db_resolved})")


def _status_for(project_dir: Path, store: VectorStore | None) -> dict:
    """Compute one row of status output for a project's index directory."""
    import hashlib
    import json as _json
    from datetime import datetime, timezone

    project_slug = project_dir.name
    manifest_path = project_dir / "manifest.json"
    packages_path = project_dir / "packages.jsonl"
    snippets_path = project_dir / "snippets.jsonl"
    references_path = project_dir / "references.jsonl"

    counts = {
        "manifest": 0,
        "packages": _count_lines(packages_path),
        "snippets": _count_lines(snippets_path),
        "references": _count_lines(references_path),
    }

    schema_version: str | None = None
    last_indexed: str | None = None
    days_stale: int | None = None
    manifest_description_hash: str | None = None

    if manifest_path.exists():
        manifest = _json.loads(manifest_path.read_text(encoding="utf-8"))
        schema_version = manifest.get("schema_version")
        last_indexed = manifest.get("last_indexed")
        description = (manifest.get("description") or "").strip()
        if description:
            counts["manifest"] = 1
            manifest_description_hash = (
                "sha256:" + hashlib.sha256(description.encode("utf-8")).hexdigest()
            )
        if last_indexed:
            try:
                dt = datetime.fromisoformat(last_indexed.replace("Z", "+00:00"))
                days_stale = (datetime.now(tz=timezone.utc) - dt).days
            except ValueError:
                pass

    expected_total = sum(counts.values())
    in_sync = store is not None  # without a DB, sync is unknown → report False
    vectors = 0
    diff_notes: list[str] = []

    if store is not None:
        existing = {
            "manifest": store.existing_hashes(project_slug, "manifest"),
            "package": store.existing_hashes(project_slug, "package"),
            "snippet": store.existing_hashes(project_slug, "snippet"),
            "reference": store.existing_hashes(project_slug, "reference"),
        }
        vectors = sum(len(v) for v in existing.values())

        # Check manifest hash matches.
        if counts["manifest"] == 1 and manifest_description_hash:
            if existing["manifest"].get(project_slug) != manifest_description_hash:
                in_sync = False
                diff_notes.append("manifest")

        # Cross-check JSONL entries against vector hashes.
        for kind, jsonl_path in (
            ("package", packages_path),
            ("snippet", snippets_path),
            ("reference", references_path),
        ):
            jsonl_keys: set[str] = set()
            if jsonl_path.exists():
                for row in _read_jsonl_safely(jsonl_path):
                    eid = row.get("id")
                    if eid is None:
                        continue
                    jsonl_keys.add(eid)
                    if existing[kind].get(eid) != row.get("content_hash"):
                        in_sync = False
            store_keys = set(existing[kind].keys())
            stale = store_keys - jsonl_keys
            if stale:
                in_sync = False
                diff_notes.append(f"{kind} stale={len(stale)}")
            missing = jsonl_keys - store_keys
            if missing:
                in_sync = False
                diff_notes.append(f"{kind} missing={len(missing)}")

        if vectors != expected_total:
            in_sync = False

    return {
        "project": project_slug,
        "schema_version": schema_version,
        "last_indexed": last_indexed,
        "days_stale": days_stale,
        "counts": counts,
        "vectors": vectors,
        "in_sync": in_sync,
        "diff_notes": diff_notes,
    }


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    n = 0
    with path.open("rb") as f:
        for line in f:
            if line.strip():
                n += 1
    return n


def _read_jsonl_safely(path: Path):
    import json as _json

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield _json.loads(line)
            except _json.JSONDecodeError:
                continue


@cli.command()
@click.argument("project_slug", type=str)
@click.option(
    "--workspace-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Workspace root. Default: current directory.",
)
@click.option(
    "--db-path",
    type=click.Path(file_okay=True, dir_okay=False, path_type=Path),
    default=None,
    help="Override the vector-store path.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be deleted without modifying the database.",
)
def drop(
    project_slug: str,
    workspace_root: Path | None,
    db_path: Path | None,
    dry_run: bool,
):
    """Remove a project's vectors from the store. Files on disk are untouched."""
    root = (workspace_root or Path.cwd()).resolve()
    db_resolved = db_path or (root / ".cosai-indexes" / ".data" / "index.db")
    if not db_resolved.exists():
        raise click.ClickException(f"Vector store does not exist at {db_resolved}")

    with VectorStore.open(db_resolved) as store:
        n = store.count_vectors(project=project_slug)
        if n == 0:
            click.echo(f"No vectors for project '{project_slug}'.")
            return
        if dry_run:
            click.echo(f"Would delete {n} vector(s) for '{project_slug}'.")
            return
        deleted = store.drop_project(project_slug)
        click.echo(f"Deleted {deleted} vector(s) for '{project_slug}'.")


def _apply_plan_to_manifest(manifest: Manifest, plan: PlannerOutput) -> None:
    """Merge Stage 1 output into the manifest skeleton."""
    manifest.description = plan.description
    manifest.primary_kind = plan.primary_kind
    manifest.primary_kind_other = (
        plan.primary_kind_other if plan.primary_kind == "other" else None
    )
    manifest.also = plan.also
    manifest.status = plan.status
    manifest.owners = plan.owners
    manifest.tags = plan.tags
    manifest.languages = plan.languages
    # Use the LLM's license judgement if it produced one; otherwise keep the
    # filename detected in Stage 0.
    if plan.license is not None:
        manifest.license = plan.license
    manifest.related_urls = list(plan.related_urls)


def _print_summary(manifest: Manifest, plan: PlannerOutput) -> None:
    click.echo("Manifest:")
    click.echo(f"  project: {manifest.project}")
    click.echo(f"  primary_kind: {manifest.primary_kind}", nl=False)
    if manifest.primary_kind == "other" and manifest.primary_kind_other:
        click.echo(f"  ({manifest.primary_kind_other})")
    else:
        click.echo("")
    click.echo(f"  also: {manifest.also}")
    click.echo(f"  status: {manifest.status}")
    click.echo(f"  languages: {manifest.languages}")
    click.echo(f"  license: {manifest.license or '<none>'}")
    click.echo(f"  tags: {manifest.tags}")
    click.echo(f"  owners: {manifest.owners}")
    click.echo(f"  related_urls: {len(manifest.related_urls)} url(s)")
    for u in manifest.related_urls[:5]:
        click.echo(f"    - {u}")
    if len(manifest.related_urls) > 5:
        click.echo(f"    ... ({len(manifest.related_urls) - 5} more)")
    desc = manifest.description or "<empty>"
    click.echo(f"  description: {desc[:200]}{'...' if len(desc) > 200 else ''}")
    click.echo()
    click.echo("Entry plan (for later stages):")
    click.echo(f"  packages: {len(plan.entry_plan_packages)}")
    click.echo(f"  snippets: {len(plan.entry_plan_snippets)}")
    click.echo(f"  references: {len(plan.entry_plan_references)}")


if __name__ == "__main__":
    cli()
