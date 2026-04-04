# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""Unit tests for agent_kg.ingest — SQLite-only path (embed=False)."""

import pytest

from agent_kg.ingest import IngestResult, ingest_turn
from agent_kg.schema import EdgeRelation, NodeKind, TaskStatus
from agent_kg.session import Session
from agent_kg.store import AgentKGStore


@pytest.fixture
def store(tmp_path):
    """Fresh store for each test."""
    s = AgentKGStore(
        db_path=tmp_path / "test.db",
        lancedb_dir=tmp_path / "lance",
    )
    yield s
    s.close()


@pytest.fixture
def session(store):
    """Active session backed by the test store."""
    return Session.open(store, session_id="test-session")


def ingest(text, role, session, store):
    """Helper: ingest with embed disabled."""
    return ingest_turn(text, role, session, store, embed=False)


# ---------------------------------------------------------------------------
# IngestResult
# ---------------------------------------------------------------------------


class TestIngestResult:
    """IngestResult dataclass."""

    def test_defaults(self):
        """IngestResult starts empty."""
        r = IngestResult()
        assert r.turn_node is None
        assert r.intent_node is None
        assert r.topic_nodes == []
        assert r.entity_nodes == []
        assert r.task_nodes == []
        assert r.edges_created == 0
        assert r.profile_updates == []

    def test_repr(self):
        """__repr__ contains expected counters."""
        r = IngestResult()
        text = repr(r)
        assert "topics=0" in text
        assert "tasks=0" in text


# ---------------------------------------------------------------------------
# ingest_turn — basic node creation
# ---------------------------------------------------------------------------


class TestIngestTurnNodes:
    """Turn and intent nodes are created for every ingested message."""

    def test_creates_turn_node(self, store, session):
        """ingest_turn creates a TURN node in the store."""
        ingest("Hello, how are you?", "user", session, store)
        turns = store.get_all_turns()
        assert len(turns) == 1
        assert turns[0].kind == NodeKind.TURN

    def test_turn_node_role(self, store, session):
        """Turn node role matches the role argument."""
        ingest("Fix this bug.", "user", session, store)
        turns = store.get_all_turns()
        assert turns[0].role == "user"

    def test_assistant_turn_role(self, store, session):
        """Assistant turns are stored with role='assistant'."""
        ingest("Sure, here's the fix.", "assistant", session, store)
        turns = store.get_all_turns()
        assert turns[0].role == "assistant"

    def test_creates_intent_node(self, store, session):
        """An INTENT node is created for each turn."""
        result = ingest("What does this class do?", "user", session, store)
        assert result.intent_node is not None
        assert result.intent_node.kind == NodeKind.INTENT

    def test_turn_index_increments(self, store, session):
        """Successive turns get increasing turn_index values."""
        ingest("Turn zero.", "user", session, store)
        ingest("Turn one.", "user", session, store)
        turns = store.get_all_turns()
        indices = sorted(t.turn_index for t in turns)
        assert indices == [0, 1]

    def test_session_id_on_turn(self, store, session):
        """Turn node carries the session ID."""
        ingest("Hello.", "user", session, store)
        turns = store.get_all_turns()
        assert turns[0].session_id == "test-session"

    def test_result_turn_node(self, store, session):
        """IngestResult.turn_node points to the created turn."""
        result = ingest("Hi.", "user", session, store)
        assert result.turn_node is not None
        assert result.turn_node.kind == NodeKind.TURN


# ---------------------------------------------------------------------------
# ingest_turn — FOLLOWS edges
# ---------------------------------------------------------------------------


class TestFollowsEdges:
    """Consecutive turns are linked with FOLLOWS edges."""

    def test_first_turn_no_follows_edge(self, store, session):
        """First turn has no FOLLOWS edge (no predecessor)."""
        result = ingest("First turn.", "user", session, store)
        edges = store.get_edges(
            target_id=result.turn_node.id,
            relation=str(EdgeRelation.FOLLOWS),
        )
        assert edges == []

    def test_second_turn_follows_first(self, store, session):
        """A FOLLOWS edge links the first turn to the second (source → target)."""
        r1 = ingest("First.", "user", session, store)
        r2 = ingest("Second.", "user", session, store)
        # FOLLOWS is stored as r1 → r2 (predecessor points to successor)
        edges = store.get_edges(
            source_id=r1.turn_node.id,
            relation=str(EdgeRelation.FOLLOWS),
        )
        assert len(edges) == 1
        assert edges[0].target_id == r2.turn_node.id


# ---------------------------------------------------------------------------
# ingest_turn — topics and entities
# ---------------------------------------------------------------------------


class TestTopicsAndEntities:
    """Topic and entity nodes are extracted and linked."""

    def test_code_topics_extracted(self, store, session):
        """Text mentioning code keywords produces topic nodes."""
        result = ingest("Refactor the Docker API endpoint.", "user", session, store)
        assert len(result.topic_nodes) >= 1

    def test_entity_import_extracted(self, store, session):
        """'import requests' produces an entity node."""
        result = ingest("import requests", "user", session, store)
        entity_labels = [e.label for e in result.entity_nodes]
        assert "requests" in entity_labels, f"Expected 'requests' in {entity_labels}"

    def test_topics_linked_to_turn(self, store, session):
        """Topic nodes have ADDRESSES edges from the turn."""
        result = ingest("Refactor the database schema.", "user", session, store)
        if result.topic_nodes:
            edges = store.get_edges(
                source_id=result.turn_node.id,
                relation=str(EdgeRelation.ADDRESSES),
            )
            assert len(edges) >= 1

    def test_entities_linked_to_turn(self, store, session):
        """Entity nodes have MENTIONS edges from the turn."""
        result = ingest("import os and import sys", "user", session, store)
        if result.entity_nodes:
            edges = store.get_edges(
                source_id=result.turn_node.id,
                relation=str(EdgeRelation.MENTIONS),
            )
            assert len(edges) >= 1


# ---------------------------------------------------------------------------
# ingest_turn — task extraction
# ---------------------------------------------------------------------------


class TestTaskExtraction:
    """Imperative requests create TASK nodes."""

    def test_imperative_creates_task(self, store, session):
        """'Fix the bug' creates a task node."""
        result = ingest("Fix the authentication bug in login.py.", "user", session, store)
        assert len(result.task_nodes) >= 1

    def test_task_status_is_open(self, store, session):
        """Extracted tasks start with status=open."""
        result = ingest("Implement the retry logic.", "user", session, store)
        for task in result.task_nodes:
            assert task.status == str(TaskStatus.OPEN)

    def test_task_linked_to_turn(self, store, session):
        """Task nodes have CREATES edges from the turn."""
        result = ingest("Create a migration script for the new schema.", "user", session, store)
        if result.task_nodes:
            edges = store.get_edges(
                source_id=result.turn_node.id,
                relation=str(EdgeRelation.CREATES),
            )
            assert len(edges) >= 1

    def test_assistant_turn_no_tasks(self, store, session):
        """Assistant turns do not produce task nodes."""
        result = ingest("Here is the implementation.", "assistant", session, store)
        assert result.task_nodes == []


# ---------------------------------------------------------------------------
# ingest_turn — profile updates
# ---------------------------------------------------------------------------


class TestProfileUpdates:
    """User-turn preference/commitment signals are reported."""

    def test_preference_in_user_turn(self, store, session):
        """'I prefer concise responses' shows up in profile_updates."""
        result = ingest("I prefer concise responses.", "user", session, store)
        assert len(result.profile_updates) >= 1

    def test_no_profile_updates_for_assistant(self, store, session):
        """Assistant turns do not generate profile updates."""
        result = ingest("I prefer verbose output.", "assistant", session, store)
        assert result.profile_updates == []


# ---------------------------------------------------------------------------
# ingest_turn — entity deduplication
# ---------------------------------------------------------------------------


class TestEntityDeduplication:
    """Re-mentioning an entity reuses the existing node."""

    def test_repeated_entity_not_duplicated(self, store, session):
        """Same import mentioned in two turns creates only one entity node."""
        ingest("import requests", "user", session, store)
        ingest("Use requests to call the API.", "user", session, store)
        entities = store.get_nodes_by_kind(NodeKind.ENTITY)
        req_entities = [e for e in entities if e.label == "requests"]
        assert len(req_entities) == 1
