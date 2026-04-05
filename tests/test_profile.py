# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""Unit tests for agent_kg.user_profile.UserProfileStore."""

import pytest

from agent_kg.schema import Node, NodeKind
from agent_kg.user_profile import UserProfileStore


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


class TestSetIdentity:
    """set_identity() and get_identity() — structured personal fields."""

    def test_set_and_get_all_fields(self, profile):
        """All identity fields round-trip correctly."""
        profile.set_identity(
            name="Alice Smith",
            email="alice@example.com",
            phone="555-1234",
            address="1 Main St",
            birth_date="1980-06-15",
            gender="Female",
            cognitive_score=90,
            delta_year=25,
        )
        identity = profile.get_identity()
        assert identity["name"] == "Alice Smith"
        assert identity["email"] == "alice@example.com"
        assert identity["phone"] == "555-1234"
        assert identity["address"] == "1 Main St"
        assert identity["birth_date"] == "1980-06-15"
        assert identity["gender"] == "Female"
        assert identity["cognitive_score"] == 90
        assert identity["delta_year"] == 25

    def test_partial_update_preserves_other_fields(self, profile):
        """Updating one field does not clear the others."""
        profile.set_identity(name="Bob", email="bob@example.com")
        profile.set_identity(phone="555-9999")
        identity = profile.get_identity()
        assert identity["name"] == "Bob"
        assert identity["email"] == "bob@example.com"
        assert identity["phone"] == "555-9999"

    def test_get_identity_defaults_when_empty(self, profile):
        """get_identity returns safe defaults when no record exists."""
        identity = profile.get_identity()
        assert identity["name"] == ""
        assert identity["cognitive_score"] == 100
        assert identity["delta_year"] == 0

    def test_cognitive_score_clamped_high(self, profile):
        """cognitive_score above 100 is clamped to 100."""
        profile.set_identity(cognitive_score=200)
        assert profile.get_identity()["cognitive_score"] == 100

    def test_cognitive_score_clamped_low(self, profile):
        """cognitive_score below 0 is clamped to 0."""
        profile.set_identity(cognitive_score=-5)
        assert profile.get_identity()["cognitive_score"] == 0

    def test_delta_year_clamped_high(self, profile):
        """delta_year above 150 is clamped to 150."""
        profile.set_identity(delta_year=999)
        assert profile.get_identity()["delta_year"] == 150

    def test_delta_year_clamped_low(self, profile):
        """delta_year below 0 is clamped to 0."""
        profile.set_identity(delta_year=-10)
        assert profile.get_identity()["delta_year"] == 0

    def test_set_identity_returns_updated_dict(self, profile):
        """set_identity returns the full updated identity dict."""
        result = profile.set_identity(name="Carol")
        assert isinstance(result, dict)
        assert result["name"] == "Carol"

    def test_singleton_row_only_one_row(self, profile):
        """Multiple set_identity calls never create more than one row."""
        profile.set_identity(name="A")
        profile.set_identity(name="B")
        profile.set_identity(name="C")
        db = profile._get_db()
        count = db.execute("SELECT COUNT(*) FROM profile_identity").fetchone()[0]
        assert count == 1


class TestEducation:
    """Education nodes — upsert, retrieve, and render."""

    def test_upsert_education_node(self, profile):
        """Upserting an EDUCATION node stores it correctly."""
        node = profile.upsert(NodeKind.EDUCATION, "PhD CS, MIT, 1998")
        assert node.kind == NodeKind.EDUCATION
        assert node.label == "PhD CS, MIT, 1998"

    def test_education_accessor(self, profile):
        """education() returns only EDUCATION nodes."""
        profile.upsert(NodeKind.EDUCATION, "BSc Physics, Oxford, 1990")
        profile.upsert(NodeKind.PREFERENCE, "dark mode")
        edu = profile.education()
        assert len(edu) == 1
        assert edu[0].kind == NodeKind.EDUCATION

    def test_multiple_education_entries(self, profile):
        """Multiple education entries are all stored independently."""
        profile.upsert(NodeKind.EDUCATION, "BSc Physics, Oxford, 1990")
        profile.upsert(NodeKind.EDUCATION, "PhD CS, MIT, 1998")
        assert len(profile.education()) == 2

    def test_render_markdown_includes_education(self, profile):
        """render_markdown shows an Education section when entries exist."""
        profile.upsert(NodeKind.EDUCATION, "PhD CS, MIT, 1998")
        md = profile.render_markdown()
        assert "## Education" in md
        assert "PhD CS, MIT, 1998" in md

    def test_render_markdown_includes_identity(self, profile):
        """render_markdown shows an Identity section when fields are set."""
        profile.set_identity(name="Eric", cognitive_score=95)
        md = profile.render_markdown()
        assert "## Identity" in md
        assert "Eric" in md
        assert "95" in md

    def test_render_markdown_omits_personal_strings_when_not_set(self, profile):
        """render_markdown does not show name/email/etc when they are blank."""
        md = profile.render_markdown()
        assert "Name" not in md
        assert "Email" not in md
        assert "Address" not in md

    def test_summary_includes_identity_and_education(self, profile):
        """summary() dict contains identity and education keys."""
        profile.set_identity(name="Eric")
        profile.upsert(NodeKind.EDUCATION, "PhD CS, MIT, 1998")
        s = profile.summary()
        assert "identity" in s
        assert "education" in s
        assert s["identity"]["name"] == "Eric"
        assert "PhD CS, MIT, 1998" in s["education"]


class TestDelete:
    """delete() — remove a single node by kind + label."""

    def test_delete_existing_node(self, profile):
        """delete() removes a node and returns True."""
        profile.upsert(NodeKind.PREFERENCE, "dark mode")
        removed = profile.delete(NodeKind.PREFERENCE, "dark mode")
        assert removed is True
        assert len(profile.preferences()) == 0

    def test_delete_case_insensitive(self, profile):
        """delete() matches the label case-insensitively."""
        profile.upsert(NodeKind.PREFERENCE, "Dark Mode")
        removed = profile.delete(NodeKind.PREFERENCE, "dark mode")
        assert removed is True
        assert len(profile.preferences()) == 0

    def test_delete_missing_node_returns_false(self, profile):
        """delete() returns False when the node does not exist."""
        result = profile.delete(NodeKind.PREFERENCE, "nonexistent")
        assert result is False

    def test_delete_only_removes_matching_kind(self, profile):
        """delete() on PREFERENCE does not remove a same-label EXPERTISE node."""
        profile.upsert(NodeKind.PREFERENCE, "Python")
        profile.upsert(NodeKind.EXPERTISE, "Python")
        profile.delete(NodeKind.PREFERENCE, "Python")
        assert len(profile.preferences()) == 0
        assert len(profile.expertise()) == 1

    def test_delete_one_of_many(self, profile):
        """delete() removes only the targeted node, leaving others intact."""
        profile.upsert(NodeKind.COMMITMENT, "write tests")
        profile.upsert(NodeKind.COMMITMENT, "no globals")
        profile.delete(NodeKind.COMMITMENT, "write tests")
        remaining = profile.commitments()
        assert len(remaining) == 1
        assert remaining[0].label == "no globals"


class TestClearKind:
    """clear_kind() — wipe all nodes of a given kind."""

    def test_clear_removes_all_of_kind(self, profile):
        """clear_kind removes every node of the specified kind."""
        profile.upsert(NodeKind.PREFERENCE, "dark mode")
        profile.upsert(NodeKind.PREFERENCE, "concise")
        n = profile.clear_kind(NodeKind.PREFERENCE)
        assert n == 2
        assert len(profile.preferences()) == 0

    def test_clear_does_not_touch_other_kinds(self, profile):
        """clear_kind leaves nodes of other kinds untouched."""
        profile.upsert(NodeKind.PREFERENCE, "dark mode")
        profile.upsert(NodeKind.EXPERTISE, "Python")
        profile.clear_kind(NodeKind.PREFERENCE)
        assert len(profile.expertise()) == 1

    def test_clear_empty_kind_returns_zero(self, profile):
        """clear_kind on a kind with no nodes returns 0."""
        n = profile.clear_kind(NodeKind.INTEREST)
        assert n == 0
