# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""Unit tests for agent_kg.assemble — context assembly and duplicate suppression.

Regression coverage for two defects that reached production graphs:

  1. The exclusion set guarding "Relevant Past Turns" was built from the
     current session while the verbatim section printed across all sessions,
     so the filter was inert for every CLI and hook invocation.
  2. Turn nodes carry no content dedup, so one turn stored under several node
     ids appeared repeatedly in the assembled block, each copy paying budget.
"""

import re

import pytest

from agent_kg.assemble import assemble_context
from agent_kg.schema import Node, NodeKind
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


def _add_turn(store, text, role="user", turn_index=0, session_id="s1"):
    """Insert a Turn node directly, bypassing ingest."""
    node = Node(
        kind=NodeKind.TURN,
        label=text[:80],
        text=text,
        role=role,
        turn_index=turn_index,
        session_id=session_id,
    )
    store.upsert_node(node)
    return node


def _section(block, name):
    """Return the body of a named Markdown section, or '' if absent."""
    m = re.search(rf"^## {name}\n(.*?)(?=^## |\Z)", block, re.S | re.M)
    return m.group(1) if m else ""


def _entries(body):
    """Return the turn texts listed in a section body."""
    return re.findall(r"^\*\*\[[A-Z]+\]\*\* (.+)$", body, re.M)


# ---------------------------------------------------------------------------
# Duplicate suppression
# ---------------------------------------------------------------------------


def test_identical_turns_under_different_ids_appear_once(store):
    """Two nodes with the same text collapse to a single entry."""
    _add_turn(store, "we need to trigger ci again", turn_index=1)
    _add_turn(store, "we need to trigger ci again", turn_index=2)

    block = assemble_context(store, query="ci", budget=4000)

    entries = _entries(_section(block, "Recent Conversation"))
    assert entries.count("we need to trigger ci again") == 1


def test_duplicates_differing_only_in_whitespace_and_case_collapse(store):
    """Normalization catches near-identical repeats, not just exact ones."""
    _add_turn(store, "Deploy the release now", turn_index=1)
    _add_turn(store, "deploy   the  release now", turn_index=2)

    block = assemble_context(store, query="deploy", budget=4000)

    assert len(_entries(_section(block, "Recent Conversation"))) == 1


def test_distinct_turns_are_all_retained(store):
    """Dedup must not swallow genuinely different turns."""
    for i, text in enumerate(["first thing", "second thing", "third thing"]):
        _add_turn(store, text, turn_index=i)

    block = assemble_context(store, query="thing", budget=4000)

    assert len(_entries(_section(block, "Recent Conversation"))) == 3


# ---------------------------------------------------------------------------
# Cross-section exclusion
# ---------------------------------------------------------------------------


def test_recent_turn_not_repeated_in_relevant_past_turns(store, monkeypatch):
    """A turn in the verbatim window must not also be listed as a past turn.

    Reproduces the inert-exclusion bug: the session passed to assemble holds no
    turns of its own, which previously emptied the exclusion set while the
    verbatim section still printed turns from every session.

    The graph holds more turns than the verbatim window, so an old turn can
    legitimately appear under "Relevant Past Turns" while a recent one must
    not. Semantic search is stubbed to return one of each, because these turns
    are stored without embeddings.
    """
    nodes = [
        _add_turn(store, f"recorded turn about oauth number {i}", turn_index=i, session_id="old")
        for i in range(10)
    ]
    oldest, newest = nodes[0], nodes[-1]
    empty_session = Session.open(store, session_id="fresh-session")

    def fake_search(query, k=8, kind_filter=None):
        if kind_filter == str(NodeKind.TURN):
            return [{"node_id": n.id, "score": 0.9} for n in (oldest, newest)]
        return []

    monkeypatch.setattr(store, "search", fake_search)

    block = assemble_context(store, query="oauth", budget=4000, session_id=empty_session.id)

    past = set(_entries(_section(block, "Relevant Past Turns")))
    recent = set(_entries(_section(block, "Recent Conversation")))
    assert oldest.text in past, "an out-of-window hit should still be offered as past context"
    assert newest.text in recent, "the newest turn belongs in the verbatim window"
    assert past & recent == set(), "no turn may appear in both sections"


def test_exclusion_falls_back_to_all_sessions_when_current_is_empty(store):
    """An empty current session must still yield recent context, not nothing."""
    _add_turn(store, "a turn stored under an earlier session", turn_index=0, session_id="old")
    empty_session = Session.open(store, session_id="fresh-session")

    block = assemble_context(store, query="earlier", budget=4000, session_id=empty_session.id)

    assert "a turn stored under an earlier session" in block


def test_current_session_turns_preferred_when_present(store):
    """When the current session has turns, they drive the verbatim window."""
    _add_turn(store, "stale turn from a previous session", turn_index=0, session_id="old")
    _add_turn(store, "live turn in the current session", turn_index=1, session_id="live")

    block = assemble_context(store, query="turn", budget=4000, session_id="live")

    recent = _entries(_section(block, "Recent Conversation"))
    assert recent == ["live turn in the current session"]


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


def test_budget_is_respected(store):
    """Assembly stops adding sections once the budget is exhausted."""
    for i in range(40):
        _add_turn(store, f"turn {i} " + "padding words " * 40, turn_index=i)

    block = assemble_context(store, query="padding", budget=100)

    assert len(block) // 4 <= 200


def test_empty_graph_returns_placeholder(store):
    """An empty graph produces a placeholder rather than an empty string."""
    assert "No conversation context" in assemble_context(store, query="anything")
