# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""graph.py — AgentKG: the main entry point for agent conversational memory.

``AgentKG`` is the high-level façade that wires together all AgentKG components:

  - :class:`~agent_kg.store.AgentKGStore` — SQLite + sqlite-vec storage
  - :class:`~agent_kg.user_profile.UserProfileStore` — global UserProfile tree
  - :class:`~agent_kg.session.Session` — session lifecycle
  - :func:`~agent_kg.ingest.ingest_turn` — Phase 1 incremental ingest
  - :func:`~agent_kg.query.query` / :func:`~agent_kg.query.pack` — semantic query
  - :func:`~agent_kg.assemble.assemble_context` — context assembly
  - :func:`~agent_kg.prune.prune` — KG Context Pruning
  - :class:`~agent_kg.summarize.Summarizer` — LLM summarization backend

Satisfies the AgentKGAdapter contract:
  - ``AgentKG(repo_path, person_id="default")``
  - ``ag.index.search(q, k=k)`` → list of hit dicts
  - ``ag.stats()`` → {nodes, edges, node_count, edge_count}
  - ``ag.ingest(text, role)`` → IngestResult
  - ``ag.prune(token_budget)`` → PruneReport
  - ``ag.assemble_context(query, budget)`` → Markdown str
  - ``ag.query(q, k)`` → list of hit dicts
  - ``ag.pack(q, k)`` → list of snippet dicts
  - ``ag.analyze()`` → Markdown report str
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kg_utils.embed import DEFAULT_MODEL
from kg_utils.validation import MAX_HOP, MAX_MAX_NODES, bounded_int

from agent_kg import assemble, consolidate, prune, query, snapshots
from agent_kg.ingest import IngestResult, ingest_turn
from agent_kg.onboard import apply_implicit_update
from agent_kg.schema import NodeKind, PruneReport
from agent_kg.session import Session
from agent_kg.store import AgentKGStore
from agent_kg.summarize import Summarizer, SummarizerConfig
from agent_kg.user_profile import UserProfileStore, profile_dir

# Default storage layout (mirrors .pycodekg / .dockg convention)
_AGENTKG_DIR = ".agentkg"
_DB_NAME = "graph.sqlite"
_VECTORS_FILE = "vectors.sqlite"
_SNAPSHOTS_DIR = "snapshots"


class AgentKG:
    """Conversational memory as a live, queryable knowledge graph.

    Exposes both a **read** interface (query/pack/assemble_context) for
    context retrieval and a **write** interface (ingest/prune) for
    incremental updates — making it unique among KGAdapters.

    Storage layout::

        <repo>/.agentkg/
            graph.sqlite     # conversation tree
            vectors.sqlite   # semantic embeddings
            snapshots/       # temporal snapshots

        <profile root>/<person_id>/   # default root: ~/.kgrag/profiles
            userprofile.sqlite   # global UserProfile tree

    :param repo_path: Repository root (conversation tree stored here).
    :param person_id: Identifier for the user's global profile (default: ``"default"``).
    :param session_id: Resume a specific session UUID; else creates new.
    :param embed_model: Sentence-transformer model for embeddings.
    :param summarizer_config: Backend config for KG Context Pruning.
    :param profile_root: Directory holding the profiles, or ``None`` for
        ``$AGENTKG_PROFILE_ROOT``, then ``~/.kgrag/profiles``.
    :param db_path: Conversation graph; ``None`` for ``<repo>/.agentkg/graph.sqlite``.
    :param vectors_path: sqlite-vec store; ``None`` for
        ``<repo>/.agentkg/vectors.sqlite``.
    """

    def __init__(
        self,
        repo_path: str | Path,
        person_id: str = "default",
        session_id: str | None = None,
        embed_model: str | None = None,
        summarizer_config: SummarizerConfig | None = None,
        profile_root: str | Path | None = None,
        *,
        db_path: str | Path | None = None,
        vectors_path: str | Path | None = None,
    ) -> None:
        self._repo_path = Path(repo_path).resolve()
        self._person_id = person_id

        # Storage paths
        agentkg_dir = self._repo_path / _AGENTKG_DIR
        agentkg_dir.mkdir(parents=True, exist_ok=True)

        self._db_path = Path(db_path) if db_path else agentkg_dir / _DB_NAME
        self._vectors_path = Path(vectors_path) if vectors_path else agentkg_dir / _VECTORS_FILE
        self._snapshots_dir = agentkg_dir / _SNAPSHOTS_DIR
        self._profile_dir = profile_dir(person_id, profile_root)

        # Components (lazy where possible)
        self._store = AgentKGStore(
            db_path=self._db_path,
            vectors_path=self._vectors_path,
            embed_model=embed_model or DEFAULT_MODEL,
        )
        self._profile = UserProfileStore(self._profile_dir)
        self._session = Session.open(self._store, session_id=session_id)
        self._summarizer = Summarizer(summarizer_config or SummarizerConfig.from_env())

    # ------------------------------------------------------------------
    # The index property — satisfies the AgentKGAdapter stub
    # ------------------------------------------------------------------

    @property
    def repo_root(self) -> Path:
        """Repository root the conversation tree is stored in."""
        return self._repo_path

    @property
    def db_path(self) -> Path:
        """SQLite conversation graph."""
        return self._db_path

    @property
    def vectors_path(self) -> Path:
        """sqlite-vec vector store."""
        return self._vectors_path

    @property
    def model_name(self) -> str:
        """Sentence-transformer model the store embeds with."""
        return self._store._embed_model_name  # pylint: disable=protected-access

    @property
    def index(self) -> AgentKGStore:
        """Expose the store as the semantic index (has .search() method)."""
        return self._store

    # ------------------------------------------------------------------
    # Write interface
    # ------------------------------------------------------------------

    def ingest(self, text: str, role: str = "user", embed: bool = True) -> IngestResult:
        """Ingest a conversation turn into the graph (Phase 1).

        :param text: Raw turn text.
        :param role: ``"user"`` or ``"assistant"``.
        :param embed: Write embeddings immediately (default True).
        :return: :class:`~agent_kg.ingest.IngestResult` with created nodes.
        """
        result = ingest_turn(
            text=text,
            role=role,
            session=self._session,
            store=self._store,
            embed=embed,
        )
        # Apply profile updates from user turns
        if role == "user" and result.profile_updates:
            apply_implicit_update(self._profile, result.profile_updates)
        return result

    def prune(
        self,
        token_budget: int | None = None,
        window: int = 20,
        session_id: str | None = None,
    ) -> PruneReport:
        """Execute one KG Context Pruning pass (Phase 3).

        :param token_budget: Optional token budget trigger.
        :param window: Hot window — most-recent N turns are never pruned.
        :param session_id: Restrict pruning to this session's turns (None = all).
        :return: :class:`~agent_kg.schema.PruneReport` with pass statistics.
        """
        return prune.prune(
            store=self._store,
            summarizer=self._summarizer,
            session=self._session,
            window=window,
            token_budget=token_budget,
            session_id=session_id,
        )

    def consolidate(self, force: bool = False) -> dict[str, Any]:
        """Run Phase 2 background consolidation.

        :param force: Run even if below the threshold.
        :return: Report dict with ``nodes_embedded``, ``edges_created``, ``tasks_updated``.
        """
        return consolidate.consolidate(
            store=self._store,
            session_id=self._session.id,
            force=force,
        )

    # ------------------------------------------------------------------
    # Read interface (KGAdapter contract + extended)
    # ------------------------------------------------------------------

    def query(
        self,
        q: str,
        k: int = 8,
        *,
        hop: int = 0,
        max_nodes: int | None = None,
        rels: tuple[str, ...] | list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search over the conversation graph.

        :param q: Natural-language query string.
        :param k: Number of semantic hits.
        :param hop: Graph hops to bring along from each hit (0-5, default 0:
            the hits alone, as before).
        :param max_nodes: Most results, hits included; ``None`` for no cap.
        :param rels: Relations to follow when *hop* > 0; ``None`` for all.
        :return: List of enriched hit dicts, each with ``hop`` (0 for a
            semantic hit) and ``via_seed``.
        :raises ValueError: If *hop* or *max_nodes* is out of range.
        """
        self._check_expansion(hop, max_nodes)
        return query.with_neighbourhood(
            self._store, query.query(self._store, q, k=k), hop=hop, max_nodes=max_nodes, rels=rels
        )

    def pack(
        self,
        q: str,
        k: int = 8,
        *,
        hop: int = 0,
        max_nodes: int | None = None,
        rels: tuple[str, ...] | list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return conversation snippets for LLM context packing.

        :param q: Natural-language query string.
        :param k: Number of semantic snippets.
        :param hop: Graph hops to bring along from each snippet (0-5, default 0).
        :param max_nodes: Most snippets, seeds included; ``None`` for no cap.
        :param rels: Relations to follow when *hop* > 0; ``None`` for all.
        :return: List of ``{node_id, kind, content, score, hop, via_seed}`` dicts.
        :raises ValueError: If *hop* or *max_nodes* is out of range.
        """
        self._check_expansion(hop, max_nodes)
        return query.with_neighbourhood(
            self._store,
            query.pack(self._store, q, k=k),
            hop=hop,
            max_nodes=max_nodes,
            rels=rels,
            content=True,
        )

    @staticmethod
    def _check_expansion(hop: int, max_nodes: int | None) -> None:
        bounded_int("hop", hop, 0, MAX_HOP)
        if max_nodes is not None:
            bounded_int("max_nodes", max_nodes, 1, MAX_MAX_NODES)

    def node(self, node_id: str) -> dict[str, Any] | None:
        """Fetch one node of the conversation graph by its ID.

        Reads the graph only; never loads the embedding model.

        :param node_id: Node ID, e.g. from :meth:`query`.
        :return: The node as a JSON-ready dict, or ``None`` if there is none.
        """
        node = self._store.get_node(node_id)
        if node is None:
            return None
        return node.to_dict() | {"covers_turns": node.covers_turns, "metadata": node.metadata}

    def neighbors(
        self,
        node_id: str,
        *,
        rels: tuple[str, ...] | list[str] | None = None,
        direction: str = "both",
        limit: int = 50,
    ) -> dict[str, Any] | None:
        """Return a node's one-hop neighbourhood: its edges and the nodes at their far ends.

        The same contract as :meth:`kg_utils.pipeline.KGModule.neighbors`: a
        turn's topics, entities and tasks, a topic's turns, a summary's
        sources. Reads the graph only; never loads the embedding model.

        :param node_id: The node whose neighbours to return.
        :param rels: Relation types to follow, or ``None`` for all of them.
        :param direction: ``"out"``, ``"in"`` or ``"both"``.
        :param limit: Maximum number of edges, between 1 and 500.
        :return: ``{"node": ..., "edges": [...], "nodes": [...]}``, ``nodes``
            holding each distinct far-end node that exists, in edge order;
            ``None`` if *node_id* is not in the graph, matching :meth:`node`.
        :raises ValueError: On an empty *node_id*, an unknown *direction* or an
            out-of-range *limit*.
        """
        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError("node_id must be a non-empty string")
        bounded_int("limit", limit, 1, MAX_MAX_NODES)
        if direction not in ("out", "in", "both"):
            raise ValueError(f"direction must be 'out', 'in' or 'both', got {direction!r}")
        node = self.node(node_id)
        if node is None:
            return None
        edges = self._store.edges_touching(
            node_id, direction=direction, rels=list(rels) if rels else None, limit=limit
        )
        seen: set[str] = set()
        nodes: list[dict[str, Any]] = []
        for e in edges:
            other = e["dst"] if e["src"] == node_id else e["src"]
            if other in seen:
                continue
            seen.add(other)
            far = self.node(other)
            if far is not None:
                nodes.append(far)
        return {"node": node, "edges": edges, "nodes": nodes}

    def assemble_context(self, query_text: str, budget: int = 4000) -> str:
        """Assemble a token-budgeted context block from the graph.

        :param query_text: Current query (used for semantic retrieval).
        :param budget: Approximate token budget.
        :return: Markdown-formatted context string.
        """
        return assemble.assemble_context(
            store=self._store,
            query=query_text,
            budget=budget,
            session_id=self._session.id,
        )

    def stats(self) -> dict[str, Any]:
        """Return node + edge counts and session info.

        :return: Dict with ``nodes``, ``edges``, ``node_count``, ``edge_count``,
                 ``session_id``, ``turn_count``.
        """
        s = self._store.stats()
        all_turns = self._store.get_all_turns()
        return {
            **s,
            "session_id": self._session.id,
            "turn_count": len(all_turns),
            "person_id": self._person_id,
        }

    def analyze(self) -> str:
        """Return a Markdown analysis report for this AgentKG instance.

        :return: Markdown-formatted report string.
        """
        try:
            s = self._store.stats()
            turns = self._store.get_all_turns()
            open_tasks = self._store.get_open_tasks()
            sessions = self._store.list_sessions()
            summaries = self._store.get_nodes_by_kind(NodeKind.SUMMARY)
            topics = self._store.get_nodes_by_kind(NodeKind.TOPIC)
            profile_summary = self._profile.summary()
            pruning_pass = max((t.pruning_pass for t in summaries), default=0)

            lines = [
                "# AgentKG Analysis\n",
                "## Overview",
                f"- **Repo**: `{self._repo_path}`",
                f"- **Person**: `{self._person_id}`",
                f"- **Session**: `{self._session.id[:8]}…`",
                f"- **Total nodes**: {s['node_count']}",
                f"- **Total edges**: {s['edge_count']}",
                f"- **Turns**: {len(turns)}",
                f"- **Summaries**: {len(summaries)}",
                f"- **Open tasks**: {len(open_tasks)}",
                f"- **Topics tracked**: {len(topics)}",
                f"- **Sessions**: {len(sessions)}",
                f"- **Pruning passes**: {pruning_pass}",
                "",
            ]

            if open_tasks:
                lines.append("## Open Tasks")
                for t in open_tasks[:10]:
                    lines.append(f"- {t.label or t.text}")
                lines.append("")

            if topics:
                lines.append("## Active Topics")
                topic_labels = [t.label or t.text for t in topics if t.label or t.text]
                lines.append(", ".join(topic_labels[:20]))
                lines.append("")

            if summaries:
                lines.append("## Compressed History (Summaries)")
                for sm in summaries[:5]:
                    lines.append(f"**Pass {sm.pruning_pass}**: {sm.text[:200]}…")
                lines.append("")

            # UserProfile summary (skip "identity" — it's a dict, not a list of labels)
            list_sections = {k: v for k, v in profile_summary.items() if isinstance(v, list)}
            if any(list_sections.values()):
                lines.append("## UserProfile")
                for section, items in list_sections.items():
                    if items:
                        lines.append(f"**{section.title()}**: {', '.join(items[:5])}")
                lines.append("")

            if sessions:
                lines.append("## Sessions")
                for sess in sessions[-5:]:
                    tc = sess.get("turn_count", 0)
                    pp = sess.get("pruning_passes", 0)
                    st = sess.get("start_time", "")[:10]
                    lines.append(f"- `{sess['id'][:8]}…` — {st}, {tc} turns, {pp} pruning passes")
                lines.append("")

            return "\n".join(lines)

        except Exception as exc:
            return f"# AgentKG Analysis\n\nAnalysis failed: {exc}"

    # ------------------------------------------------------------------
    # Session control
    # ------------------------------------------------------------------

    def close_session(self) -> None:
        """Record end_time for the current session."""
        self._session.close()

    def snapshot(
        self,
        label: str | None = None,
        version: str | None = None,
        key: str = "",
        subject: str = "",
    ) -> snapshots.Snapshot:
        """Capture and persist a point-in-time snapshot of this AgentKG's state.

        :param label: Optional human-readable label, stored in ``metrics``.
        :param version: Version string; auto-detected from the installed
            package if not provided.
        :param key: Snapshot identifier. Pass the release tag for a repo
            snapshot; omit it for a conversation graph, which has no tag, and
            get a UTC timestamp instead.
        :param subject: What was measured, e.g. ``repo:agent-kg`` or
            ``person:eric``.
        :return: The saved :class:`~agent_kg.snapshots.Snapshot`.
        """
        mgr = snapshots.SnapshotManager(self._snapshots_dir)
        snap = mgr.capture_conversation(
            self._store, version=version, key=key, subject=subject, label=label
        )
        mgr.save_snapshot(snap)
        return snap

    @property
    def profile(self) -> UserProfileStore:
        """The UserProfile tree for direct inspection."""
        return self._profile

    @property
    def session(self) -> Session:
        """The current active session."""
        return self._session

    def should_prune(self, token_budget: int | None = None) -> bool:
        """Return True if the graph is ready for a pruning pass."""
        return prune.should_prune(self._store, token_budget=token_budget)

    def should_consolidate(self) -> bool:
        """Return True if a consolidation pass is warranted."""
        return consolidate.should_consolidate(self._store, session_id=self._session.id)

    def close(self) -> None:
        """Close all database connections and record session end."""
        self.close_session()
        self._store.close()
        self._profile.close()

    def __repr__(self) -> str:
        s = self._store.stats()
        return (
            f"AgentKG(repo={self._repo_path.name!r}, "
            f"person={self._person_id!r}, "
            f"nodes={s['node_count']}, edges={s['edge_count']})"
        )
