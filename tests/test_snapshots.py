# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""Unit tests for agent_kg.snapshots — the shared-model SnapshotManager.

AgentKG used to hand-roll its own capture/list/diff functions with no
relationship to kg_utils.snapshots: no tag keying, no manifest, no
subject/tool/tool_version provenance. This suite covers the migration onto
the shared model, matching the pattern used by every other KG module.
"""

from __future__ import annotations

import json

import pytest
from kg_utils.snapshots import Snapshot as SharedSnapshot

from agent_kg.schema import Node, NodeKind, TaskStatus
from agent_kg.snapshots import Snapshot, SnapshotManager
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
def mgr(tmp_path):
    """SnapshotManager rooted at a fresh directory."""
    return SnapshotManager(tmp_path / "snapshots")


# ---------------------------------------------------------------------------
# Snapshot is the shared class
# ---------------------------------------------------------------------------


def test_snapshot_is_the_shared_class() -> None:
    """AgentKG does not subclass Snapshot -- that pattern is what shipped a
    real bug in two sibling repos (see SNAPSHOT_SUBCLASS_RETIREMENT.md)."""
    assert Snapshot is SharedSnapshot


# ---------------------------------------------------------------------------
# capture_conversation()
# ---------------------------------------------------------------------------


class TestCaptureConversation:
    """capture_conversation() — build a Snapshot from store state."""

    def test_returns_a_snapshot(self, store, mgr) -> None:
        snap = mgr.capture_conversation(store, version="0.10.0", key="v0.10.0")
        assert isinstance(snap, Snapshot)

    def test_metrics_contains_required_keys(self, store, mgr) -> None:
        snap = mgr.capture_conversation(store, version="0.10.0", key="v0.10.0")
        for key in (
            "total_nodes",
            "total_edges",
            "turn_count",
            "summary_count",
            "open_task_count",
            "session_count",
            "pruning_pass",
        ):
            assert key in snap.metrics, f"Missing metric: {key}"

    def test_empty_store_zeros(self, store, mgr) -> None:
        snap = mgr.capture_conversation(store, version="0.10.0", key="v0.10.0")
        assert snap.metrics["total_nodes"] == 0
        assert snap.metrics["turn_count"] == 0
        assert snap.metrics["open_task_count"] == 0

    def test_counts_reflect_data(self, store, mgr) -> None:
        store.upsert_node(Node(kind=NodeKind.TURN, session_id="s"))
        store.upsert_node(Node(kind=NodeKind.TASK, status=str(TaskStatus.OPEN)))
        snap = mgr.capture_conversation(store, version="0.10.0", key="v0.10.0")
        assert snap.metrics["total_nodes"] == 2
        assert snap.metrics["turn_count"] == 1
        assert snap.metrics["open_task_count"] == 1

    def test_label_stored_in_metrics(self, store, mgr) -> None:
        snap = mgr.capture_conversation(store, version="0.10.0", key="v0.10.0", label="pre-release")
        assert snap.metrics["label"] == "pre-release"

    def test_label_omitted_when_not_given(self, store, mgr) -> None:
        snap = mgr.capture_conversation(store, version="0.10.0", key="v0.10.0")
        assert "label" not in snap.metrics

    def test_version_stored(self, store, mgr) -> None:
        snap = mgr.capture_conversation(store, version="1.2.3", key="v1.2.3")
        assert snap.version == "1.2.3"

    def test_subject_stored(self, store, mgr) -> None:
        snap = mgr.capture_conversation(
            store, version="0.10.0", key="v0.10.0", subject="repo:agent-kg"
        )
        assert snap.subject == "repo:agent-kg"


# ---------------------------------------------------------------------------
# Key scheme (matches kgmodule-utils >= 0.19.0)
# ---------------------------------------------------------------------------


class TestKeyScheme:
    """A snapshot is keyed on the supplied tag, not a tree hash."""

    def test_capture_uses_a_supplied_key(self, store, mgr) -> None:
        snap = mgr.capture_conversation(store, version="0.10.0", key="v0.10.0")
        assert snap.key == "v0.10.0"

    def test_capture_without_a_key_does_not_use_the_tree_hash(self, store, mgr) -> None:
        snap = mgr.capture_conversation(store, version="0.10.0")
        assert snap.key != snap.tree_hash

    def test_save_snapshot_persists_key_subject_and_tool(self, store, mgr, tmp_path) -> None:
        store.upsert_node(Node(kind=NodeKind.TURN, session_id="s"))
        snap = mgr.capture_conversation(
            store, version="0.10.0", key="v0.10.0", subject="repo:agent-kg"
        )
        saved = mgr.save_snapshot(snap)
        assert saved is not None

        on_disk = json.loads(saved.read_text(encoding="utf-8"))
        assert on_disk["key"] == "v0.10.0"
        assert on_disk["subject"] == "repo:agent-kg"
        assert on_disk["tool"] == "agent-kg"
        assert on_disk["tool_version"]


# ---------------------------------------------------------------------------
# save_snapshot / load_snapshot / list_snapshots / diff_snapshots
# (all inherited from the shared manager -- covered here at the integration
# level, not re-testing the shared implementation itself)
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_save_rejects_zero_nodes(self, store, mgr) -> None:
        snap = mgr.capture_conversation(store, version="0.10.0", key="v0.10.0")
        with pytest.raises(ValueError, match="0 nodes"):
            mgr.save_snapshot(snap)

    def test_save_and_load_round_trip(self, store, mgr) -> None:
        store.upsert_node(Node(kind=NodeKind.TURN, session_id="s"))
        snap = mgr.capture_conversation(store, version="0.10.0", key="v0.10.0")
        mgr.save_snapshot(snap)

        loaded = mgr.load_snapshot("v0.10.0")
        assert loaded is not None
        assert loaded.metrics["total_nodes"] == 1

    def test_list_snapshots(self, store, mgr) -> None:
        store.upsert_node(Node(kind=NodeKind.TURN, session_id="s"))
        snap = mgr.capture_conversation(store, version="0.10.0", key="v0.10.0")
        mgr.save_snapshot(snap)

        listed = mgr.list_snapshots()
        assert len(listed) == 1
        assert listed[0]["key"] == "v0.10.0"


class TestDiffSnapshots:
    """diff_snapshots() delta includes AgentKG's domain fields."""

    def test_domain_delta_fields_present(self, store, mgr) -> None:
        store.upsert_node(Node(kind=NodeKind.TURN, session_id="s"))
        snap_a = mgr.capture_conversation(store, version="0.10.0", key="a")
        mgr.save_snapshot(snap_a)

        store.upsert_node(Node(kind=NodeKind.TURN, session_id="s2"))
        store.upsert_node(Node(kind=NodeKind.TASK, status=str(TaskStatus.OPEN)))
        snap_b = mgr.capture_conversation(store, version="0.10.0", key="b")
        mgr.save_snapshot(snap_b)

        result = mgr.diff_snapshots("a", "b")
        assert result["delta"]["turns_delta"] == 1
        assert result["delta"]["open_tasks_delta"] == 1

    def test_backfilled_delta_keeps_domain_fields(self, store, mgr) -> None:
        """The load_snapshot backfill also carries the domain delta fields --
        the exact gap fixed in kgmodule-utils 0.19.1."""
        store.upsert_node(Node(kind=NodeKind.TURN, session_id="s"))
        snap_a = mgr.capture_conversation(store, version="0.10.0", key="a")
        mgr.save_snapshot(snap_a)

        store.upsert_node(Node(kind=NodeKind.TURN, session_id="s2"))
        snap_b = mgr.capture_conversation(store, version="0.10.0", key="b")
        mgr.save_snapshot(snap_b)

        loaded = mgr.load_snapshot("b")
        assert loaded is not None
        assert loaded.vs_previous is not None
        assert loaded.vs_previous["turns_delta"] == 1
