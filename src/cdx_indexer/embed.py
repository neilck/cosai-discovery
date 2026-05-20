"""Voyage embedding wrapper and Phase 6 orchestration.

`VoyageEmbedder` is the thin SDK wrapper (batching, retry, token counting).
`embed_index_files()` is the top-level orchestrator: reads the JSONL files a
build just wrote, diffs against the vector store, calls Voyage for what
changed, upserts vectors, deletes stale rows.

Pass `verbose=True` to embed_index_files() to print a step-by-step trace of
the pipeline. Each trace line is prefixed `[embed]` for easy grepping.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import voyageai

from .vectorstore import EntryKey, VectorStore


def _trace(verbose: bool, msg: str) -> None:
    """Emit a [embed] debug line on stderr when verbose is on.

    stderr keeps trace output separate from any structured stdout the caller
    might want to pipe (e.g. --json). The prefix lets you grep `[embed]` to
    isolate the pipeline trace from other logs.
    """
    if verbose:
        print(f"[embed] {msg}", file=sys.stderr, flush=True)

# Model names per spec (_docs/index-file-format-0.1.0.md → Embedding strategy).
MODEL_PROSE = "voyage-3"
MODEL_CODE = "voyage-code-3"

# Voyage's batch endpoint caps at 128 inputs and ~120K total tokens per call.
# Conservative batch sizes; we'll chunk further if a single batch exceeds
# Voyage's token limit (counted client-side via the SDK).
BATCH_SIZE_LIMIT = 64
BATCH_TOKEN_LIMIT = 100_000


# ----------------------------------------------------------------- embedder


@dataclass
class EmbedderResult:
    vectors: list[list[float]]
    total_tokens: int


class VoyageEmbedder:
    """Per-model Voyage embedder with batching and exponential-backoff retry."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        max_retries: int = 4,
        verbose: bool = False,
    ):
        if api_key is None:
            api_key = os.environ.get("VOYAGE_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "VOYAGE_API_KEY not set. Add it to .env or export it before "
                    "running an --embed build."
                )
        self.model = model
        self._client = voyageai.Client(api_key=api_key, max_retries=0)
        self._max_retries = max_retries
        self._verbose = verbose
        _trace(self._verbose, f"VoyageEmbedder.__init__ model={model} max_retries={max_retries}")

    def embed(self, texts: list[str], input_type: str = "document") -> EmbedderResult:
        """Embed a list of texts; returns vectors in input order plus token total."""
        if not texts:
            _trace(self._verbose, f"VoyageEmbedder.embed model={self.model} (no texts; skip)")
            return EmbedderResult(vectors=[], total_tokens=0)

        # Split into batches, respecting count AND token caps.
        batches = self._chunk_into_batches(texts)
        _trace(
            self._verbose,
            f"VoyageEmbedder.embed model={self.model} texts={len(texts)} "
            f"batches={len(batches)} (limit_per_batch={BATCH_SIZE_LIMIT})",
        )

        out_vectors: list[list[float]] = []
        total_tokens = 0
        for i, batch in enumerate(batches, start=1):
            est = sum(max(1, len(t) // 4) for t in batch)
            _trace(
                self._verbose,
                f"  batch {i}/{len(batches)}: {len(batch)} text(s), ~{est} est-tokens → POST",
            )
            r = self._embed_one_batch(batch, input_type=input_type)
            _trace(
                self._verbose,
                f"  batch {i}/{len(batches)}: ← {len(r.vectors)} vec(s), "
                f"{r.total_tokens} actual-tokens",
            )
            out_vectors.extend(r.vectors)
            total_tokens += r.total_tokens

        return EmbedderResult(vectors=out_vectors, total_tokens=total_tokens)

    def _chunk_into_batches(self, texts: list[str]) -> list[list[str]]:
        """Group texts into batches not exceeding BATCH_SIZE_LIMIT or BATCH_TOKEN_LIMIT."""
        # Cheap upper-bound token estimate: 4 chars/token. Don't pay for a real
        # tokenize call here — Voyage charges for it and we just need a guard.
        def est_tokens(t: str) -> int:
            return max(1, len(t) // 4)

        batches: list[list[str]] = []
        current: list[str] = []
        current_tokens = 0
        for t in texts:
            tt = est_tokens(t)
            would_overflow = (
                len(current) >= BATCH_SIZE_LIMIT
                or (current and current_tokens + tt > BATCH_TOKEN_LIMIT)
            )
            if would_overflow:
                batches.append(current)
                current = []
                current_tokens = 0
            current.append(t)
            current_tokens += tt
        if current:
            batches.append(current)
        return batches

    def _embed_one_batch(self, batch: list[str], input_type: str) -> EmbedderResult:
        delay = 1.0
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._client.embed(
                    texts=batch,
                    model=self.model,
                    input_type=input_type,
                    truncation=True,
                )
                return EmbedderResult(
                    vectors=[list(v) for v in resp.embeddings],
                    total_tokens=int(resp.total_tokens or 0),
                )
            except Exception as exc:  # noqa: BLE001 — Voyage SDK raises generic RuntimeError
                last_exc = exc
                if attempt >= self._max_retries:
                    break
                _trace(
                    self._verbose,
                    f"    retry {attempt + 1}/{self._max_retries}: "
                    f"{type(exc).__name__}: {exc}; sleeping {delay:.1f}s",
                )
                time.sleep(delay)
                delay = min(delay * 2.0, 16.0)
        raise RuntimeError(
            f"Voyage embed failed after {self._max_retries + 1} attempts "
            f"(model={self.model}, batch_size={len(batch)}): {last_exc}"
        ) from last_exc


# --------------------------------------------------------- index orchestration


@dataclass
class CorpusEntry:
    """One row we'd send to the embedder. Carries enough to upsert later."""

    project: str
    kind: str  # 'manifest' | 'package' | 'snippet' | 'reference'
    entry_id: str
    content_hash: str
    model: str  # voyage-3 | voyage-code-3
    embedded_text: str  # what we'll send to Voyage


@dataclass
class EmbedSummary:
    embedded: int = 0
    cached: int = 0
    deleted: int = 0
    tokens: int = 0
    cost_estimate_usd: float = 0.0


def embed_index_files(
    *,
    project_slug: str,
    index_dir: Path,
    db_path: Path,
    voyage_api_key: str | None = None,
    verbose: bool = False,
) -> EmbedSummary:
    """Read JSONLs from index_dir, embed the new/changed entries, upsert to DB.

    Pipeline (visible with verbose=True):
      1. Load desired entries from manifest.json / packages.jsonl /
         snippets.jsonl / references.jsonl. One CorpusEntry per row that
         should have a vector.
      2. Open the vector store; fetch existing content_hashes per kind.
      3. Diff: for each desired entry, either flag for re-embed (hash differs
         or no row in store) or count as cached.
      4. Group entries-to-embed by model (voyage-3 for prose, voyage-code-3
         for code).
      5. For each model, call Voyage once per batch (≤64 texts/batch).
      6. Upsert each (entry, vector) pair to the store.
      7. Delete rows in the store whose entry_id is gone from the JSONL.

    Side effects: writes to db_path; calls Voyage cloud for any non-cached
    entry.
    """
    _trace(verbose, f"embed_index_files START project={project_slug}")
    _trace(verbose, f"  index_dir = {index_dir}")
    _trace(verbose, f"  db_path   = {db_path}")

    # Step 1.
    _trace(verbose, "step 1: load desired entries from JSONL files")
    desired = list(_load_desired_entries(project_slug, index_dir))
    if verbose:
        by_kind_count: dict[str, int] = {}
        for e in desired:
            by_kind_count[e.kind] = by_kind_count.get(e.kind, 0) + 1
        _trace(
            verbose,
            "  loaded "
            + ", ".join(f"{k}={v}" for k, v in sorted(by_kind_count.items()))
            + f" (total={len(desired)})",
        )

    # Step 2.
    _trace(verbose, "step 2: open vector store + fetch existing hashes")
    with VectorStore.open(db_path) as store:
        existing_by_kind: dict[str, dict[str, str]] = {
            "manifest": store.existing_hashes(project_slug, "manifest"),
            "package": store.existing_hashes(project_slug, "package"),
            "snippet": store.existing_hashes(project_slug, "snippet"),
            "reference": store.existing_hashes(project_slug, "reference"),
        }
        if verbose:
            _trace(
                verbose,
                "  store currently holds "
                + ", ".join(
                    f"{k}={len(v)}" for k, v in sorted(existing_by_kind.items())
                ),
            )

        # Step 3.
        _trace(verbose, "step 3: diff desired vs. stored (by content_hash)")
        desired_keys: set[tuple[str, str]] = set()  # (kind, entry_id)
        to_embed: list[CorpusEntry] = []
        cached = 0

        for entry in desired:
            desired_keys.add((entry.kind, entry.entry_id))
            prior_hash = existing_by_kind[entry.kind].get(entry.entry_id)
            if prior_hash == entry.content_hash:
                cached += 1
                continue
            to_embed.append(entry)

        _trace(verbose, f"  cached={cached}, to_embed={len(to_embed)}")

        # Step 4.
        _trace(verbose, "step 4: group entries-to-embed by Voyage model")
        by_model: dict[str, list[CorpusEntry]] = {MODEL_PROSE: [], MODEL_CODE: []}
        for e in to_embed:
            by_model.setdefault(e.model, []).append(e)
        for m, es in by_model.items():
            _trace(verbose, f"  {m}: {len(es)} entr(ies)")

        summary = EmbedSummary(cached=cached)

        # Steps 5 + 6.
        _trace(verbose, "step 5+6: call Voyage per model; upsert each (entry, vector)")
        for model, entries in by_model.items():
            if not entries:
                continue
            embedder = VoyageEmbedder(
                model=model, api_key=voyage_api_key, verbose=verbose
            )
            result = embedder.embed([e.embedded_text for e in entries])
            _trace(verbose, f"  upserting {len(entries)} {model} vectors into store")
            for entry, vector in zip(entries, result.vectors, strict=True):
                store.upsert(
                    EntryKey(entry.project, entry.kind, entry.entry_id),
                    content_hash=entry.content_hash,
                    model=entry.model,
                    embedded_text=entry.embedded_text,
                    vector=vector,
                )
            summary.embedded += len(entries)
            summary.tokens += result.total_tokens

        # Step 7.
        _trace(verbose, "step 7: delete vectors whose entry vanished from JSONL")
        for kind, hashes in existing_by_kind.items():
            for entry_id in hashes:
                if (kind, entry_id) not in desired_keys:
                    _trace(verbose, f"  delete {kind}/{entry_id}")
                    store.delete_entry(EntryKey(project_slug, kind, entry_id))
                    summary.deleted += 1

    summary.cost_estimate_usd = _estimate_cost(summary.tokens)
    _trace(
        verbose,
        f"embed_index_files DONE embedded={summary.embedded} cached={summary.cached} "
        f"deleted={summary.deleted} tokens={summary.tokens} "
        f"cost≈${summary.cost_estimate_usd:.4f}",
    )
    return summary


# ------------------------------------------------------------- file readers


def _load_desired_entries(
    project_slug: str, index_dir: Path, verbose: bool = False
) -> Iterable[CorpusEntry]:
    """Yield one CorpusEntry per row that should have a vector.

    Reads, in order:
      manifest.json   → 1 entry (the description), model voyage-3
      packages.jsonl  → 1 entry per row, model voyage-code-3
      snippets.jsonl  → 1 entry per row, model voyage-code-3
      references.jsonl → 1 entry per row, model voyage-3
    Rows with empty embedded text are skipped silently.
    """
    # Manifest is a single JSON object, not JSONL.
    manifest_path = index_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        description = (manifest.get("description") or "").strip()
        if description:
            # Hash the description itself so a manifest re-write that didn't
            # change the description doesn't re-embed.
            import hashlib

            ch = "sha256:" + hashlib.sha256(description.encode("utf-8")).hexdigest()
            yield CorpusEntry(
                project=project_slug,
                kind="manifest",
                entry_id=project_slug,
                content_hash=ch,
                model=MODEL_PROSE,
                embedded_text=description,
            )

    pkg_path = index_dir / "packages.jsonl"
    if pkg_path.exists():
        for row in _read_jsonl(pkg_path):
            text = _join_nonempty([row.get("summary"), row.get("install")])
            if not text:
                continue
            yield CorpusEntry(
                project=project_slug,
                kind="package",
                entry_id=row["id"],
                content_hash=row["content_hash"],
                model=MODEL_CODE,
                embedded_text=text,
            )

    snip_path = index_dir / "snippets.jsonl"
    if snip_path.exists():
        for row in _read_jsonl(snip_path):
            text = _join_nonempty([row.get("title"), row.get("summary")])
            if not text:
                continue
            yield CorpusEntry(
                project=project_slug,
                kind="snippet",
                entry_id=row["id"],
                content_hash=row["content_hash"],
                model=MODEL_CODE,
                embedded_text=text,
            )

    ref_path = index_dir / "references.jsonl"
    if ref_path.exists():
        for row in _read_jsonl(ref_path):
            text = _join_nonempty(
                [row.get("title"), row.get("summary"), row.get("structure_description")]
            )
            if not text:
                continue
            yield CorpusEntry(
                project=project_slug,
                kind="reference",
                entry_id=row["id"],
                content_hash=row["content_hash"],
                model=MODEL_PROSE,
                embedded_text=text,
            )


def _read_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _join_nonempty(parts: list[str | None]) -> str:
    return "\n\n".join(p.strip() for p in parts if p and p.strip())


# --------------------------------------------------------------- cost guess


# Voyage public pricing (as of Aug 2025 knowledge cutoff): voyage-3 family is
# ~$0.06 / 1M tokens; voyage-code-3 ~$0.18 / 1M. Treat as approximate.
_PRICE_PER_M_TOKEN = 0.10  # blended average; output is a rough order-of-magnitude


def _estimate_cost(tokens: int) -> float:
    return (tokens / 1_000_000) * _PRICE_PER_M_TOKEN
