# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""Unit tests for agent_kg.profile.UserProfileStore."""

import pytest

from agent_kg.profile import UserProfileStore
from agent_kg.schema import Node, NodeKind


@pytest.fixture
def profile(tmp_path):
    """Fresh UserProfileStore in a temp directory for each test."""
    p = UserProfileStore(profile_dir=tmp_path / "profile")
    yield p
    p.close()


class TestUpsert:
    """upsert() — insert and update profile nodes."""

    def test_insert_returns_node(self, profile):
        """upsert returns a Node with the correct kind and label."""
        node = profile.upsert(NodeKind.PREFERENCE, "concise responses")
        assert isinstance(node, Node)
        assert node.kind == NodeKind.PREFERENCE
        assert node.label == "concise responses"

    def test_duplicate_label_no_insert(self, profile):
        """Upserting the same label twice yields exactly one stored node."""
        profile.upsert(NodeKind.PREFERENCE, "dark mode")
        profile.upsert(NodeKind.PREFERENCE, "dark mode")
        nodes = profile.get_by_kind(NodeKind.PREFERENCE)
        assert len(nodes) == 1

    def test_case_insensitive_dedup(self, profile):
        """'Dark Mode' and 'dark mode' are treated as the same label."""
        profile.upsert(NodeKind.PREFERENCE, "Dark Mode")
        profile.upsert(NodeKind.PREFERENCE, "dark mode")
        assert len(profile.get_by_kind(NodeKind.PREFERENCE)) == 1

    def test_confidence_boosted_on_update(self, profile):
        """Re-upserting with higher confidence raises the stored confidence."""
        profile.upsert(NodeKind.EXPERTISE, "Python", confidence=0.5)
        profile.upsert(NodeKind.EXPERTISE, "Python", confidence=0.9)
        nodes = profile.get_by_kind(NodeKind.EXPERTISE)
        assert nodes[0].confidence >= 0.9

    def test_text_stored(self, profile):
        """The text field is persisted."""
        profile.upsert(NodeKind.COMMITMENT, "write tests", text="Always write tests first.")
        nodes = profile.get_by_kind(NodeKind.COMMITMENT)
        assert nodes[0].text == "Always write tests first."

    def test_different_kinds_stored_separately(self, profile):
        """Nodes of different kinds with the same label coexist."""
        profile.upsert(NodeKind.PREFERENCE, "Python")
        profile.upsert(NodeKind.EXPERTISE, "Python")
        assert len(profile.get_by_kind(NodeKind.PREFERENCE)) == 1
        assert len(profile.get_by_kind(NodeKind.EXPERTISE)) == 1


class TestQueryMethods:
    """Convenience accessors — preferences(), commitments(), etc."""

    def test_preferences(self, profile):
        """preferences() returns only PREFERENCE nodes."""
        profile.upsert(NodeKind.PREFERENCE, "dark theme")
        profile.upsert(NodeKind.COMMITMENT, "write tests")
        prefs = profile.preferences()
        assert len(prefs) == 1
        assert prefs[0].kind == NodeKind.PREFERENCE

    def test_commitments(self, profile):
        """commitments() returns only COMMITMENT nodes."""
        profile.upsert(NodeKind.COMMITMENT, "no globals")
        comms = profile.commitments()
        assert len(comms) == 1

    def test_expertise(self, profile):
        """expertise() returns only EXPERTISE nodes."""
        profile.upsert(NodeKind.EXPERTISE, "Python")
        exp = profile.expertise()
        assert len(exp) == 1

    def test_interests(self, profile):
        """interests() returns only INTEREST nodes."""
        profile.upsert(NodeKind.INTEREST, "distributed systems")
        interests = profile.interests()
        assert len(interests) == 1

    def test_all_nodes(self, profile):
        """all_nodes() returns every node regardless of kind."""
        profile.upsert(NodeKind.PREFERENCE, "dark theme")
        profile.upsert(NodeKind.EXPERTISE, "Go")
        profile.upsert(NodeKind.INTEREST, "ML")
        all_ = profile.all_nodes()
        assert len(all_) == 3


class TestApplyUpdates:
    """apply_updates() — bulk NLP-extracted preference ingestion."""

    def test_apply_single_update(self, profile):
        """apply_updates with one record upserts one node."""
        updates = [
            {"kind": "preference", "label": "short answers", "text": "I prefer short answers."}
        ]
        nodes = profile.apply_updates(updates)
        assert len(nodes) == 1
        assert nodes[0].kind == NodeKind.PREFERENCE

    def test_apply_mixed_kinds(self, profile):
        """apply_updates handles multiple kinds in one batch."""
        updates = [
            {"kind": "preference", "label": "dark mode", "text": ""},
            {"kind": "expertise", "label": "Rust", "text": "5 years of Rust"},
            {"kind": "commitment", "label": "no side effects", "text": ""},
        ]
        nodes = profile.apply_updates(updates)
        assert len(nodes) == 3
        kinds = {str(n.kind) for n in nodes}
        assert "preference" in kinds
        assert "expertise" in kinds
        assert "commitment" in kinds

    def test_apply_unknown_kind_falls_back_to_preference(self, profile):
        """apply_updates maps unknown kind strings to PREFERENCE."""
        updates = [{"kind": "bogus", "label": "whatever", "text": ""}]
        nodes = profile.apply_updates(updates)
        assert len(nodes) == 1
        assert nodes[0].kind == NodeKind.PREFERENCE


class TestRenderAndStats:
    """render_markdown() and stats()."""

    def test_render_markdown_returns_string(self, profile):
        """render_markdown returns a non-empty string."""
        profile.upsert(NodeKind.PREFERENCE, "dark theme")
        md = profile.render_markdown()
        assert isinstance(md, str)
        assert len(md) > 0

    def test_render_markdown_empty_profile(self, profile):
        """render_markdown on an empty profile returns a string."""
        md = profile.render_markdown()
        assert isinstance(md, str)

    def test_stats_counts(self, profile):
        """stats() reflects the number of nodes per kind."""
        profile.upsert(NodeKind.PREFERENCE, "dark mode")
        profile.upsert(NodeKind.EXPERTISE, "Python")
        s = profile.stats()
        assert isinstance(s, dict)
        assert s["total"] == 2
        assert s["by_kind"]["preference"] == 1
        assert s["by_kind"]["expertise"] == 1
