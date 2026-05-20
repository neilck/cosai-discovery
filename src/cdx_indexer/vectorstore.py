"""SQLite + sqlite-vec vector store for embedded index entries.

Schema:
  schema_version(version)                      -- DB schema marker
  entries(project, kind, entry_id, ...)        -- metadata + content_hash
  vec_entries(rowid, embedding float[1024])    -- sqlite-vec virtual table
  entry_vec(project, kind, entry_id, rowid)    -- bridge to vec_entries

Phase 6 (see _docs/indexer-build-plan.md). One row per embedded entry; the
indexer does not chunk past the entry boundary (that's the importer's job,
and in this codebase the indexer IS the importer for now).
"""

from __future__ import annotations

import sqlite3
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import sqlite_vec

DB_SCHEMA_VERSION = "1"
VECTOR_DIM = 1024  # voyage-3 and voyage-code-3 default

EntryKind = str  # 'manifest' | 'package' | 'snippet' | 'reference'


@dataclass(frozen=True)
class EntryKey:
    project: str
    kind: EntryKind
    entry_id: str


@dataclass(frozen=True)
class SearchHit:
    project: str
    kind: EntryKind
    entry_id: str
    distance: float


class VectorStore:
    """Thin wrapper around the project's SQLite database.

    Open one per process. The connection is single-threaded; callers that need
    concurrency should open their own.
    """

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    # ---------------------------------------------------------------- opening

    @classmethod
    def open(cls, db_path: Path) -> "VectorStore":
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        conn.execute("PRAGMA foreign_keys = ON")
        store = cls(conn)
        store._ensure_schema()
        return store

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "VectorStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---------------------------------------------------------------- schema

    def _ensure_schema(self) -> None:
        cur = self._conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
              version TEXT PRIMARY KEY
            );

            CREATE TABLE IF NOT EXISTS entries (
              project       TEXT NOT NULL,
              kind          TEXT NOT NULL,
              entry_id      TEXT NOT NULL,
              content_hash  TEXT NOT NULL,
              model         TEXT NOT NULL,
              embedded_text TEXT NOT NULL,
              embedded_at   TEXT NOT NULL,
              PRIMARY KEY (project, kind, entry_id)
            );
            CREATE INDEX IF NOT EXISTS entries_project_idx ON entries(project);
            CREATE INDEX IF NOT EXISTS entries_kind_idx    ON entries(kind);

            CREATE TABLE IF NOT EXISTS entry_vec (
              project   TEXT NOT NULL,
              kind      TEXT NOT NULL,
              entry_id  TEXT NOT NULL,
              rowid     INTEGER NOT NULL,
              PRIMARY KEY (project, kind, entry_id)
            );
            CREATE INDEX IF NOT EXISTS entry_vec_rowid_idx ON entry_vec(rowid);
            """
        )
        cur.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_entries USING vec0(
              embedding float[{VECTOR_DIM}]
            )
            """
        )
        cur.execute(
            "INSERT OR IGNORE INTO schema_version(version) VALUES (?)",
            (DB_SCHEMA_VERSION,),
        )
        self._conn.commit()

        # Sanity check: refuse to operate on a DB built by a newer schema.
        row = cur.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
        if row and row[0] != DB_SCHEMA_VERSION:
            raise RuntimeError(
                f"Vector store schema mismatch: DB has '{row[0]}', "
                f"indexer expects '{DB_SCHEMA_VERSION}'. Drop the DB and rebuild."
            )

    # ----------------------------------------------------------- queries

    def existing_hashes(self, project: str, kind: EntryKind) -> dict[str, str]:
        """Return {entry_id: content_hash} for every entry in (project, kind)."""
        cur = self._conn.execute(
            "SELECT entry_id, content_hash FROM entries WHERE project = ? AND kind = ?",
            (project, kind),
        )
        return dict(cur.fetchall())

    def all_keys(self, project: str | None = None) -> list[EntryKey]:
        if project is None:
            cur = self._conn.execute(
                "SELECT project, kind, entry_id FROM entries ORDER BY project, kind, entry_id"
            )
        else:
            cur = self._conn.execute(
                "SELECT project, kind, entry_id FROM entries "
                "WHERE project = ? ORDER BY kind, entry_id",
                (project,),
            )
        return [EntryKey(p, k, e) for (p, k, e) in cur.fetchall()]

    def count_vectors(self, project: str | None = None, kind: str | None = None) -> int:
        sql = "SELECT COUNT(*) FROM entries"
        args: list[str] = []
        clauses: list[str] = []
        if project is not None:
            clauses.append("project = ?")
            args.append(project)
        if kind is not None:
            clauses.append("kind = ?")
            args.append(kind)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        return self._conn.execute(sql, args).fetchone()[0]

    def list_projects(self) -> list[str]:
        cur = self._conn.execute(
            "SELECT DISTINCT project FROM entries ORDER BY project"
        )
        return [row[0] for row in cur.fetchall()]

    # ----------------------------------------------------------- mutations

    def upsert(
        self,
        key: EntryKey,
        content_hash: str,
        model: str,
        embedded_text: str,
        vector: list[float],
    ) -> None:
        """Insert or replace one entry + its vector.

        If a row exists with the same content_hash and the same vector model,
        this is a no-op so callers can blindly upsert without re-issuing the
        embedding call. To force a replacement, use replace=True via delete_entry
        first.
        """
        if len(vector) != VECTOR_DIM:
            raise ValueError(
                f"Expected {VECTOR_DIM}-dim vector, got {len(vector)} for "
                f"{key.project}/{key.kind}/{key.entry_id}"
            )

        cur = self._conn.cursor()
        # Look up any existing row.
        row = cur.execute(
            "SELECT content_hash, model FROM entries "
            "WHERE project = ? AND kind = ? AND entry_id = ?",
            (key.project, key.kind, key.entry_id),
        ).fetchone()

        embedded_at = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
        vec_blob = _vector_to_blob(vector)

        if row is None:
            # New entry: insert into vec_entries first to get rowid.
            cur.execute(
                "INSERT INTO vec_entries(embedding) VALUES (?)",
                (vec_blob,),
            )
            new_rowid = cur.lastrowid
            cur.execute(
                "INSERT INTO entry_vec(project, kind, entry_id, rowid) VALUES (?, ?, ?, ?)",
                (key.project, key.kind, key.entry_id, new_rowid),
            )
            cur.execute(
                "INSERT INTO entries"
                "(project, kind, entry_id, content_hash, model, embedded_text, embedded_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    key.project,
                    key.kind,
                    key.entry_id,
                    content_hash,
                    model,
                    embedded_text,
                    embedded_at,
                ),
            )
            self._conn.commit()
            return

        existing_hash, existing_model = row
        if existing_hash == content_hash and existing_model == model:
            # Cached. Skip.
            return

        # Hash or model changed. Replace vector in place using the existing rowid.
        bridge = cur.execute(
            "SELECT rowid FROM entry_vec WHERE project = ? AND kind = ? AND entry_id = ?",
            (key.project, key.kind, key.entry_id),
        ).fetchone()
        if bridge is None:
            raise RuntimeError(
                f"Bridge row missing for {key.project}/{key.kind}/{key.entry_id} — "
                "vector store is in an inconsistent state."
            )
        rowid = bridge[0]
        cur.execute("UPDATE vec_entries SET embedding = ? WHERE rowid = ?", (vec_blob, rowid))
        cur.execute(
            "UPDATE entries SET content_hash = ?, model = ?, embedded_text = ?, embedded_at = ? "
            "WHERE project = ? AND kind = ? AND entry_id = ?",
            (
                content_hash,
                model,
                embedded_text,
                embedded_at,
                key.project,
                key.kind,
                key.entry_id,
            ),
        )
        self._conn.commit()

    def delete_entry(self, key: EntryKey) -> bool:
        """Remove one entry. Returns True if a row was deleted."""
        cur = self._conn.cursor()
        bridge = cur.execute(
            "SELECT rowid FROM entry_vec WHERE project = ? AND kind = ? AND entry_id = ?",
            (key.project, key.kind, key.entry_id),
        ).fetchone()
        if bridge is None:
            return False
        rowid = bridge[0]
        cur.execute("DELETE FROM vec_entries WHERE rowid = ?", (rowid,))
        cur.execute(
            "DELETE FROM entry_vec WHERE project = ? AND kind = ? AND entry_id = ?",
            (key.project, key.kind, key.entry_id),
        )
        cur.execute(
            "DELETE FROM entries WHERE project = ? AND kind = ? AND entry_id = ?",
            (key.project, key.kind, key.entry_id),
        )
        self._conn.commit()
        return True

    def drop_project(self, project: str) -> int:
        """Remove every entry for a project. Returns number of rows deleted."""
        cur = self._conn.cursor()
        bridges = cur.execute(
            "SELECT rowid FROM entry_vec WHERE project = ?",
            (project,),
        ).fetchall()
        if not bridges:
            return 0
        # Delete vectors row by row (vec0 needs explicit rowid deletes).
        for (rowid,) in bridges:
            cur.execute("DELETE FROM vec_entries WHERE rowid = ?", (rowid,))
        cur.execute("DELETE FROM entry_vec WHERE project = ?", (project,))
        cur.execute("DELETE FROM entries WHERE project = ?", (project,))
        self._conn.commit()
        return len(bridges)

    # ----------------------------------------------------------- search

    def search(
        self,
        query_vector: list[float],
        k: int = 10,
        project: str | None = None,
        kind: str | None = None,
    ) -> list[SearchHit]:
        """K-nearest search. Optional project/kind filtering.

        sqlite-vec's KNN syntax requires the query in the WHERE clause via
        `embedding MATCH ?` plus an explicit `k = ?` constraint.
        """
        if len(query_vector) != VECTOR_DIM:
            raise ValueError(
                f"Expected {VECTOR_DIM}-dim query vector, got {len(query_vector)}"
            )
        vec_blob = _vector_to_blob(query_vector)

        # Over-fetch when filtering, so post-filter still leaves k results.
        fetch_k = k
        if project is not None or kind is not None:
            fetch_k = max(k * 5, 50)

        # vec_entries MATCH returns (rowid, distance). Join through entry_vec.
        sql = (
            "SELECT ev.project, ev.kind, ev.entry_id, v.distance "
            "FROM vec_entries v "
            "JOIN entry_vec ev ON ev.rowid = v.rowid "
            "WHERE v.embedding MATCH ? AND k = ? "
            "ORDER BY v.distance"
        )
        rows = self._conn.execute(sql, (vec_blob, fetch_k)).fetchall()

        results: list[SearchHit] = []
        for proj, knd, eid, dist in rows:
            if project is not None and proj != project:
                continue
            if kind is not None and knd != kind:
                continue
            results.append(SearchHit(proj, knd, eid, float(dist)))
            if len(results) >= k:
                break
        return results


def _vector_to_blob(vec: list[float]) -> bytes:
    """Pack a float list into sqlite-vec's expected binary representation."""
    return struct.pack(f"{len(vec)}f", *vec)
