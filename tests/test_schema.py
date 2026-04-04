# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""Unit tests for agent_kg.schema — Node, Edge, and enum types."""

import json

from agent_kg.schema import (
    Edge,
    EdgeRelation,
    IntentCategory,
    Node,
    NodeKind,
    PruneReport,
    TaskStatus,
)

# ---------------------------------------------------------------------------
# Enum smoke tests
# ---------------------------------------------------------------------------


class TestNodeKind:
    """NodeKind enum values."""

    def test_turn(self):
        """TURN has the expected string value."""
        assert NodeKind.TURN == "turn"

    def test_summary(self):
        """SUMMARY has the expected string value."""
        assert NodeKind.SUMMARY == "summary"

    def test_task(self):
        """TASK has the expected string value."""
        assert NodeKind.TASK == "task"

    def test_profile_kinds_present(self):
        """All UserProfile node kinds are defined."""
        for name in ("PREFERENCE", "STYLE", "INTEREST", "EXPERTISE", "COMMITMENT", "CONTEXT"):
            assert hasattr(NodeKind, name), f"NodeKind.{name} missing"

    def test_round_trip(self):
        """NodeKind can be reconstructed from its string value."""
        for kind in NodeKind:
            assert NodeKind(str(kind)) == kind


class TestEdgeRelation:
    """EdgeRelation enum values."""

    def test_follows(self):
        """FOLLOWS is upper-cased."""
        assert EdgeRelation.FOLLOWS == "FOLLOWS"

    def test_addresses(self):
        """ADDRESSES is upper-cased."""
        assert EdgeRelation.ADDRESSES == "ADDRESSES"

    def test_all_uppercase(self):
        """All EdgeRelation values are upper-case strings."""
        for rel in EdgeRelation:
            assert str(rel) == str(rel).upper()

    def test_round_trip(self):
        """EdgeRelation can be reconstructed from its string value."""
        for rel in EdgeRelation:
            assert EdgeRelation(str(rel)) == rel


class TestTaskStatus:
    """TaskStatus enum values."""

    def test_open(self):
        """OPEN is 'open'."""
        assert TaskStatus.OPEN == "open"

    def test_completed(self):
        """COMPLETED is 'completed'."""
        assert TaskStatus.COMPLETED == "completed"

    def test_all_values(self):
        """All four lifecycle states are present."""
        values = {str(s) for s in TaskStatus}
        assert values == {"open", "in_progress", "completed", "abandoned"}


class TestIntentCategory:
    """IntentCategory enum values."""

    def test_question(self):
        """QUESTION is 'question'."""
        assert IntentCategory.QUESTION == "question"

    def test_request(self):
        """REQUEST is 'request'."""
        assert IntentCategory.REQUEST == "request"

    def test_unknown(self):
        """UNKNOWN is 'unknown'."""
        assert IntentCategory.UNKNOWN == "unknown"

    def test_all_categories_present(self):
        """All eight intent categories are defined."""
        expected = {
            "question",
            "request",
            "correction",
            "confirmation",
            "clarification",
            "context",
            "feedback",
            "unknown",
        }
        assert {str(c) for c in IntentCategory} == expected


# ---------------------------------------------------------------------------
# Node dataclass
# ---------------------------------------------------------------------------


class TestNode:
    """Node dataclass construction, defaults, and serialisation."""

    def test_minimal_construction(self):
        """Node with only kind set uses sensible defaults."""
        node = Node(kind=NodeKind.TURN)
        assert node.kind == NodeKind.TURN
        assert node.label == ""
        assert node.text == ""
        assert node.turn_index == 0
        assert node.pruning_pass == 0
        assert node.confidence == 1.0
        assert isinstance(node.id, str) and len(node.id) > 0

    def test_auto_id_is_unique(self):
        """Two nodes get different auto-generated IDs."""
        a = Node(kind=NodeKind.TURN)
        b = Node(kind=NodeKind.TURN)
        assert a.id != b.id

    def test_explicit_fields(self):
        """Explicitly set fields are stored correctly."""
        node = Node(
            kind=NodeKind.TASK,
            label="Fix bug",
            text="Fix the null pointer bug in login",
            role="user",
            turn_index=3,
            status=str(TaskStatus.OPEN),
            session_id="sess-abc",
        )
        assert node.label == "Fix bug"
        assert node.turn_index == 3
        assert node.status == "open"
        assert node.session_id == "sess-abc"

    def test_to_dict_keys(self):
        """to_dict() contains all expected keys."""
        node = Node(kind=NodeKind.TOPIC, label="docker")
        d = node.to_dict()
        for key in (
            "id",
            "kind",
            "label",
            "text",
            "role",
            "turn_index",
            "token_count",
            "status",
            "category",
            "confidence",
            "covers_turns",
            "pruning_pass",
            "session_id",
            "created_at",
            "metadata",
        ):
            assert key in d, f"Missing key: {key}"

    def test_to_dict_kind_is_string(self):
        """to_dict() serialises kind as a plain string."""
        node = Node(kind=NodeKind.SUMMARY)
        assert node.to_dict()["kind"] == "summary"
        assert isinstance(node.to_dict()["kind"], str)

    def test_to_dict_covers_turns_is_json(self):
        """covers_turns is JSON-encoded in the dict."""
        node = Node(kind=NodeKind.SUMMARY, covers_turns=["id1", "id2"])
        raw = node.to_dict()["covers_turns"]
        assert json.loads(raw) == ["id1", "id2"]

    def test_to_dict_metadata_is_json(self):
        """metadata is JSON-encoded in the dict."""
        node = Node(kind=NodeKind.ENTITY, metadata={"src": "regex"})
        raw = node.to_dict()["metadata"]
        assert json.loads(raw) == {"src": "regex"}

    def test_from_dict_round_trip(self):
        """from_dict(to_dict(node)) reconstructs the node faithfully."""
        original = Node(
            kind=NodeKind.TASK,
            label="Deploy fix",
            text="Deploy the hotfix to prod",
            role="user",
            turn_index=5,
            status=str(TaskStatus.IN_PROGRESS),
            covers_turns=["t1", "t2"],
            metadata={"priority": "high"},
        )
        restored = Node.from_dict(original.to_dict())
        assert restored.id == original.id
        assert restored.kind == NodeKind.TASK
        assert restored.label == "Deploy fix"
        assert restored.turn_index == 5
        assert restored.status == "in_progress"
        assert restored.covers_turns == ["t1", "t2"]
        assert restored.metadata == {"priority": "high"}

    def test_from_dict_missing_optional_fields(self):
        """from_dict() handles dicts with missing optional fields gracefully."""
        d = {"id": "abc", "kind": "turn"}
        node = Node.from_dict(d)
        assert node.id == "abc"
        assert node.kind == NodeKind.TURN
        assert node.label == ""
        assert node.confidence == 1.0


# ---------------------------------------------------------------------------
# Edge dataclass
# ---------------------------------------------------------------------------


class TestEdge:
    """Edge dataclass construction and serialisation."""

    def test_minimal_construction(self):
        """Edge with required fields uses sensible defaults."""
        edge = Edge(
            source_id="src",
            target_id="tgt",
            relation=EdgeRelation.FOLLOWS,
        )
        assert edge.source_id == "src"
        assert edge.target_id == "tgt"
        assert edge.relation == EdgeRelation.FOLLOWS
        assert edge.weight == 1.0
        assert isinstance(edge.id, str) and len(edge.id) > 0

    def test_auto_id_is_unique(self):
        """Two edges get different auto-generated IDs."""
        a = Edge(source_id="s", target_id="t", relation=EdgeRelation.FOLLOWS)
        b = Edge(source_id="s", target_id="t", relation=EdgeRelation.FOLLOWS)
        assert a.id != b.id

    def test_to_dict_keys(self):
        """to_dict() contains source_id, target_id, relation, id, weight."""
        edge = Edge(source_id="s", target_id="t", relation=EdgeRelation.MENTIONS)
        d = edge.to_dict()
        for key in ("id", "source_id", "target_id", "relation", "weight", "created_at"):
            assert key in d, f"Missing key: {key}"

    def test_to_dict_relation_is_string(self):
        """relation is stored as a plain string."""
        edge = Edge(source_id="s", target_id="t", relation=EdgeRelation.CREATES)
        assert edge.to_dict()["relation"] == "CREATES"


# ---------------------------------------------------------------------------
# PruneReport dataclass
# ---------------------------------------------------------------------------


class TestPruneReport:
    """PruneReport construction (required positional fields)."""

    def test_required_fields(self):
        """PruneReport stores all provided values."""
        report = PruneReport(
            summaries_created=2,
            turns_pruned=8,
            nodes_removed=12,
            pruning_pass=1,
            token_savings_approx=1200,
        )
        assert report.summaries_created == 2
        assert report.turns_pruned == 8
        assert report.nodes_removed == 12
        assert report.pruning_pass == 1
        assert report.token_savings_approx == 1200

    def test_optional_token_savings_default(self):
        """token_savings_approx defaults to 0 when omitted."""
        report = PruneReport(summaries_created=1, turns_pruned=4, nodes_removed=6, pruning_pass=1)
        assert report.token_savings_approx == 0
