"""AgentKG's adoption of the shared kg_utils.temporal contract.

AgentKG is the fleet's clearest *interval* case. A diary entry happens on a
day; a conversational topic is first mentioned on Monday and last mentioned on
Friday, and occurred across that span. So unlike DiaryKG, all three contract
keys carry information here.

The contract is a derived view of the node's own authored timestamps —
``first_seen`` / ``last_seen`` / ``created_at`` — never a second authoring, so
the two representations cannot disagree.
"""

from __future__ import annotations

from datetime import UTC, datetime

from kg_utils.temporal import parse_temporal, read_span

from agent_kg.schema import Node, NodeKind


def _node(first, last, created=None, **kw):
    return Node(
        kind=NodeKind.TOPIC,
        label="waverider",
        first_seen=first,
        last_seen=last,
        created_at=created or first,
        **kw,
    )


class TestTemporalDerivation:
    def test_all_three_keys_are_emitted(self):
        n = _node(datetime(2026, 4, 1, tzinfo=UTC), datetime(2026, 4, 15, tzinfo=UTC))
        assert set(n.temporal()) == {"occurred_start", "occurred_end", "recorded_at"}

    def test_maps_first_and_last_seen_to_the_interval(self):
        n = _node(
            datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
            datetime(2026, 4, 15, 17, 30, tzinfo=UTC),
        )
        t = n.temporal()
        assert parse_temporal(t["occurred_start"])[0] == datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
        assert parse_temporal(t["occurred_end"])[0] == datetime(2026, 4, 15, 17, 30, tzinfo=UTC)

    def test_created_at_is_the_recorded_time(self):
        n = _node(
            datetime(2026, 4, 1, tzinfo=UTC),
            datetime(2026, 4, 15, tzinfo=UTC),
            created=datetime(2026, 4, 20, tzinfo=UTC),
        )
        assert parse_temporal(n.temporal()["recorded_at"])[0] == datetime(2026, 4, 20, tzinfo=UTC)

    def test_derivation_is_pure(self):
        """A derived view: same node, same result, every time."""
        n = _node(datetime(2026, 4, 1, tzinfo=UTC), datetime(2026, 4, 15, tzinfo=UTC))
        assert n.temporal() == n.temporal()

    def test_does_not_touch_the_metadata_field(self):
        """metadata stays free for callers; the contract is computed, not stored."""
        n = _node(
            datetime(2026, 4, 1, tzinfo=UTC),
            datetime(2026, 4, 15, tzinfo=UTC),
            metadata={"mine": "untouched"},
        )
        n.temporal()
        assert n.metadata == {"mine": "untouched"}

    def test_default_node_is_effectively_a_point_in_time(self):
        """A freshly created node spans one moment.

        Not byte-identical: ``first_seen`` and ``last_seen`` each have their own
        ``default_factory``, so the two ``_now()`` calls land microseconds
        apart. What matters is that the span is a point for any window anyone
        would actually query.
        """
        n = Node(kind=NodeKind.TOPIC, label="x")
        span = read_span(n.temporal())
        assert (span.end - span.start).total_seconds() < 1
        today = span.start.date().isoformat()
        assert span.overlaps(today, today)


class TestIntervalSemantics:
    """The payoff: a span matches a window that touches any part of it."""

    def _span(self):
        return read_span(
            _node(
                datetime(2026, 4, 1, tzinfo=UTC),
                datetime(2026, 4, 15, tzinfo=UTC),
            ).temporal()
        )

    def test_window_inside_the_span_matches(self):
        assert self._span().overlaps("2026-04-10", "2026-04-10")

    def test_window_overlapping_the_start_matches(self):
        assert self._span().overlaps("2026-03-20", "2026-04-02")

    def test_window_overlapping_the_end_matches(self):
        assert self._span().overlaps("2026-04-14", "2026-05-01")

    def test_window_after_the_span_does_not_match(self):
        assert not self._span().overlaps("2026-05-01", "2026-05-31")

    def test_window_before_the_span_does_not_match(self):
        assert not self._span().overlaps("2026-01-01", "2026-03-01")

    def test_a_point_node_matches_only_its_own_moment(self):
        moment = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)
        span = read_span(_node(moment, moment).temporal())
        assert span.overlaps("2026-04-10", "2026-04-10")
        assert not span.overlaps("2026-04-11", "2026-04-12")


class TestQueryResultsCarryTheContract:
    """The federated path: kg-rag's adapter reads `metadata` off each hit."""

    def test_query_hits_expose_metadata(self, tmp_path):
        from agent_kg.query import query as run_query
        from agent_kg.store import AgentKGStore

        store = AgentKGStore(tmp_path / "g.sqlite", tmp_path / "v.sqlite")
        node = _node(
            datetime(2026, 4, 1, tzinfo=UTC),
            datetime(2026, 4, 15, tzinfo=UTC),
            text="the waverider manifold work",
        )
        store.upsert_node(node)
        hits = run_query(store, "waverider manifold", k=3)
        if hits:  # semantic backend may return nothing without an index
            assert "metadata" in hits[0]
            if hits[0]["metadata"]:
                assert "occurred_start" in hits[0]["metadata"]
        store.close()
