# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""snapshots.py — Temporal snapshot support for AgentKG.

Thin layer over the shared ``kg_utils.snapshots`` module, the same
infrastructure every other KG module in the fleet uses.

``Snapshot``, ``SnapshotManifest`` and ``PruneResult`` are re-exported from
``kg_utils.snapshots`` unchanged. This module adds ``SnapshotManager``, which
sets ``package_name="agent-kg"`` and builds the AgentKG-specific metrics dict
in ``capture_conversation()``: node/edge counts, turn count, summary count,
open task count, session count, and the pruning pass, plus ``turns_delta``,
``summaries_delta`` and ``open_tasks_delta`` in the computed delta.

Before this, AgentKG hand-rolled its own ``capture``/``list_snapshots``/
``diff_snapshots`` functions with no relationship to the shared model: no tag
keying, no manifest, no ``subject``/``tool``/``tool_version`` provenance, and
none of the fixes the rest of the fleet's snapshot infrastructure has had.
Snapshots were filed under a timestamp-only filename in
``<repo>/.agentkg/snapshots/`` with no index. That directory layout is
unchanged; the files in it now carry the shared schema.

Do not subclass ``Snapshot`` here, and do not reimplement ``save_snapshot``,
``load_snapshot``, ``get_previous``, ``get_baseline`` or ``diff_snapshots``.
That pattern is what let a real bug ship in two sibling repos -- see
``kgrag_priv/docs/SNAPSHOT_SUBCLASS_RETIREMENT.md``.

Usage
-----
>>> from agent_kg.snapshots import SnapshotManager
>>> mgr = SnapshotManager(".agentkg/snapshots")
>>> snapshot = mgr.capture_conversation(store, version="0.10.0", key="v0.10.0",
...                                      subject="repo:agent-kg")
>>> mgr.save_snapshot(snapshot)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kg_utils.snapshots import PruneResult as PruneResult  # noqa: F401 -- re-exported
from kg_utils.snapshots import Snapshot as Snapshot  # noqa: F401 -- re-exported
from kg_utils.snapshots import SnapshotManager as _BaseSnapshotManager
from kg_utils.snapshots import SnapshotManifest as SnapshotManifest  # noqa: F401 -- re-exported

from agent_kg.schema import NodeKind

if TYPE_CHECKING:
    from pathlib import Path

    from agent_kg.store import AgentKGStore

__all__ = [
    "PruneResult",
    "Snapshot",
    "SnapshotManager",
    "SnapshotManifest",
]


class SnapshotManager(_BaseSnapshotManager):
    """AgentKG snapshot manager.

    Subclasses the shared ``kg_utils.snapshots.SnapshotManager`` and adds:

    * ``package_name="agent-kg"`` default for version detection.
    * ``capture_conversation()``, which reads the store for node/edge counts,
      turn count, summary count, open task count, session count and the
      current pruning pass, and delegates to the shared ``capture()``.
    * ``_compute_delta_from_metrics`` extended with ``turns_delta``,
      ``summaries_delta`` and ``open_tasks_delta``.

    Everything else -- saving, loading, listing, pruning, key handling -- is
    inherited unchanged.
    """

    def __init__(
        self,
        snapshots_dir: Path | str,
        *,
        package_name: str = "agent-kg",
    ) -> None:
        """Initialize the manager rooted at ``snapshots_dir``.

        :param snapshots_dir: Directory holding snapshot JSON and the manifest.
        :param package_name: Package name used for version detection.
        """
        super().__init__(snapshots_dir, package_name=package_name)

    # ------------------------------------------------------------------
    # capture_conversation — build the AgentKG metrics dict
    # ------------------------------------------------------------------

    def capture_conversation(
        self,
        store: AgentKGStore,
        version: str | None = None,
        branch: str | None = None,
        key: str = "",
        subject: str = "",
        label: str | None = None,
    ) -> Snapshot:
        """Capture a snapshot of the current AgentKG conversation-tree state.

        :param store: The backing store to read metrics from.
        :param version: Version string; auto-detected from the installed
            package if not provided.
        :param branch: Git branch; auto-detected if ``None``.
        :param key: Snapshot identifier. Pass the release tag for a repo
            snapshot; omit it for a conversation graph, which has no tag, and
            get a UTC timestamp instead -- the same convention as every other
            KG module.
        :param subject: What was measured, e.g. ``repo:agent-kg`` or
            ``person:eric``. Recorded separately from ``version``, which
            names the measuring tool.
        :param label: Optional human-readable label, stored in ``metrics``.
        :return: New :class:`~kg_utils.snapshots.Snapshot` (not yet persisted).
        """
        stats = store.stats()
        turns = store.get_all_turns()
        open_tasks = store.get_open_tasks()
        summaries = store.get_nodes_by_kind(NodeKind.SUMMARY)
        sessions = store.list_sessions()

        pruning_pass = 0
        if turns:
            pruning_pass = max(t.pruning_pass for t in turns)
        elif summaries:
            pruning_pass = max(s.pruning_pass for s in summaries)

        metrics: dict[str, Any] = {
            "total_nodes": stats["node_count"],
            "total_edges": stats["edge_count"],
            "node_counts": stats.get("kind_counts", {}),
            "turn_count": len(turns),
            "summary_count": len(summaries),
            "open_task_count": len(open_tasks),
            "session_count": len(sessions),
            "pruning_pass": pruning_pass,
        }
        if label is not None:
            metrics["label"] = label

        return super().capture(
            version=version,
            branch=branch,
            graph_stats_dict=metrics,
            key=key,
            subject=subject,
        )

    # ------------------------------------------------------------------
    # Delta computation — adds turns_delta, summaries_delta, open_tasks_delta
    # ------------------------------------------------------------------

    def _compute_delta_from_metrics(
        self, new_m: dict[str, Any], old_m: dict[str, Any]
    ) -> dict[str, Any]:
        """Compute delta dict including AgentKG-specific fields."""
        base = super()._compute_delta_from_metrics(new_m, old_m)
        base["turns_delta"] = new_m.get("turn_count", 0) - old_m.get("turn_count", 0)
        base["summaries_delta"] = new_m.get("summary_count", 0) - old_m.get("summary_count", 0)
        base["open_tasks_delta"] = new_m.get("open_task_count", 0) - old_m.get("open_task_count", 0)
        return base
