"""Configuration loading and path resolution.

Reads cdx-config.yaml from the repo root and resolves all paths relative
to the config file's directory. Resolution order (later wins):
  1. Built-in defaults
  2. cdx-config.yaml
  3. Environment variables (CDX_MODEL, CDX_EMBED, etc.)
  4. CLI flags (passed directly to CdxConfig methods)

All paths are resolved to absolute paths at load time.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

_DEFAULT_CONFIG = {
    "workspace": {
        "root": "..",
        "indexes_dir": ".cosai-indexes",
        "sidecar": True,
    },
    "data": {
        "checkpoints_db": ".cdx/checkpoints.db",
        "vectors_db": ".cdx/vectors.db",
    },
    "models": {
        "default": "claude-haiku-4-5",
        "strong": "claude-sonnet-4-6",
    },
    "embed": {
        "enabled": False,
    },
}


@dataclass
class CdxConfig:
    """Resolved configuration for the indexer.

    All paths are absolute. The config_dir is the directory containing
    cdx-config.yaml (or the repo root if auto-discovered).
    """

    config_dir: Path
    workspace_root: Path
    indexes_dir: Path
    sidecar: bool
    checkpoints_db: Path
    vectors_db: Path
    model_default: str
    model_strong: str
    embed_enabled: bool

    @classmethod
    def load(cls, config_path: Path | None = None) -> CdxConfig:
        """Load and resolve configuration.

        If config_path is provided, use it. Otherwise auto-discover by walking
        up from cwd looking for cdx-config.yaml. If not found, use built-in
        defaults anchored to the repo root.
        """
        if config_path is not None:
            config_dir = config_path.resolve().parent
            config_data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        else:
            # Auto-discover: walk up from cwd looking for cdx-config.yaml
            config_dir = _find_config_file()
            config_path = config_dir / "cdx-config.yaml"
            if config_path.exists():
                config_data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            else:
                config_data = {}

        # Merge: built-in defaults, file, env vars
        merged = _merge_config(_DEFAULT_CONFIG.copy(), config_data or {})

        # Resolve all paths relative to config_dir
        workspace_root = (config_dir / merged["workspace"]["root"]).resolve()
        indexes_dir = (config_dir / merged["workspace"]["indexes_dir"]).resolve()
        checkpoints_db = (config_dir / merged["data"]["checkpoints_db"]).resolve()
        vectors_db = (config_dir / merged["data"]["vectors_db"]).resolve()

        # Env var overrides
        model_default = os.environ.get(
            "CDX_MODEL", merged["models"]["default"]
        )
        model_strong = os.environ.get("CDX_MODEL_STRONG", merged["models"]["strong"])
        embed_enabled = os.environ.get("CDX_EMBED", "").lower() in (
            "1",
            "true",
            "yes",
        ) or merged["embed"]["enabled"]

        return cls(
            config_dir=config_dir,
            workspace_root=workspace_root,
            indexes_dir=indexes_dir,
            sidecar=merged["workspace"]["sidecar"],
            checkpoints_db=checkpoints_db,
            vectors_db=vectors_db,
            model_default=model_default,
            model_strong=model_strong,
            embed_enabled=embed_enabled,
        )

    def get_model(self, model: str | None) -> str:
        """Resolve model name: CLI arg → env var → config → default.

        model="strong" is a shorthand for models.strong from config.
        """
        if model == "strong":
            return self.model_strong
        if model:
            return model
        return self.model_default


def _find_config_file() -> Path:
    """Walk up from cwd looking for cdx-config.yaml or repo root.

    Returns the directory containing cdx-config.yaml, or the first
    directory containing pyproject.toml (repo root) if cdx-config.yaml
    is not found.
    """
    current = Path.cwd().resolve()
    for parent in [current, *current.parents]:
        if (parent / "cdx-config.yaml").exists():
            return parent
        if (parent / "pyproject.toml").exists():
            return parent
    return current


def _merge_config(defaults: dict, overrides: dict) -> dict:
    """Recursively merge overrides into defaults (overrides win)."""
    result = defaults.copy()
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_config(result[key], value)
        else:
            result[key] = value
    return result
