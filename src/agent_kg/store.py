# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""store.py — SQLite + sqlite-vec storage for the AgentKG conversation tree."""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import UTC, datetime, timedelta

os.environ.setdefault("TQDM_DISABLE", "1")
from pathlib import Path
from typing import Any

from kg_utils.embed import DEFAULT_MODEL as _EMBED_MODEL
from kg_utils.embed import KNOWN_MODELS, resolve_model_path

from agent_kg.schema import Edge, EdgeRelation, Node, NodeKind


def _load_sentence_transformer(model_name: str):
    """Load a SentenceTransformer, preferring the local kg_utils cache.

    Checks ``~/.kgrag/models/<model_name>/`` (via :func:`~kg_utils.embed.resolve_model_path`)
    before falling back to the HuggingFace hub download.  This ensures that a
    model pre-downloaded by ``pycodekg download-model`` or a prior ``agent-kg init``
    is used directly without a network round-trip.

    The safetensors weight-loading progress bar is suppressed — it fires on every
    load (local or remote) and is noise in a CLI context.

    :param model_name: HuggingFace repo ID or known short alias (e.g. ``"bge-small"``).
    :return: Loaded :class:`~sentence_transformers.SentenceTransformer` instance.
    """
    from sentence_transformers import SentenceTransformer

    local = resolve_model_path(model_name)
    model_path = str(local) if local.exists() else KNOWN_MODELS.get(model_name, model_name)
    return SentenceTransformer(model_path)


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS nodes (
    id            TEXT PRIMARY KEY,
    kind          TEXT NOT NULL,
    label         TEXT DEFAULT '',
    text          TEXT DEFAULT '',
    role          TEXT DEFAULT '',
    turn_index    INTEGER DEFAULT 0,
    token_count   INTEGER DEFAULT 0,
    status        TEXT DEFAULT '',
    category      TEXT DEFAULT '',
    source        TEXT DEFAULT '',
    confidence    REAL DEFAULT 1.0,
    covers_turns  TEXT DEFAULT '[]',
    pruning_pass  INTEGER DEFAULT 0,
    session_id    TEXT DEFAULT '',
    first_seen    TEXT NOT NULL,
    last_seen     TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    metadata      TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS edges (
    id         TEXT PRIMARY KEY,
    source_id  TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    target_id  TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    relation   TEXT NOT NULL,
    weight     REAL DEFAULT 1.0,
    metadata   TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nodes_kind      ON nodes(kind);
CREATE INDEX IF NOT EXISTS idx_nodes_session   ON nodes(session_id);
CREATE INDEX IF NOT EXISTS idx_nodes_turn_idx  ON nodes(turn_index);
CREATE INDEX IF NOT EXISTS idx_edges_source    ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target    ON edges(target_id);
CREATE INDEX IF NOT EXISTS idx_edges_relation  ON edges(relation);
-- Prevent duplicate topic/entity nodes created by concurrent ingest processes.
-- Only enforced for topic and entity kinds; other kinds (turn, intent, task,
-- summary, profile nodes) use UUID primary keys and allow label collisions.
CREATE UNIQUE INDEX IF NOT EXISTS idx_nodes_kind_label_dedup
    ON nodes(kind, LOWER(TRIM(label)))
    WHERE kind IN ('topic', 'entity');

CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,
    start_time      TEXT NOT NULL,
    end_time        TEXT,
    turn_count      INTEGER DEFAULT 0,
    pruning_passes  INTEGER DEFAULT 0,
    metadata        TEXT DEFAULT '{}'
);
"""

_EMBED_DIM = 384

# Metadata persisted alongside each vector in the sqlite-vec store.  ``search()``
# returns these columns verbatim, so anything a caller reads out of a hit must
# appear here — ``text`` in particular is surfaced directly to consumers.
_META_COLUMNS = ("kind", "text", "session_id")


def _purge_redundant_edges(db: sqlite3.Connection) -> None:
    """Collapse self-loops and duplicates created by repointing edges.

    :param db: Open connection.
    """
    db.execute("DELETE FROM edges WHERE source_id = target_id")
    db.execute(
        """
        DELETE FROM edges
        WHERE rowid NOT IN (
            SELECT MIN(rowid) FROM edges GROUP BY source_id, target_id, relation
        )
        """
    )


class AgentKGStore:
    """Two-layer storage: SQLite for graph topology + sqlite-vec for embeddings.

    :param db_path: Path to the SQLite ``.db`` file.
    :param vectors_path: Path to the sqlite-vec vector store file.
    :param embed_model: sentence-transformers model name for embeddings.
    """

    def __init__(
        self,
        db_path: Path,
        vectors_path: Path,
        embed_model: str = _EMBED_MODEL,
    ) -> None:
        self._db_path = Path(db_path)
        self._vectors_path = Path(vectors_path)
        self._embed_model_name = embed_model
        self._db: sqlite3.Connection | None = None
        self._backend = None
        self._embedder = None
        #: Number of nodes whose embedding failed during this store's lifetime.
        self.embed_failures = 0
        self._embed_warned = False

    # ------------------------------------------------------------------
    # Lazy init
    # ------------------------------------------------------------------

    def _get_db(self) -> sqlite3.Connection:
        if self._db is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(str(self._db_path), check_same_thread=False)
            self._db.row_factory = sqlite3.Row
            # SQLite ignores foreign keys unless asked, per connection. Without
            # this the edges table's ON DELETE CASCADE never fires and deleted
            # nodes leave their edges dangling.
            self._db.execute("PRAGMA foreign_keys = ON")
            # Deduplicate before creating the unique index so that the index
            # creation in _SCHEMA_SQL does not fail on existing duplicate rows.
            self._migrate_dedup_before_schema()
            self._db.executescript(_SCHEMA_SQL)
            self._migrate_purge_dangling_edges()
            self._db.commit()
        return self._db

    def _migrate_dedup_before_schema(self) -> None:
        """Remove duplicate topic/entity rows before the unique index is created.

        Keeps the row with the lexicographically smallest UUID (MIN(id)) for
        each (kind, lower-label) pair and deletes the rest. Safe to call on
        every open: if there are no duplicates the DELETE is a no-op.
        """
        db = self._db
        assert db is not None
        # Only run if the nodes table already exists (i.e. this is an existing DB).
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='nodes'"
        ).fetchone()
        if not exists:
            return
        has_edges = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='edges'"
        ).fetchone()

        for kind in ("topic", "entity"):
            # Move the losers' edges onto the surviving node first. Foreign keys
            # are enabled by the time this runs, so deleting a duplicate would
            # otherwise cascade its edges away and drop the turn-to-topic links
            # the survivor should inherit.
            if has_edges:
                for column in ("source_id", "target_id"):
                    db.execute(
                        f"""
                        UPDATE OR IGNORE edges
                        SET {column} = (
                            SELECT MIN(k.id) FROM nodes k
                            WHERE k.kind = loser.kind
                              AND LOWER(TRIM(k.label)) = LOWER(TRIM(loser.label))
                        )
                        FROM nodes AS loser
                        WHERE edges.{column} = loser.id
                          AND loser.kind = ?
                          AND loser.id NOT IN (
                              SELECT MIN(id) FROM nodes WHERE kind = ?
                              GROUP BY LOWER(TRIM(label))
                          )
                        """,
                        (kind, kind),
                    )
            db.execute(
                """
                DELETE FROM nodes
                WHERE kind = ?
                  AND id NOT IN (
                      SELECT MIN(id)
                      FROM nodes
                      WHERE kind = ?
                      GROUP BY LOWER(TRIM(label))
                  )
                """,
                (kind, kind),
            )

        if has_edges:
            _purge_redundant_edges(db)
        db.commit()

    def _migrate_purge_dangling_edges(self) -> None:
        """Delete edges whose endpoints no longer exist.

        Historical damage only. The schema has always declared ON DELETE
        CASCADE, but SQLite ignores foreign keys unless the pragma is set per
        connection, and it never was -- so every node deletion since the first
        release left its edges behind. Fleet graphs carry thousands each.
        Cheap and idempotent: a no-op once the graph is clean.
        """
        db = self._db
        assert db is not None
        db.execute(
            """
            DELETE FROM edges
            WHERE source_id NOT IN (SELECT id FROM nodes)
               OR target_id NOT IN (SELECT id FROM nodes)
            """
        )

    def _get_backend(self):
        """Open (creating if needed) the sqlite-vec vector store."""
        if self._backend is not None:
            return self._backend
        try:
            from kg_utils.vector_backend import SqliteVecBackend
        except ImportError as exc:
            raise ImportError(
                "kgmodule-utils[sqlite-vec] is required for AgentKG embeddings"
            ) from exc

        self._vectors_path.parent.mkdir(parents=True, exist_ok=True)
        backend = SqliteVecBackend(self._vectors_path, dim=_EMBED_DIM, meta_columns=_META_COLUMNS)
        backend.open()
        self._backend = backend
        return self._backend

    def _get_embedder(self):
        if self._embedder is None:
            self._embedder = _load_sentence_transformer(self._embed_model_name)
        return self._embedder

    def embed(self, text: str) -> list[float]:
        """Return a normalized sentence embedding for ``text``."""
        vec = self._get_embedder().encode(text, normalize_embeddings=True)
        return vec.tolist()

    # ------------------------------------------------------------------
    # Node CRUD
    # ------------------------------------------------------------------

    def upsert_node(self, node: Node) -> None:
        """Insert or update a node (SQLite only — call embed_node separately).

        Deliberately not ``INSERT OR REPLACE``: that deletes the existing row
        before inserting the new one, which fires ``ON DELETE CASCADE`` on the
        edges table and silently destroys every edge touching the node. Ingest
        re-upserts topic and entity nodes on almost every turn, so the damage
        would be continuous. ``ON CONFLICT DO UPDATE`` mutates the row in place
        and leaves edges intact.
        """
        db = self._get_db()
        d = node.to_dict()
        cols = ", ".join(d.keys())
        placeholders = ", ".join(["?"] * len(d))
        assignments = ", ".join(f"{c} = excluded.{c}" for c in d if c != "id")
        db.execute(
            f"INSERT INTO nodes ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {assignments}",
            list(d.values()),
        )
        db.commit()

    def embed_node(self, node: Node) -> None:
        """Compute and upsert the embedding for ``node`` into the vector store.

        Embedding is best-effort: SQLite is always written, and a failure here
        leaves the node searchable structurally but not semantically.  Failures
        are counted in :attr:`embed_failures` and warned about *once* per store
        instance, so a systematically broken embedder is visible rather than
        silent — run ``agentkg reindex`` to backfill afterwards.
        """
        text = (node.text or node.label).strip()
        if not text:
            return
        try:
            vector = self.embed(text)
        except Exception as exc:  # noqa: BLE001 — embedding must never break ingest
            self.embed_failures += 1
            if not self._embed_warned:
                self._embed_warned = True
                print(
                    f"[AgentKG] embedding unavailable ({type(exc).__name__}: {exc}); "
                    "nodes are being stored without vectors. "
                    "Run `agentkg reindex` once resolved.",
                    file=sys.stderr,
                )
            return
        backend = self._get_backend()
        # SqliteVecBackend.upsert() deletes any prior row for the id first, so
        # no separate delete is needed here.
        backend.upsert(
            [
                {
                    "id": node.id,
                    "kind": str(node.kind),
                    "text": text[:500],
                    "session_id": node.session_id,
                    "vector": vector,
                }
            ]
        )

    def missing_embedding_ids(self) -> list[str]:
        """Return ids of nodes present in SQLite but absent from the vector store.

        SQLite is the source of truth; the vector store is derived.  The two
        drift apart whenever a node is written while embedding is disabled
        (``--no-embed``) or unavailable, because nothing backfills afterwards.

        Nodes with no embeddable text are excluded — they can never be indexed,
        so counting them would report permanent phantom drift.

        :return: Node ids needing an embedding, in insertion order.
        """
        rows = (
            self._get_db()
            .execute("SELECT id FROM nodes WHERE TRIM(COALESCE(NULLIF(text, ''), label)) != ''")
            .fetchall()
        )
        try:
            indexed = self._get_backend().existing_ids()
        except Exception:  # noqa: BLE001 — no store yet means everything is missing
            indexed = set()
        return [r["id"] for r in rows if r["id"] not in indexed]

    def reindex(self, *, progress: bool = False) -> dict[str, int]:
        """Embed every node that is missing from the vector store.

        Idempotent: nodes already indexed are skipped, so this is safe to run
        repeatedly and cheap when the store is already in sync.

        :param progress: Print a progress line to stderr every 100 nodes.
        :return: ``{"scanned", "embedded", "failed"}`` counts.
        """
        missing = self.missing_embedding_ids()
        before = self.embed_failures
        embedded = 0
        for i, node_id in enumerate(missing, start=1):
            node = self.get_node(node_id)
            if node is None:
                continue
            self.embed_node(node)
            embedded += 1
            if progress and i % 100 == 0:
                print(f"[AgentKG] reindexed {i}/{len(missing)}", file=sys.stderr)
        failed = self.embed_failures - before
        return {"scanned": len(missing), "embedded": embedded - failed, "failed": failed}

    def upsert_node_with_embedding(self, node: Node) -> None:
        """Write to SQLite and the vector store in one call."""
        self.upsert_node(node)
        self.embed_node(node)

    def get_node(self, node_id: str) -> Node | None:
        """Retrieve a single node by ID."""
        row = self._get_db().execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        return Node.from_dict(dict(row)) if row else None

    def get_nodes_by_kind(self, kind: NodeKind, session_id: str | None = None) -> list[Node]:
        """Return all nodes of ``kind``, optionally filtered to one session."""
        db = self._get_db()
        if session_id:
            rows = db.execute(
                "SELECT * FROM nodes WHERE kind = ? AND session_id = ?"
                " ORDER BY turn_index, created_at",
                (str(kind), session_id),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM nodes WHERE kind = ? ORDER BY turn_index, created_at",
                (str(kind),),
            ).fetchall()
        return [Node.from_dict(dict(r)) for r in rows]

    def get_all_turns(self, session_id: str | None = None) -> list[Node]:
        """Return Turn nodes ordered by turn_index."""
        return self.get_nodes_by_kind(NodeKind.TURN, session_id=session_id)

    def get_open_tasks(self) -> list[Node]:
        """Return all Task nodes with status = 'open'."""
        rows = (
            self._get_db()
            .execute(
                "SELECT * FROM nodes WHERE kind = ? AND status = 'open' ORDER BY created_at",
                (str(NodeKind.TASK),),
            )
            .fetchall()
        )
        return [Node.from_dict(dict(r)) for r in rows]

    def update_node_field(self, node_id: str, field: str, value: Any) -> None:
        """Update a single field on an existing node."""
        db = self._get_db()
        db.execute(
            f"UPDATE nodes SET {field} = ?, updated_at = ? WHERE id = ?",
            (value, datetime.now(UTC).isoformat(), node_id),
        )
        db.commit()

    def delete_nodes(self, node_ids: list[str]) -> None:
        """Delete nodes (CASCADE removes their edges) from SQLite + vector store."""
        if not node_ids:
            return
        db = self._get_db()
        placeholders = ",".join(["?"] * len(node_ids))
        db.execute(f"DELETE FROM nodes WHERE id IN ({placeholders})", node_ids)
        db.commit()
        try:
            self._get_backend().delete_ids(node_ids)
        except Exception:
            pass

    def find_similar_node(self, text: str, kind: NodeKind, threshold: float = 0.88) -> Node | None:
        """Return an existing node of ``kind`` whose embedding is within
        ``threshold`` cosine similarity of ``text``, or None.

        Falls back to exact-label SQLite match when the vector index is
        empty (e.g. after ``--no-embed`` ingestion), ensuring deduplication
        works even before the first consolidation pass.

        Used for entity/topic deduplication during ingest.
        """
        # Fast path: exact label match in SQLite (works even with an empty index)
        row = (
            self._get_db()
            .execute(
                "SELECT * FROM nodes WHERE kind = ?"
                " AND LOWER(TRIM(label)) = LOWER(TRIM(?)) LIMIT 1",
                (str(kind), text),
            )
            .fetchone()
        )
        if row:
            return Node.from_dict(dict(row))

        # Semantic path: cosine similarity via the sqlite-vec store.  Both
        # backends report cosine ``_distance``, so the similarity conversion
        # below is unchanged from the LanceDB implementation.
        try:
            backend = self._get_backend()
            vector = self.embed(text)
            results = backend.search(vector, 1, where=f"kind = '{kind}'")
            if not results:
                return None
            distance = results[0].get("_distance", 1.0)
            similarity = 1.0 - distance
            if similarity >= threshold:
                return self.get_node(results[0]["id"])
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Edge CRUD
    # ------------------------------------------------------------------

    def add_edge(self, edge: Edge) -> None:
        """Insert an edge; silently ignored if it already exists."""
        db = self._get_db()
        d = edge.to_dict()
        cols = ", ".join(d.keys())
        placeholders = ", ".join(["?"] * len(d))
        db.execute(
            f"INSERT OR IGNORE INTO edges ({cols}) VALUES ({placeholders})", list(d.values())
        )
        db.commit()

    def get_edges(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        relation: str | None = None,
    ) -> list[Edge]:
        """Query edges; all parameters are optional AND-combined filters."""
        db = self._get_db()
        conditions, params = [], []
        if source_id:
            conditions.append("source_id = ?")
            params.append(source_id)
        if target_id:
            conditions.append("target_id = ?")
            params.append(target_id)
        if relation:
            conditions.append("relation = ?")
            params.append(relation)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = db.execute(f"SELECT * FROM edges {where}", params).fetchall()
        return [_row_to_edge(dict(r)) for r in rows]

    # ------------------------------------------------------------------
    # Semantic search (the `index` interface)
    # ------------------------------------------------------------------

    def search(
        self, query: str, k: int = 8, kind_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """Semantic search over embedded nodes.

        :param query: Natural-language query string.
        :param k: Maximum results to return.
        :param kind_filter: Restrict to a specific node kind string.
        :return: List of ``{node_id, kind, text, session_id, score}`` dicts.
        """
        try:
            backend = self._get_backend()
            vector = self.embed(query)
            where = f"kind = '{kind_filter}'" if kind_filter else None
            results = backend.search(vector, k * 3, where=where)
            hits = []
            for r in results:
                hits.append(
                    {
                        "node_id": r["id"],
                        "kind": r["kind"],
                        "text": r["text"],
                        "session_id": r.get("session_id") or "",
                        "score": float(max(0.0, 1.0 - r.get("_distance", 1.0))),
                    }
                )
                if len(hits) >= k:
                    break
            return hits
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        """Return node count, edge count, and per-kind breakdown."""
        db = self._get_db()
        node_count = db.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        edge_count = db.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        kind_counts: dict[str, int] = {}
        for row in db.execute("SELECT kind, COUNT(*) FROM nodes GROUP BY kind"):
            kind_counts[row[0]] = row[1]
        return {
            "node_count": node_count,
            "nodes": node_count,
            "edge_count": edge_count,
            "edges": edge_count,
            "kind_counts": kind_counts,
            "kind": "agent",
        }

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def upsert_session(
        self,
        session_id: str,
        start_time: str,
        end_time: str | None = None,
        turn_count: int = 0,
        pruning_passes: int = 0,
    ) -> None:
        """Insert or update a session record."""
        db = self._get_db()
        db.execute(
            """INSERT OR REPLACE INTO sessions
               (id, start_time, end_time, turn_count, pruning_passes)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, start_time, end_time, turn_count, pruning_passes),
        )
        db.commit()

    def get_session(self, session_id: str) -> dict | None:
        """Return a session record dict or None."""
        row = (
            self._get_db().execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        )
        return dict(row) if row else None

    def list_sessions(self) -> list[dict]:
        """Return all sessions ordered by start_time."""
        rows = self._get_db().execute("SELECT * FROM sessions ORDER BY start_time").fetchall()
        return [dict(r) for r in rows]

    def latest_open_session(self, within_hours: float = 4.0) -> dict | None:
        """Return the most recent open session started within ``within_hours``, or None.

        An "open" session has no ``end_time`` recorded (the CLI hook closed it)
        **or** was started recently enough that the agent is likely still in the
        same Claude Code session.  This lets the ``ingest`` command resume an
        existing session rather than fragmenting into a new one on every hook
        invocation.

        :param within_hours: Only consider sessions started within this many hours.
        :return: Session dict or None.
        """
        cutoff = (datetime.now(UTC) - timedelta(hours=within_hours)).isoformat()
        row = (
            self._get_db()
            .execute(
                """SELECT * FROM sessions
               WHERE start_time >= ?
               ORDER BY start_time DESC
               LIMIT 1""",
                (cutoff,),
            )
            .fetchone()
        )
        return dict(row) if row else None

    def increment_session_turns(self, session_id: str) -> None:
        """Atomically increment turn_count for a session."""
        self._get_db().execute(
            "UPDATE sessions SET turn_count = turn_count + 1 WHERE id = ?", (session_id,)
        )
        self._get_db().commit()

    def increment_session_prune_passes(self, session_id: str) -> None:
        """Atomically increment pruning_passes for a session."""
        self._get_db().execute(
            "UPDATE sessions SET pruning_passes = pruning_passes + 1 WHERE id = ?", (session_id,)
        )
        self._get_db().commit()

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def refresh_related_to_edges(self, threshold: float = 0.75) -> int:
        """Re-compute RELATED_TO edges between Topic nodes.

        Returns the number of new edges created.
        """
        topics = self.get_nodes_by_kind(NodeKind.TOPIC)
        if len(topics) < 2:
            return 0
        try:
            self._get_backend()
        except Exception:
            return 0
        created = 0
        for i, t1 in enumerate(topics):
            for t2 in topics[i + 1 :]:
                v1 = self.embed(t1.label or t1.text)
                v2 = self.embed(t2.label or t2.text)
                sim = float(sum(a * b for a, b in zip(v1, v2)))
                if sim >= threshold:
                    edge = Edge(
                        source_id=t1.id,
                        target_id=t2.id,
                        relation=EdgeRelation.RELATED_TO,
                        weight=sim,
                    )
                    self.add_edge(edge)
                    created += 1
        return created

    def close(self) -> None:
        """Close all open database connections."""
        if self._db:
            self._db.close()
            self._db = None
        if self._backend is not None:
            try:
                self._backend.close()
            except Exception:
                pass
            self._backend = None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _row_to_edge(r: dict) -> Edge:
    try:
        relation = EdgeRelation(r["relation"])
    except ValueError:
        relation = r["relation"]
    return Edge(
        id=r["id"],
        source_id=r["source_id"],
        target_id=r["target_id"],
        relation=relation,
        weight=r.get("weight", 1.0),
        metadata=__import__("json").loads(r.get("metadata", "{}")),
        created_at=datetime.fromisoformat(r.get("created_at", datetime.now(UTC).isoformat())),
    )
