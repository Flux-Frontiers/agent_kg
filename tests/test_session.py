# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""Unit tests for agent_kg.session.Session."""

import pytest

from agent_kg.session import Session
from agent_kg.store import AgentKGStore


@pytest.fixture
def store(tmp_path):
    """Fresh in-temp-dir AgentKGStore for each test."""
    s = AgentKGStore(
        db_path=tmp_path / "test.db",
        lancedb_dir=tmp_path / "lance",
    )
    yield s
    s.close()


class TestSessionOpen:
    """Session.open() — factory method."""

    def test_new_session_persisted(self, store):
        """Opening a new session persists it to the store."""
        sess = Session.open(store)
        assert store.get_session(sess.id) is not None

    def test_new_session_has_zero_turns(self, store):
        """A freshly opened session starts with turn_count == 0."""
        sess = Session.open(store)
        assert sess.turn_count == 0

    def test_explicit_session_id(self, store):
        """Session.open respects an explicit session_id."""
        sess = Session.open(store, session_id="my-session")
        assert sess.id == "my-session"

    def test_resume_existing_session(self, store):
        """Opening an existing session_id resumes it."""
        sess1 = Session.open(store, session_id="resume-me")
        sess2 = Session.open(store, session_id="resume-me")
        assert sess1.id == sess2.id


class TestSessionTurnIndex:
    """next_turn_index() — monotonic counter."""

    def test_starts_at_zero(self, store):
        """First call returns 0."""
        sess = Session.open(store)
        assert sess.next_turn_index() == 0

    def test_increments(self, store):
        """Successive calls increment by 1."""
        sess = Session.open(store)
        indices = [sess.next_turn_index() for _ in range(5)]
        assert indices == [0, 1, 2, 3, 4]

    def test_turn_count_property(self, store):
        """turn_count property reflects next_turn_index calls."""
        sess = Session.open(store)
        sess.next_turn_index()
        sess.next_turn_index()
        assert sess.turn_count == 2


class TestSessionPersistence:
    """record_turn, record_prune, close."""

    def test_record_turn_increments_store(self, store):
        """record_turn increments the session's turn_count in the store."""
        sess = Session.open(store, session_id="s1")
        sess.record_turn()
        sess.record_turn()
        db_sess = store.get_session("s1")
        assert db_sess["turn_count"] == 2

    def test_record_prune_increments_store(self, store):
        """record_prune increments the session's pruning_passes in the store."""
        sess = Session.open(store, session_id="s1")
        sess.record_prune()
        db_sess = store.get_session("s1")
        assert db_sess["pruning_passes"] == 1

    def test_close_sets_end_time(self, store):
        """close() writes end_time to the store."""
        sess = Session.open(store, session_id="s1")
        sess.close()
        db_sess = store.get_session("s1")
        assert db_sess.get("end_time") is not None

    def test_repr(self, store):
        """__repr__ includes session ID prefix and turn count."""
        sess = Session.open(store)
        r = repr(sess)
        assert "Session" in r
        assert "turns=0" in r
