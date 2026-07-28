"""index.py — ConversationIndex: sqlite-vec-backed semantic index for conversation nodes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kg_utils.embed import DEFAULT_MODEL as DEFAULT_MODEL  # noqa: F401 — re-exported

_EMBED_DIM = 384

# Metadata persisted beside each vector.  ``search()`` returns these verbatim,
# so every key a caller reads out of a hit must appear here.
_META_COLUMNS = ("kind", "text", "session_id")


class ConversationIndex:
    """sqlite-vec-backed semantic index for conversation nodes.

    Provides a standalone vector store that can be used independently of
    :class:`~agent_kg.store.AgentKGStore` or composed with it for additional
    indexing flexibility.

    :param vectors_path: Path to the sqlite-vec vector store file.
    :param model_name: Sentence-transformer model name for embedding.
    """

    def __init__(self, vectors_path: Path, model_name: str = DEFAULT_MODEL) -> None:
        self.vectors_path = Path(vectors_path)
        self.vectors_path.parent.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        self._backend: Any = None
        self._embedder: Any = None

    def _get_embedder(self) -> Any:
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer

            self._embedder = SentenceTransformer(self.model_name)
        return self._embedder

    def _get_backend(self, create: bool = False) -> Any:
        """Return the open backend, or ``None`` when the store does not exist.

        :param create: Create the store if it is not already present.
        :return: An open ``SqliteVecBackend``, or ``None``.
        """
        if self._backend is not None:
            return self._backend
        if not create and not self.vectors_path.exists():
            return None
        from kg_utils.vector_backend import SqliteVecBackend

        backend = SqliteVecBackend(self.vectors_path, dim=_EMBED_DIM, meta_columns=_META_COLUMNS)
        backend.open()
        self._backend = backend
        return self._backend

    def add(self, nodes: list[dict]) -> int:
        """Add nodes into the index.

        :param nodes: List of dicts with ``node_id``, ``kind``, ``text``,
            ``session_id`` keys. Falls back to ``id`` / ``label`` if the
            primary keys are absent.
        :return: Number of rows added.
        """
        if not nodes:
            return 0
        backend = self._get_backend(create=True)
        embedder = self._get_embedder()
        texts = [n.get("text") or n.get("label", "") for n in nodes]
        vecs = embedder.encode(texts, normalize_embeddings=True)
        rows = []
        for node, vec in zip(nodes, vecs, strict=False):
            rows.append(
                {
                    "id": node.get("node_id") or node.get("id", ""),
                    "kind": node.get("kind", ""),
                    "text": node.get("text") or node.get("label", ""),
                    "session_id": node.get("session_id") or "",
                    "vector": vec.tolist(),
                }
            )
        backend.upsert(rows)
        return len(rows)

    def search(self, query: str, k: int = 10, session_id: str | None = None) -> list[dict]:
        """Semantic search over indexed nodes.

        ``score`` is the raw distance reported by the backend (lower is closer),
        preserving the previous contract of surfacing ``_distance`` directly.
        Note the underlying metric changed with the sqlite-vec move: the old
        LanceDB table was queried without an explicit metric and so returned
        L2, whereas sqlite-vec reports cosine.

        :param query: Natural language query string.
        :param k: Maximum number of results to return.
        :param session_id: Optional session filter; when set only nodes from
            that session are returned.
        :return: List of result dicts with ``node_id``, ``score``, ``kind``,
            ``text``, ``session_id`` keys.
        """
        backend = self._get_backend(create=False)
        if backend is None:
            return []
        embedder = self._get_embedder()
        vec = embedder.encode([query], normalize_embeddings=True)[0].tolist()
        where = f"session_id = {session_id!r}" if session_id else None
        results = backend.search(vec, k, where=where)
        out = []
        for r in results:
            out.append(
                {
                    "node_id": r["id"],
                    "kind": r["kind"],
                    "text": r["text"],
                    "session_id": r["session_id"],
                    "score": float(r.get("_distance", 0.0)),
                }
            )
        return out

    def wipe(self) -> None:
        """Drop and recreate the conversation vector store."""
        backend = self._get_backend(create=True)
        backend.open(wipe=True)
