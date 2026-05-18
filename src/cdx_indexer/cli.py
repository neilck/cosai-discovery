"""CLI entry point for cdx-index.

Phase 1 work begins here. See _docs/indexer-build-plan.md for the build order.
"""

import click


@click.group()
@click.version_option()
def cli():
    """COSAI Discovery indexer."""


@cli.command()
@click.argument("project_path", type=click.Path(exists=True, file_okay=False), required=False)
@click.option("--output", "output_path", type=click.Path(file_okay=False), help="Where to write index files. Defaults to PROJECT_PATH/.cosai-index/ if writable, else workspace sidecar.")
@click.option("--sidecar", is_flag=True, help="Force sidecar location even when project is writable.")
@click.option("--workspace-root", type=click.Path(exists=True, file_okay=False), help="Override inferred workspace root.")
def build(project_path, output_path, sidecar, workspace_root):
    """Build the index for one project."""
    click.echo("cdx-index build: not yet implemented (Phase 1 in progress)")
    click.echo(f"  project_path={project_path or '<cwd>'}")
    click.echo(f"  output_path={output_path or '<default>'}")
    click.echo(f"  sidecar={sidecar}")
    click.echo(f"  workspace_root={workspace_root or '<inferred>'}")


if __name__ == "__main__":
    cli()
