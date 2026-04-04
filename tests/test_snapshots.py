# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""Unit tests for agent_kg.snapshots — capture, list, diff."""

import json

import pytest

from agent_kg.schema import Node, NodeKind, TaskStatus
from agent_kg.snapshots import capture, diff_snapshots, list_snapshots
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
def snaps_dir(tmp_path):
    """Dedicated snapshots directory."""
    return tmp_path / "snapshots"


# ---------------------------------------------------------------------------
# capture()
# ---------------------------------------------------------------------------


class TestCapture:
    """capture() — write a snapshot JSON and return the dict."""

    def test_returns_dict(self, store, snaps_dir):
        """capture returns a dictionary."""
        snap = capture(store, snaps_dir)
        assert isinstance(snap, dict)

    def test_required_keys(self, store, snaps_dir):
        """Snapshot contains all required metric keys."""
        snap = capture(store, snaps_dir)
        for key in (
            "version",
            "timestamp",
            "node_count",
            "edge_count",
            "turn_count",
            "summary_count",
            "open_task_count",
            "session_count",
            "pruning_pass",
        ):
            assert key in snap, f"Missing key: {key}"

    def test_empty_store_zeros(self, store, snaps_dir):
        """Empty store produces zero counts."""
        snap = capture(store, snaps_dir)
        assert snap["node_count"] == 0
        assert snap["turn_count"] == 0
        assert snap["open_task_count"] == 0

    def test_counts_reflect_data(self, store, snaps_dir):
        """Snapshot counts match actual store contents."""
        store.upsert_node(Node(kind=NodeKind.TURN, session_id="s"))
        store.upsert_node(Node(kind=NodeKind.TASK, status=str(TaskStatus.OPEN)))
        snap = capture(store, snaps_dir)
        assert snap["node_count"] == 2
        assert snap["turn_count"] == 1
        assert snap["open_task_count"] == 1

    def test_writes_file_to_disk(self, store, snaps_dir):
        """capture writes exactly one JSON file to snaps_dir."""
        capture(store, snaps_dir)
        files = list(snaps_dir.glob("*.json"))
        assert len(files) == 1

    def test_file_is_valid_json(self, store, snaps_dir):
        """The written file contains valid JSON."""
        capture(store, snaps_dir)
        f = next(snaps_dir.glob("*.json"))
        data = json.loads(f.read_text())
        assert "node_count" in data

    def test_label_stored(self, store, snaps_dir):
        """The optional label is stored in the snapshot."""
        snap = capture(store, snaps_dir, label="pre-release")
        assert snap["label"] == "pre-release"

    def test_version_stored(self, store, snaps_dir):
        """The version string is stored in the snapshot."""
        snap = capture(store, snaps_dir, version="1.2.3")
        assert snap["version"] == "1.2.3"

    def test_creates_snaps_dir(self, store, tmp_path):
        """capture creates the snapshots directory if it doesn't exist."""
        new_dir = tmp_path / "new" / "deep" / "dir"
        assert not new_dir.exists()
        capture(store, new_dir)
        assert new_dir.exists()


# ---------------------------------------------------------------------------
# list_snapshots()
# ---------------------------------------------------------------------------


class TestListSnapshots:
    """list_snapshots() — enumerate JSON files in a directory."""

    def test_empty_dir_returns_empty(self, snaps_dir):
        """Non-existent directory returns []."""
        assert list_snapshots(snaps_dir) == []

    def test_lists_captured_snapshot(self, store, snaps_dir):
        """Captured snapshots appear in list_snapshots."""
        capture(store, snaps_dir)
        snaps = list_snapshots(snaps_dir)
        assert len(snaps) == 1

    def test_multiple_snapshots(self, store, snaps_dir):
        """Multiple captures produce multiple entries."""
        import time

        capture(store, snaps_dir, label="a")
        time.sleep(1.1)  # filenames are second-precision; ensure distinct names
        capture(store, snaps_dir, label="b")
        snaps = list_snapshots(snaps_dir)
        assert len(snaps) == 2

    def test_each_entry_has_path(self, store, snaps_dir):
        """Each entry in the list has a 'path' key."""
        capture(store, snaps_dir)
        snaps = list_snapshots(snaps_dir)
        assert "path" in snaps[0]

    def test_newest_first_order(self, store, snaps_dir):
        """Snapshots are returned newest first (by filename sort, reversed)."""
        capture(store, snaps_dir, label="first")
        import time

        time.sleep(1.1)  # ensure distinct filenames (timestamp-based)
        capture(store, snaps_dir, label="second")
        snaps = list_snapshots(snaps_dir)
        assert snaps[0]["label"] == "second"


# ---------------------------------------------------------------------------
# diff_snapshots()
# ---------------------------------------------------------------------------


class TestDiffSnapshots:
    """diff_snapshots() — pure function, no I/O."""

    def test_zero_delta_identical(self):
        """Two identical snapshots have zero deltas for all numeric fields."""
        snap = {
            "node_count": 5,
            "edge_count": 3,
            "turn_count": 4,
            "summary_count": 1,
            "open_task_count": 0,
            "session_count": 2,
            "pruning_pass": 0,
        }
        delta = diff_snapshots(snap, snap)
        for key, v in delta.items():
            assert v["delta"] == 0, f"{key}: expected delta=0, got {v}"

    def test_positive_delta(self):
        """Nodes added between snapshots show positive delta."""
        a = {
            "node_count": 2,
            "edge_count": 1,
            "turn_count": 1,
            "summary_count": 0,
            "open_task_count": 0,
            "session_count": 1,
            "pruning_pass": 0,
        }
        b = {
            "node_count": 10,
            "edge_count": 5,
            "turn_count": 6,
            "summary_count": 2,
            "open_task_count": 1,
            "session_count": 1,
            "pruning_pass": 1,
        }
        delta = diff_snapshots(a, b)
        assert delta["node_count"]["delta"] == 8
        assert delta["turn_count"]["delta"] == 5
        assert delta["summary_count"]["delta"] == 2

    def test_negative_delta(self):
        """Nodes removed between snapshots show negative delta."""
        a = {
            "node_count": 10,
            "edge_count": 5,
            "turn_count": 8,
            "summary_count": 0,
            "open_task_count": 2,
            "session_count": 1,
            "pruning_pass": 0,
        }
        b = {
            "node_count": 4,
            "edge_count": 5,
            "turn_count": 0,
            "summary_count": 2,
            "open_task_count": 0,
            "session_count": 1,
            "pruning_pass": 1,
        }
        delta = diff_snapshots(a, b)
        assert delta["node_count"]["delta"] == -6
        assert delta["turn_count"]["delta"] == -8

    def test_before_after_values(self):
        """Delta dict contains 'before' and 'after' values."""
        a = {
            "node_count": 3,
            "edge_count": 0,
            "turn_count": 0,
            "summary_count": 0,
            "open_task_count": 0,
            "session_count": 0,
            "pruning_pass": 0,
        }
        b = {
            "node_count": 7,
            "edge_count": 0,
            "turn_count": 0,
            "summary_count": 0,
            "open_task_count": 0,
            "session_count": 0,
            "pruning_pass": 0,
        }
        delta = diff_snapshots(a, b)
        assert delta["node_count"]["before"] == 3
        assert delta["node_count"]["after"] == 7

    def test_missing_keys_default_to_zero(self):
        """Missing numeric keys in either snapshot default to 0."""
        delta = diff_snapshots({}, {})
        for key in ("node_count", "edge_count", "turn_count"):
            assert delta[key]["delta"] == 0
