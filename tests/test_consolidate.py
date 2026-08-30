# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""Unit tests for agent_kg.consolidate — should_consolidate and task-status logic."""

import pytest

from agent_kg.consolidate import _CONSOLIDATE_THRESHOLD, should_consolidate
from agent_kg.ingest import ingest_turn
from agent_kg.session import Session
from agent_kg.store import AgentKGStore


@pytest.fixture
def store(tmp_path):
    """Fresh store for each test."""
    s = AgentKGStore(
        db_path=tmp_path / "test.db",
        vectors_path=tmp_path / "vectors.sqlite",
    )
    yield s
    s.close()


@pytest.fixture
def session(store):
    """Active session for the test store."""
    return Session.open(store, session_id="test-session")


def _add_turns(store, session, n: int) -> None:
    """Ingest n plain turns without embedding."""
    for i in range(n):
        ingest_turn(f"Turn {i}", "user", session, store, embed=False)


class TestShouldConsolidate:
    """should_consolidate() — threshold check."""

    def test_empty_store_false(self, store):
        """Empty store does not need consolidation."""
        assert should_consolidate(store) is False

    def test_below_threshold_false(self, store, session):
        """Fewer turns than the threshold returns False."""
        _add_turns(store, session, _CONSOLIDATE_THRESHOLD - 1)
        assert should_consolidate(store) is False

    def test_at_threshold_true(self, store, session):
        """Exactly threshold turns triggers consolidation."""
        _add_turns(store, session, _CONSOLIDATE_THRESHOLD)
        assert should_consolidate(store) is True

    def test_above_threshold_true(self, store, session):
        """More turns than the threshold returns True."""
        _add_turns(store, session, _CONSOLIDATE_THRESHOLD + 5)
        assert should_consolidate(store) is True

    def test_session_filter_below(self, store, session):
        """should_consolidate with session_id only counts that session's turns."""
        # Add enough turns globally but split across two sessions
        sess_b = Session.open(store, session_id="session-b")
        half = _CONSOLIDATE_THRESHOLD // 2
        _add_turns(store, session, half)
        _add_turns(store, sess_b, half)
        # Neither session alone exceeds threshold (assuming threshold > half)
        assert should_consolidate(store, session_id="test-session") is False

    def test_threshold_value(self):
        """The threshold constant is a positive integer."""
        assert isinstance(_CONSOLIDATE_THRESHOLD, int)
        assert _CONSOLIDATE_THRESHOLD > 0


# ---------------------------------------------------------------------------
# Prune session scoping
#
# Regression coverage: prune read store.get_all_turns() with no session filter,
# so a compaction in one session compressed a concurrent session's turns into
# its own summary clusters.
# ---------------------------------------------------------------------------


def _seed_turns(store, session_id, count, prefix):
    """Insert ``count`` turns for a session, bypassing ingest."""
    from agent_kg.schema import Node, NodeKind

    for i in range(count):
        store.upsert_node(
            Node(
                kind=NodeKind.TURN,
                label=f"{prefix} {i}",
                text=f"{prefix} turn number {i} with enough words to be worth pruning",
                role="user" if i % 2 == 0 else "assistant",
                turn_index=i,
                token_count=12,
                session_id=session_id,
            )
        )


def test_prune_scoped_to_session_leaves_other_sessions_alone(tmp_path):
    """A scoped prune must not touch a concurrent session's turns."""
    from agent_kg.prune import prune
    from agent_kg.store import AgentKGStore
    from agent_kg.summarize import Summarizer, SummarizerConfig

    store = AgentKGStore(db_path=tmp_path / "t.db", vectors_path=tmp_path / "v.sqlite")
    try:
        _seed_turns(store, "mine", 30, "mine")
        _seed_turns(store, "theirs", 30, "theirs")
        summarizer = Summarizer(SummarizerConfig(backend="extractive"))

        prune(store, summarizer, window=5, session_id="mine")

        theirs = store.get_all_turns(session_id="theirs")
        assert len(theirs) == 30, "a concurrent session's turns must survive"
    finally:
        store.close()


def test_unscoped_prune_still_spans_sessions(tmp_path):
    """Omitting the scope keeps the previous repo-wide behaviour."""
    from agent_kg.prune import prune
    from agent_kg.store import AgentKGStore
    from agent_kg.summarize import Summarizer, SummarizerConfig

    store = AgentKGStore(db_path=tmp_path / "t.db", vectors_path=tmp_path / "v.sqlite")
    try:
        _seed_turns(store, "mine", 30, "mine")
        _seed_turns(store, "theirs", 30, "theirs")
        summarizer = Summarizer(SummarizerConfig(backend="extractive"))

        report = prune(store, summarizer, window=5)

        assert report.turns_pruned > 0
        remaining = len(store.get_all_turns())
        assert remaining < 60
    finally:
        store.close()
