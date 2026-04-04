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
        lancedb_dir=tmp_path / "lance",
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
