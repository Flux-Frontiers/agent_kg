"""index.py — ConversationIndex: LanceDB-backed semantic index for conversation nodes."""
# pylint: disable=import-outside-toplevel

from __future__ import annotations

from pathlib import Path
from typing import Any

from kg_utils.embed import DEFAULT_MODEL as DEFAULT_MODEL  # noqa: F401 — re-exported

_EMBED_DIM = 384


class ConversationIndex:
    """LanceDB-backed semantic index for conversation nodes.

    Provides a standalone, named LanceDB table (``"conversation"``) that
    can be used independently of :class:`~agent_kg.store.AgentKGStore` or
    composed with it for additional indexing flexibility.

    :param lancedb_dir: Directory where LanceDB tables are stored.
    :param model_name: Sentence-transformer model name for embedding.
    """

    TABLE = "conversation"

    def __init__(self, lancedb_dir: Path, model_name: str = DEFAULT_MODEL) -> None:
        self.lancedb_dir = Path(lancedb_dir)
        self.lancedb_dir.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        self._db: Any = None
        self._table: Any = None
        self._embedder: Any = None

    def _get_embedder(self) -> Any:
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415

            self._embedder = SentenceTransformer(self.model_name)
        return self._embedder

    def _get_db(self) -> Any:
        if self._db is None:
            import lancedb  # noqa: PLC0415

            self._db = lancedb.connect(str(self.lancedb_dir))
        return self._db

    def _get_table(self, create: bool = False) -> Any:
        if self._table is not None:
            return self._table
        db = self._get_db()
        names = db.table_names()
        if self.TABLE in names:
            self._table = db.open_table(self.TABLE)
        elif create:
            import pyarrow as pa  # noqa: PLC0415

            schema = pa.schema(
                [
                    pa.field("node_id", pa.utf8()),
                    pa.field("kind", pa.utf8()),
                    pa.field("text", pa.utf8()),
                    pa.field("session_id", pa.utf8()),
                    pa.field("vector", pa.list_(pa.float32(), _EMBED_DIM)),
                ]
            )
            self._table = db.create_table(self.TABLE, schema=schema)
        return self._table

    def add(self, nodes: list[dict]) -> int:
        """Add nodes into the index.

        :param nodes: List of dicts with ``node_id``, ``kind``, ``text``,
            ``session_id`` keys. Falls back to ``id`` / ``label`` if the
            primary keys are absent.
        :return: Number of rows added.
        """
        if not nodes:
            return 0
        table = self._get_table(create=True)
        embedder = self._get_embedder()
        texts = [n.get("text") or n.get("label", "") for n in nodes]
        vecs = embedder.encode(texts, normalize_embeddings=True)
        rows = []
        for node, vec in zip(nodes, vecs):
            rows.append(
                {
                    "node_id": node.get("node_id") or node.get("id", ""),
                    "kind": node.get("kind", ""),
                    "text": node.get("text") or node.get("label", ""),
                    "session_id": node.get("session_id") or "",
                    "vector": vec.tolist(),
                }
            )
        table.add(rows)
        return len(rows)

    def search(self, query: str, k: int = 10, session_id: str | None = None) -> list[dict]:
        """Semantic search over indexed nodes.

        :param query: Natural language query string.
        :param k: Maximum number of results to return.
        :param session_id: Optional session filter; when set only nodes from
            that session are returned.
        :return: List of result dicts with ``node_id``, ``score``, ``kind``,
            ``text``, ``session_id`` keys.
        """
        table = self._get_table(create=False)
        if table is None:
            return []
        embedder = self._get_embedder()
        vec = embedder.encode([query], normalize_embeddings=True)[0].tolist()
        q = table.search(vec).limit(k)
        if session_id:
            q = q.where(f"session_id = {session_id!r}")
        results = q.to_list()
        out = []
        for r in results:
            out.append(
                {
                    "node_id": r["node_id"],
                    "kind": r["kind"],
                    "text": r["text"],
                    "session_id": r["session_id"],
                    "score": float(r.get("_distance", 0.0)),
                }
            )
        return out

    def wipe(self) -> None:
        """Drop the conversation table from LanceDB."""
        db = self._get_db()
        if self.TABLE in db.table_names():
            db.drop_table(self.TABLE)
        self._table = None
