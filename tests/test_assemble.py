# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""Unit tests for agent_kg.assemble -- context assembly and recall quality.

Regression coverage for defects that reached production graphs:

  1. The exclusion set guarding "Relevant Past Turns" was built from the
     current session while the verbatim section printed across all sessions,
     so the filter was inert for every CLI and hook invocation.
  2. Turn nodes carry no content dedup, so one turn stored under several node
     ids appeared repeatedly in the assembled block, each copy paying budget.
  3. Recall injected noise measured against a real graph: the caller's own
     live session came back to it, low-relevance hits (turn scores as low as
     0.68, summary scores as low as 0.79) were included with no floor, and
     recalled items carried no date so stale context read as current.
"""

import re
from datetime import UTC, datetime

import pytest

from agent_kg.assemble import assemble_context
from agent_kg.schema import Node, NodeKind
from agent_kg.session import Session
from agent_kg.store import AgentKGStore

# Fixed at local noon UTC so the local-time date is stable regardless of the
# timezone the suite runs in.
_FIXED_DT = datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC)
_FIXED_DATE = _FIXED_DT.astimezone().strftime("%Y-%m-%d")


@pytest.fixture
def store(tmp_path):
    """Fresh store for each test."""
    s = AgentKGStore(
        db_path=tmp_path / "test.db",
        vectors_path=tmp_path / "vectors.sqlite",
    )
    yield s
    s.close()


def _add_turn(store, text, role="user", turn_index=0, session_id="s1", created_at=_FIXED_DT):
    """Insert a Turn node directly, bypassing ingest."""
    node = Node(
        kind=NodeKind.TURN,
        label=text[:80],
        text=text,
        role=role,
        turn_index=turn_index,
        session_id=session_id,
        created_at=created_at,
    )
    store.upsert_node(node)
    return node


def _add_summary(store, text, session_id="s1", created_at=_FIXED_DT):
    """Insert a Summary node directly."""
    node = Node(
        kind=NodeKind.SUMMARY,
        label=text[:80],
        text=text,
        session_id=session_id,
        created_at=created_at,
    )
    store.upsert_node(node)
    return node


def _add_open_task(store, label, created_at=_FIXED_DT):
    """Insert an open Task node directly."""
    node = Node(kind=NodeKind.TASK, label=label, status="open", created_at=created_at)
    store.upsert_node(node)
    return node


def _section(block, name):
    """Return the body of a named Markdown section, or '' if absent."""
    m = re.search(rf"^## {re.escape(name)}\n(.*?)(?=^## |\Z)", block, re.S | re.M)
    return m.group(1) if m else ""


def _entries(body):
    """Return the turn texts listed in a section body (date prefix stripped)."""
    return re.findall(r"^\*\*\[[A-Z]+\]\*\* \(\d{4}-\d{2}-\d{2}\) (.+)$", body, re.M)


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


# ---------------------------------------------------------------------------
# Live-session exclusion
# ---------------------------------------------------------------------------


def test_live_session_has_no_recent_conversation_section(store):
    """When the current session already has turns, it is 'live' and is never
    echoed back as "Recent Conversation" -- the model already has those turns.

    Inverts the old test_current_session_turns_preferred_when_present, which
    asserted the opposite (that a live session's turns should drive the
    verbatim window).
    """
    _add_turn(store, "stale turn from a previous session", turn_index=0, session_id="old")
    _add_turn(store, "live turn in the current session", turn_index=1, session_id="live")

    block = assemble_context(store, query="turn", budget=4000, session_id="live")

    assert _section(block, "Recent Conversation") == ""
    assert "live turn in the current session" not in block


def test_live_session_turns_excluded_even_when_search_returns_them(store, monkeypatch):
    """A live session's own turns must never be recalled, even at score 1.0.

    This includes the just-ingested current prompt, which search can return
    as a near-perfect match against itself.
    """
    live_turn = _add_turn(store, "the current prompt itself", turn_index=0, session_id="live")
    old_turn = _add_turn(
        store, "an older turn from a different session", turn_index=0, session_id="old"
    )

    def fake_search(query, k=8, kind_filter=None):
        if kind_filter == str(NodeKind.TURN):
            return [
                {"node_id": live_turn.id, "score": 1.0},
                {"node_id": old_turn.id, "score": 0.9},
            ]
        return []

    monkeypatch.setattr(store, "search", fake_search)

    block = assemble_context(store, query="prompt", budget=4000, session_id="live")

    assert "the current prompt itself" not in block
    assert "an older turn from a different session" in block


# ---------------------------------------------------------------------------
# Relevance floors
# ---------------------------------------------------------------------------


def test_turn_score_floor(store, monkeypatch):
    """Turn hits below 0.77 are dropped; hits at or above it are kept."""
    _add_turn(store, "keeps the block non-trivial", turn_index=0, session_id="live")
    below = _add_turn(store, "a turn just below the turn relevance floor", session_id="old")
    above = _add_turn(store, "a turn just above the turn relevance floor", session_id="old")

    def fake_search(query, k=8, kind_filter=None):
        if kind_filter == str(NodeKind.TURN):
            return [
                {"node_id": below.id, "score": 0.76},
                {"node_id": above.id, "score": 0.78},
            ]
        return []

    monkeypatch.setattr(store, "search", fake_search)

    block = assemble_context(store, query="floor", budget=4000, session_id="live")

    past = _section(block, "Relevant Past Turns")
    assert "a turn just below the turn relevance floor" not in past
    assert "a turn just above the turn relevance floor" in past


def test_summary_score_floor(store, monkeypatch):
    """Summary hits below 0.80 are dropped; hits at or above it are kept."""
    _add_turn(store, "keeps the block non-trivial", turn_index=0, session_id="live")
    below = _add_summary(store, "a summary just below the summary relevance floor")
    above = _add_summary(store, "a summary just above the summary relevance floor")

    def fake_search(query, k=8, kind_filter=None):
        if kind_filter == str(NodeKind.SUMMARY):
            return [
                {"node_id": below.id, "score": 0.79},
                {"node_id": above.id, "score": 0.81},
            ]
        return []

    monkeypatch.setattr(store, "search", fake_search)

    block = assemble_context(store, query="floor", budget=4000, session_id="live")

    summaries = _section(block, "Relevant Context (Compressed)")
    assert "a summary just below the summary relevance floor" not in summaries
    assert "a summary just above the summary relevance floor" in summaries


def test_all_hits_below_floor_with_live_session_returns_empty(store, monkeypatch):
    """A live session plus only-sub-floor hits leaves nothing to assemble."""
    _add_turn(store, "the only turn, in the live session", turn_index=0, session_id="live")
    other = _add_turn(store, "an old turn that scores too low to matter", session_id="old")

    def fake_search(query, k=8, kind_filter=None):
        if kind_filter == str(NodeKind.TURN):
            return [{"node_id": other.id, "score": 0.5}]
        return []

    monkeypatch.setattr(store, "search", fake_search)

    block = assemble_context(store, query="anything", budget=4000, session_id="live")

    assert block == ""


# ---------------------------------------------------------------------------
# Active Topics removed
# ---------------------------------------------------------------------------


def test_no_active_topics_section(store, monkeypatch):
    """The Active Topics section is gone, even when topic search hits."""
    _add_turn(store, "keeps the block non-trivial", turn_index=0, session_id="s1")

    def fake_search(query, k=8, kind_filter=None):
        if kind_filter == str(NodeKind.TOPIC):
            return [{"node_id": "whatever", "score": 0.99}]
        return []

    monkeypatch.setattr(store, "search", fake_search)

    block = assemble_context(store, query="anything", budget=4000)

    assert "Active Topics" not in block


# ---------------------------------------------------------------------------
# Dating
# ---------------------------------------------------------------------------


def test_dates_rendered_for_all_recalled_item_kinds(store, monkeypatch):
    """Past turns, summaries, and open tasks all carry a (YYYY-MM-DD) stamp."""
    _add_turn(store, "keeps the block non-trivial", turn_index=0, session_id="live")
    past_turn = _add_turn(store, "a past turn worth recalling", session_id="old")
    summary = _add_summary(store, "a compressed summary of past work")
    _add_open_task(store, "finish the report")

    def fake_search(query, k=8, kind_filter=None):
        if kind_filter == str(NodeKind.TURN):
            return [{"node_id": past_turn.id, "score": 0.9}]
        if kind_filter == str(NodeKind.SUMMARY):
            return [{"node_id": summary.id, "score": 0.9}]
        return []

    monkeypatch.setattr(store, "search", fake_search)

    block = assemble_context(store, query="anything", budget=4000, session_id="live")

    assert f"({_FIXED_DATE})" in _section(block, "Relevant Past Turns")
    assert f"({_FIXED_DATE})" in _section(block, "Relevant Context (Compressed)")
    assert f"({_FIXED_DATE})" in _section(block, "Open Tasks")


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------


def test_header_includes_staleness_warning(store):
    """A non-empty block carries the "may be stale" disclaimer."""
    _add_turn(store, "some turn", turn_index=0, session_id="s1")

    block = assemble_context(store, query="turn", budget=4000)

    assert "may be stale" in block


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


def test_budget_is_respected(store):
    """Assembly stops adding sections once the budget is exhausted."""
    for i in range(40):
        _add_turn(store, f"turn {i} " + "padding words " * 40, turn_index=i)

    block = assemble_context(store, query="padding", budget=100)

    assert len(block) // 4 <= 200


def test_empty_graph_returns_empty_string(store):
    """An empty graph produces an empty string, not a placeholder.

    The hook that injects assembled context reads stdout and treats empty as
    "inject nothing"; the placeholder used to defeat that by always injecting.
    """
    assert assemble_context(store, query="anything") == ""


# ---------------------------------------------------------------------------
# Harness notification filtering
# ---------------------------------------------------------------------------

_NOTE = (
    "<task-notification>\n<task-id>b123</task-id>\n<status>completed</status>\n"
    "<summary>Background command finished</summary>\n</task-notification>"
)


def test_notification_query_returns_empty(store, monkeypatch):
    """A harness notification used as the query recalls nothing."""
    other = _add_turn(store, "a relevant old turn about ci runs", session_id="old")

    def fake_search(query, k=8, kind_filter=None):
        if kind_filter == str(NodeKind.TURN):
            return [{"node_id": other.id, "score": 0.95}]
        return []

    monkeypatch.setattr(store, "search", fake_search)

    assert assemble_context(store, query="  " + _NOTE, budget=4000) == ""


def test_notification_turns_not_recalled(store, monkeypatch):
    """Old notification turns stored before the ingest fix are not recalled."""
    _add_turn(store, "the live turn", turn_index=0, session_id="live")
    note = _add_turn(store, _NOTE, session_id="old")
    real = _add_turn(store, "a real past turn about ci runs", session_id="old")

    def fake_search(query, k=8, kind_filter=None):
        if kind_filter == str(NodeKind.TURN):
            return [{"node_id": note.id, "score": 0.95}, {"node_id": real.id, "score": 0.9}]
        return []

    monkeypatch.setattr(store, "search", fake_search)

    block = assemble_context(store, query="ci runs", budget=4000, session_id="live")

    assert "task-notification" not in block
    assert "a real past turn about ci runs" in block


def test_summary_notification_blocks_stripped(store, monkeypatch):
    """Closed notification blocks are removed; the real content survives."""
    _add_turn(store, "the live turn", turn_index=0, session_id="live")
    mixed = _add_summary(
        store,
        f"[USER] {_NOTE}\n\n[ASSISTANT] memory-kg 0.11.0 was confirmed live on PyPI after CI.",
    )

    def fake_search(query, k=8, kind_filter=None):
        if kind_filter == str(NodeKind.SUMMARY):
            return [{"node_id": mixed.id, "score": 0.9}]
        return []

    monkeypatch.setattr(store, "search", fake_search)

    block = assemble_context(store, query="memory-kg", budget=4000, session_id="live")

    summaries = _section(block, "Relevant Context (Compressed)")
    assert "task-notification" not in summaries
    assert "memory-kg 0.11.0 was confirmed live" in summaries


def test_summary_of_only_notifications_dropped(store, monkeypatch):
    """A summary that is nothing but notifications, or an unclosed one, is dropped."""
    _add_turn(store, "the live turn", turn_index=0, session_id="live")
    pure = _add_summary(store, f"[USER] {_NOTE}\n\n[USER] {_NOTE}")
    unclosed = _add_summary(
        store, "[USER] <task-notification>\n<task-id>b9</task-id> ... and a long tail of text"
    )

    def fake_search(query, k=8, kind_filter=None):
        if kind_filter == str(NodeKind.SUMMARY):
            return [{"node_id": pure.id, "score": 0.9}, {"node_id": unclosed.id, "score": 0.9}]
        return []

    monkeypatch.setattr(store, "search", fake_search)

    block = assemble_context(store, query="anything", budget=4000, session_id="live")

    assert block == ""
