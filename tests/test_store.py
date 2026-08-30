# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""Unit tests for agent_kg.store.AgentKGStore — SQLite-only operations.

Tests only exercise operations that go through SQLite, avoiding the
sqlite-vec / sentence-transformers embedding path.
"""

import pytest

from agent_kg.schema import Edge, EdgeRelation, Node, NodeKind, TaskStatus
from agent_kg.store import AgentKGStore


@pytest.fixture
def store(tmp_path):
    """Fresh in-temp-dir AgentKGStore for each test."""
    s = AgentKGStore(
        db_path=tmp_path / "test.db",
        vectors_path=tmp_path / "vectors.sqlite",
    )
    yield s
    s.close()


# ---------------------------------------------------------------------------
# Node CRUD
# ---------------------------------------------------------------------------


class TestNodeCRUD:
    """upsert_node, get_node, get_nodes_by_kind, delete_nodes."""

    def test_upsert_and_get(self, store):
        """A node can be inserted and retrieved by ID."""
        node = Node(kind=NodeKind.TURN, label="hello", text="Hello world", session_id="s1")
        store.upsert_node(node)
        fetched = store.get_node(node.id)
        assert fetched is not None
        assert fetched.id == node.id
        assert fetched.label == "hello"
        assert fetched.text == "Hello world"

    def test_get_nonexistent_returns_none(self, store):
        """get_node returns None for unknown IDs."""
        assert store.get_node("nonexistent-id") is None

    def test_upsert_is_idempotent(self, store):
        """Upserting the same node twice does not duplicate it."""
        node = Node(kind=NodeKind.TOPIC, label="docker")
        store.upsert_node(node)
        store.upsert_node(node)
        nodes = store.get_nodes_by_kind(NodeKind.TOPIC)
        assert len(nodes) == 1

    def test_get_nodes_by_kind_empty(self, store):
        """get_nodes_by_kind returns [] when no nodes of that kind exist."""
        assert store.get_nodes_by_kind(NodeKind.SUMMARY) == []

    def test_get_nodes_by_kind_multiple(self, store):
        """get_nodes_by_kind returns all nodes of the given kind."""
        store.upsert_node(Node(kind=NodeKind.TOPIC, label="api"))
        store.upsert_node(Node(kind=NodeKind.TOPIC, label="docker"))
        store.upsert_node(Node(kind=NodeKind.TURN, label="turn1"))
        topics = store.get_nodes_by_kind(NodeKind.TOPIC)
        assert len(topics) == 2
        labels = {t.label for t in topics}
        assert labels == {"api", "docker"}

    def test_get_nodes_by_kind_session_filter(self, store):
        """get_nodes_by_kind with session_id filters correctly."""
        store.upsert_node(Node(kind=NodeKind.TURN, label="t1", session_id="A"))
        store.upsert_node(Node(kind=NodeKind.TURN, label="t2", session_id="B"))
        a_turns = store.get_nodes_by_kind(NodeKind.TURN, session_id="A")
        assert len(a_turns) == 1
        assert a_turns[0].label == "t1"

    def test_delete_nodes(self, store):
        """Deleted nodes are no longer retrievable."""
        node = Node(kind=NodeKind.TURN, label="to-delete")
        store.upsert_node(node)
        assert store.get_node(node.id) is not None
        store.delete_nodes([node.id])
        assert store.get_node(node.id) is None

    def test_delete_nonexistent_is_safe(self, store):
        """Deleting a non-existent ID does not raise."""
        store.delete_nodes(["ghost-id"])  # should not raise

    def test_update_node_field(self, store):
        """update_node_field changes a single field."""
        node = Node(kind=NodeKind.TASK, label="task", status=str(TaskStatus.OPEN))
        store.upsert_node(node)
        store.update_node_field(node.id, "status", str(TaskStatus.COMPLETED))
        updated = store.get_node(node.id)
        assert updated.status == str(TaskStatus.COMPLETED)

    def test_get_all_turns(self, store):
        """get_all_turns returns only TURN nodes."""
        store.upsert_node(Node(kind=NodeKind.TURN, label="t1", session_id="s"))
        store.upsert_node(Node(kind=NodeKind.TOPIC, label="topic"))
        turns = store.get_all_turns()
        assert len(turns) == 1
        assert turns[0].kind == NodeKind.TURN

    def test_get_all_turns_session_filter(self, store):
        """get_all_turns(session_id=...) filters by session."""
        store.upsert_node(Node(kind=NodeKind.TURN, label="t1", session_id="A"))
        store.upsert_node(Node(kind=NodeKind.TURN, label="t2", session_id="B"))
        assert len(store.get_all_turns(session_id="A")) == 1
        assert len(store.get_all_turns(session_id="B")) == 1
        assert len(store.get_all_turns()) == 2

    def test_get_open_tasks(self, store):
        """get_open_tasks returns only TASK nodes with status=open."""
        store.upsert_node(Node(kind=NodeKind.TASK, label="open-t", status=str(TaskStatus.OPEN)))
        store.upsert_node(
            Node(kind=NodeKind.TASK, label="done-t", status=str(TaskStatus.COMPLETED))
        )
        open_tasks = store.get_open_tasks()
        assert len(open_tasks) == 1
        assert open_tasks[0].label == "open-t"


# ---------------------------------------------------------------------------
# Edge CRUD
# ---------------------------------------------------------------------------


class TestEdgeCRUD:
    """add_edge, get_edges."""

    @staticmethod
    def _nodes(store, *ids):
        """Create the nodes an edge references.

        Foreign keys are enforced, so an edge to a node that does not exist is
        rejected -- which is the point. These tests exercise edge CRUD, not the
        constraint, so they need real endpoints.
        """
        for node_id in ids:
            store.upsert_node(Node(id=node_id, kind=NodeKind.TURN, text=node_id))

    def test_add_and_get_by_source(self, store):
        """An edge can be added and retrieved by source_id."""
        self._nodes(store, "s1", "t1")
        edge = Edge(source_id="s1", target_id="t1", relation=EdgeRelation.FOLLOWS)
        store.add_edge(edge)
        edges = store.get_edges(source_id="s1")
        assert len(edges) == 1
        assert edges[0].source_id == "s1"
        assert edges[0].target_id == "t1"
        assert edges[0].relation == EdgeRelation.FOLLOWS

    def test_add_and_get_by_target(self, store):
        """get_edges by target_id works."""
        self._nodes(store, "s1", "t1")
        edge = Edge(source_id="s1", target_id="t1", relation=EdgeRelation.MENTIONS)
        store.add_edge(edge)
        edges = store.get_edges(target_id="t1")
        assert len(edges) == 1

    def test_get_edges_by_relation(self, store):
        """get_edges with relation filter returns only matching edges."""
        self._nodes(store, "a", "b", "c")
        store.add_edge(Edge(source_id="a", target_id="b", relation=EdgeRelation.FOLLOWS))
        store.add_edge(Edge(source_id="a", target_id="c", relation=EdgeRelation.MENTIONS))
        follows = store.get_edges(source_id="a", relation=str(EdgeRelation.FOLLOWS))
        assert len(follows) == 1
        assert follows[0].relation == EdgeRelation.FOLLOWS

    def test_get_edges_empty(self, store):
        """get_edges returns [] when no matching edges exist."""
        assert store.get_edges(source_id="ghost") == []


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


class TestSessionManagement:
    """upsert_session, get_session, list_sessions, increment helpers."""

    def test_upsert_and_get(self, store):
        """A session can be inserted and retrieved."""
        store.upsert_session(session_id="sess-1", start_time="2026-01-01T00:00:00")
        sess = store.get_session("sess-1")
        assert sess is not None
        assert sess["id"] == "sess-1"

    def test_get_nonexistent_returns_none(self, store):
        """get_session returns None for unknown IDs."""
        assert store.get_session("unknown") is None

    def test_list_sessions_empty(self, store):
        """list_sessions returns [] when no sessions exist."""
        assert store.list_sessions() == []

    def test_list_sessions_multiple(self, store):
        """list_sessions returns all sessions."""
        store.upsert_session("s1", "2026-01-01T00:00:00")
        store.upsert_session("s2", "2026-01-02T00:00:00")
        sessions = store.list_sessions()
        assert len(sessions) == 2
        ids = {s["id"] for s in sessions}
        assert ids == {"s1", "s2"}

    def test_increment_turn_count(self, store):
        """increment_session_turns increments turn_count by 1."""
        store.upsert_session("s1", "2026-01-01T00:00:00", turn_count=0)
        store.increment_session_turns("s1")
        store.increment_session_turns("s1")
        sess = store.get_session("s1")
        assert sess["turn_count"] == 2

    def test_increment_prune_passes(self, store):
        """increment_session_prune_passes increments pruning_passes by 1."""
        store.upsert_session("s1", "2026-01-01T00:00:00", pruning_passes=0)
        store.increment_session_prune_passes("s1")
        sess = store.get_session("s1")
        assert sess["pruning_passes"] == 1


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestStats:
    """store.stats() returns aggregate counts."""

    def test_empty_store(self, store):
        """Empty store has zero node and edge counts."""
        s = store.stats()
        assert s["node_count"] == 0
        assert s["edge_count"] == 0

    def test_counts_after_inserts(self, store):
        """node_count and edge_count reflect inserted data."""
        turn = Node(kind=NodeKind.TURN, label="t1")
        topic = Node(kind=NodeKind.TOPIC, label="api")
        store.upsert_node(turn)
        store.upsert_node(topic)
        store.add_edge(Edge(source_id=turn.id, target_id=topic.id, relation=EdgeRelation.FOLLOWS))
        s = store.stats()
        assert s["node_count"] == 2
        assert s["edge_count"] == 1

    def test_kind_counts(self, store):
        """stats returns per-kind breakdown."""
        store.upsert_node(Node(kind=NodeKind.TURN))
        store.upsert_node(Node(kind=NodeKind.TURN))
        store.upsert_node(Node(kind=NodeKind.TOPIC))
        s = store.stats()
        assert s["kind_counts"].get("turn", 0) == 2
        assert s["kind_counts"].get("topic", 0) == 1


# ---------------------------------------------------------------------------
# Vector-index reconciliation (drift detection + reindex)
# ---------------------------------------------------------------------------


class TestMissingEmbeddingIds:
    """SQLite is the source of truth; the vector index is derived and drifts."""

    def test_all_missing_when_nothing_embedded(self, store):
        """Nodes written without embedding are reported as missing."""
        store.upsert_node(Node(kind=NodeKind.TOPIC, label="api"))
        store.upsert_node(Node(kind=NodeKind.TOPIC, label="docker"))
        assert len(store.missing_embedding_ids()) == 2

    def test_empty_when_no_nodes(self, store):
        """An empty graph has no drift."""
        assert store.missing_embedding_ids() == []

    def test_textless_nodes_are_not_reported(self, store):
        """Nodes with no embeddable text can never be indexed.

        Counting them would report drift that no amount of reindexing could
        ever clear.
        """
        store.upsert_node(Node(kind=NodeKind.TOPIC, label="", text=""))
        assert store.missing_embedding_ids() == []


class TestReindex:
    """reindex() backfills only what is missing and converges."""

    @pytest.mark.integration
    def test_reindex_backfills_and_converges(self, store):
        """After reindex the vector store matches SQLite, and re-running is a no-op."""
        pytest.importorskip("sentence_transformers")
        for label in ("alpha", "beta", "gamma"):
            store.upsert_node(Node(kind=NodeKind.TOPIC, label=label))
        assert len(store.missing_embedding_ids()) == 3

        result = store.reindex()
        assert result["scanned"] == 3
        assert result["embedded"] == 3
        assert result["failed"] == 0
        assert store.missing_embedding_ids() == []

        # Idempotent: a second pass finds nothing to do.
        assert store.reindex() == {"scanned": 0, "embedded": 0, "failed": 0}

    def test_reindex_on_empty_graph_is_noop(self, store):
        """reindex() on an empty graph does nothing and does not raise."""
        assert store.reindex() == {"scanned": 0, "embedded": 0, "failed": 0}


class TestEmbedFailureVisibility:
    """Embedding failures must be counted, not silently swallowed."""

    def test_failure_is_counted_and_warned_once(self, store, monkeypatch, capsys):
        """A broken embedder increments the counter and warns exactly once."""

        def _boom(_text):
            raise RuntimeError("model unavailable")

        monkeypatch.setattr(store, "embed", _boom)
        for label in ("one", "two", "three"):
            store.embed_node(Node(kind=NodeKind.TOPIC, label=label))

        assert store.embed_failures == 3
        # Warned once, not once per node.
        assert capsys.readouterr().err.count("embedding unavailable") == 1


# ---------------------------------------------------------------------------
# Referential integrity
#
# The schema always declared ON DELETE CASCADE, but SQLite ignores foreign keys
# unless the pragma is set per connection and it never was. Every node deletion
# since the first release left its edges behind; fleet graphs accumulated
# thousands each.
# ---------------------------------------------------------------------------


class TestReferentialIntegrity:
    """Foreign key enforcement, cascade, and the upsert hazard it creates."""

    @staticmethod
    def _pair(store):
        """Create two connected nodes and return them."""
        a = Node(kind=NodeKind.TURN, label="a", text="a")
        b = Node(kind=NodeKind.TOPIC, label="b", text="b")
        store.upsert_node(a)
        store.upsert_node(b)
        store.add_edge(Edge(source_id=a.id, target_id=b.id, relation=EdgeRelation.MENTIONS))
        return a, b

    def test_deleting_a_node_removes_its_edges(self, store):
        """The declared cascade actually fires."""
        a, _ = self._pair(store)
        assert store.stats()["edge_count"] == 1

        store.delete_nodes([a.id])

        assert store.stats()["edge_count"] == 0

    def test_reupserting_a_node_preserves_its_edges(self, store):
        """Updating a node must not take its edges with it.

        INSERT OR REPLACE deletes the row before reinserting, which fires the
        cascade. Ingest re-upserts topic and entity nodes on almost every turn,
        so using it here would erase the graph's structure continuously.
        """
        a, b = self._pair(store)

        a.text = "updated text"
        store.upsert_node(a)

        assert store.stats()["edge_count"] == 1
        assert store.get_node(a.id).text == "updated text"

    def test_edge_to_a_missing_node_is_rejected(self, store):
        """An edge cannot reference a node that does not exist."""
        import sqlite3

        import pytest

        a = Node(kind=NodeKind.TURN, label="a", text="a")
        store.upsert_node(a)

        with pytest.raises(sqlite3.IntegrityError):
            store.add_edge(Edge(source_id=a.id, target_id="ghost", relation=EdgeRelation.MENTIONS))

    def test_existing_dangling_edges_are_purged_on_open(self, tmp_path):
        """Historical damage is cleaned up when the store is next opened."""
        db_path = tmp_path / "legacy.db"

        # Build a graph the old way: foreign keys off, so the delete orphans
        # the edge exactly as every prior release did.
        legacy = AgentKGStore(db_path=db_path, vectors_path=tmp_path / "v.sqlite")
        a, b = self._pair(legacy)
        raw = legacy._get_db()
        raw.execute("PRAGMA foreign_keys = OFF")
        raw.execute("DELETE FROM nodes WHERE id = ?", (a.id,))
        raw.commit()
        assert legacy.stats()["edge_count"] == 1, "setup should leave one orphan"
        legacy.close()

        reopened = AgentKGStore(db_path=db_path, vectors_path=tmp_path / "v.sqlite")
        try:
            assert reopened.stats()["edge_count"] == 0
        finally:
            reopened.close()
