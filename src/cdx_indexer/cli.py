"""CLI entry point for cdx-index.

Stage 0 (deterministic scan) → Stage 1 (LLM classification + entry plan)
→ writer. Subsequent stages (per-entry processing, embedding) come later.
"""

from __future__ import annotations

from pathlib import Path

import click

from . import __version__
from .manifest import build_manifest
from .packages import run_packages
from .planner import PlannerOutput, run_planner
from .references import run_references
from .scan import scan_project
from .snippets import run_snippets
from .types import Manifest
from .writer import (
    resolve_output_dir,
    write_empty_jsonl,
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
def build(
    project_path: Path | None,
    output_path: Path | None,
    sidecar: bool,
    workspace_root: Path | None,
    force: bool,
    model: str | None,
    verbose: bool,
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
