"""mcp/server.py — MCP tool surface for AgentKG.

Serves one repository's conversation graph to MCP clients (e.g. Claude Code)
over the fleet's shared server base, :mod:`kg_utils.mcp`.

The server answers the fleet's canonical tools -- ``stats``, ``query``,
``pack``, ``get_node``, ``neighbors`` -- under the same names as every other
KG server, plus AgentKG's own: ``ingest``, ``assemble``, ``prune``,
``topics``, ``tasks``, ``profile`` and ``analyze``. ``query`` and ``pack`` are
AgentKG's semantic recall; ``stats``, ``get_node`` and ``neighbors`` are the
shared ones.

The tool list is not kept by hand anywhere: each tool's docstring is its
description, the server's instructions are generated from them, and::

    agentkg mcp --manifest

prints the whole list as JSON without opening the graph.

Configuration via environment, as the installers write it:

  AGENTKG_REPO      — repository whose graph is served, when ``--repo`` is
                      not given (default: the working directory)
  AGENTKG_PERSON    — person ID whose profile is read (default: "default")
  AGENTKG_SESSION   — session UUID to resume (optional)

``agentkg-mcp`` is the same command as ``agentkg mcp``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from kg_utils.embed import DEFAULT_MODEL
from kg_utils.mcp import Context, KGServer, kg_from, make_server

from agent_kg import __version__
from agent_kg.graph import AgentKG
from agent_kg.schema import NodeKind

PREAMBLE = (
    "AgentKG is conversational memory as a knowledge graph. Turns of past "
    "conversations are nodes, linked to the topics, entities, intents and tasks "
    "drawn from them; pruning compresses old turns into summary nodes. A person's "
    "profile (preferences, commitments, expertise) is kept separately and spans "
    "repositories.\n\n"
    "## Recommended workflows\n\n"
    "- **Orientation**: stats, topics, tasks\n"
    "- **Recall what was said**: query → get_node, or pack for the text itself\n"
    "- **Context for the current question**: assemble with a token budget\n"
    "- **Walk from a turn**: neighbors(node_id) — its topics, entities and tasks\n"
    "- **Remember something**: ingest a turn"
)


def query(
    q: str,
    k: int = 8,
    hop: int = 0,
    max_nodes: int = 25,
    rels: list[str] | None = None,
    *,
    ctx: Context,
) -> dict[str, Any]:
    """
    Semantic recall over past conversations: ranked turns, summaries, topics and tasks.

    :param q: Natural-language query.
    :param k: Semantic hits (default 8).
    :param hop: Graph hops to bring along from each hit (0-5, default 0: the
        hits alone).
    :param max_nodes: Most results, hits included (default 25).
    :param rels: Edge types to follow when hop > 0; omit for all of them.
    """
    return {"query": q, "hits": kg_from(ctx).query(q, k=k, hop=hop, max_nodes=max_nodes, rels=rels)}


def pack(
    q: str,
    k: int = 6,
    hop: int = 0,
    max_nodes: int = 15,
    rels: list[str] | None = None,
    *,
    ctx: Context,
) -> str:
    """
    Conversation snippets for the query, summaries first, as text ready for a prompt.

    :param q: Natural-language query.
    :param k: Semantic snippets (default 6).
    :param hop: Graph hops to bring along from each snippet (0-5, default 0).
    :param max_nodes: Most snippets, seeds included (default 15).
    :param rels: Edge types to follow when hop > 0; omit for all of them.
    """
    snippets = kg_from(ctx).pack(q, k=k, hop=hop, max_nodes=max_nodes, rels=rels)
    parts = [f"[{s.get('kind')}] {s.get('content', '')}" for s in snippets]
    return "\n\n---\n\n".join(parts) or "No snippets found."


def ingest(turn_text: str, role: str = "user", *, ctx: Context) -> str:
    """
    Add a conversation turn to the graph, extracting its topics, entities and tasks.

    :param turn_text: The turn's text.
    :param role: "user" or "assistant" (default "user"). User turns also update the profile.
    """
    if role not in ("user", "assistant"):
        raise ValueError(f"role must be 'user' or 'assistant', got {role!r}")
    result = kg_from(ctx).ingest(text=turn_text, role=role)
    return (
        f"Ingested turn (role={role}).\n"
        f"Topics: {[t.label for t in result.topic_nodes]}\n"
        f"Entities: {[e.label for e in result.entity_nodes]}\n"
        f"Tasks: {[t.label for t in result.task_nodes]}\n"
        f"Profile updates: {len(result.profile_updates)}"
    )


def assemble(q: str, budget: int = 4000, *, ctx: Context) -> str:
    """
    A token-budgeted Markdown context block for the current question, drawn from the whole graph.

    :param q: The current question, used for semantic retrieval.
    :param budget: Approximate token budget (default 4000).
    """
    return kg_from(ctx).assemble_context(q, budget=budget) or "No relevant context found."


def prune(window: int = 20, *, ctx: Context) -> str:
    """
    Compress old turns into summary nodes (KG Context Pruning); the newest turns are kept.

    :param window: Most recent turns never pruned (default 20).
    """
    kg = kg_from(ctx)
    if not kg.should_prune():
        return "Not enough cold turns to prune yet."
    report = kg.prune(window=window)
    return (
        f"Pruning pass {report.pruning_pass} complete.\n"
        f"Summaries created: {report.summaries_created}\n"
        f"Turns pruned: {report.turns_pruned}\n"
        f"Nodes removed: {report.nodes_removed}\n"
        f"Token savings ~{report.token_savings_approx}"
    )


def topics(*, ctx: Context) -> str:
    """
    Every topic tracked in the conversation graph, with when it was last seen.
    """
    found = kg_from(ctx).index.get_nodes_by_kind(NodeKind.TOPIC)
    if not found:
        return "No topics tracked yet."
    lines = [
        f"- {t.label or t.text} (last seen: {t.last_seen.strftime('%Y-%m-%d')})" for t in found
    ]
    return f"Topics ({len(found)}):\n" + "\n".join(lines)


def tasks(*, ctx: Context) -> str:
    """
    Open tasks extracted from the conversation.
    """
    found = kg_from(ctx).index.get_open_tasks()
    if not found:
        return "No open tasks."
    return f"Open tasks ({len(found)}):\n" + "\n".join(
        f"- [{t.status}] {t.label or t.text}" for t in found
    )


def profile(person_id: str | None = None, *, ctx: Context) -> str:
    """
    A person's profile — preferences, commitments, expertise — as Markdown.

    :param person_id: Whose profile; omit for the person this server serves (AGENTKG_PERSON).
    """
    if person_id is None:
        return kg_from(ctx).profile.render_markdown()
    from agent_kg.user_profile import (  # pylint: disable=import-outside-toplevel
        UserProfileStore,
        profile_dir,
    )

    store = UserProfileStore(profile_dir(person_id))
    try:
        return store.render_markdown()
    finally:
        store.close()


def analyze(*, ctx: Context) -> str:
    """
    A full Markdown analysis report of the conversation graph.
    """
    return kg_from(ctx).analyze()


EXTRA_TOOLS = (ingest, assemble, prune, topics, tasks, profile, analyze)


def build_server(
    repo: str | Path,
    db: str | Path | None = None,
    vectors: str | Path | None = None,
    model: str | None = None,
) -> KGServer:
    """Build the AgentKG MCP server for one repository, without opening its graph.

    The person and the session to resume come from ``AGENTKG_PERSON`` and
    ``AGENTKG_SESSION``, read when a client session opens the graph.

    :param repo: Repository whose ``.agentkg/`` graph is served.
    :param db: Graph database; ``None`` for ``<repo>/.agentkg/graph.sqlite``.
    :param vectors: Vector store; ``None`` for ``<repo>/.agentkg/vectors.sqlite``.
    :param model: Embedding model; ``None`` for the fleet default.
    :return: The server; serve it with :func:`kg_utils.mcp.run`.
    """
    root = Path(repo).resolve()

    def open_kg() -> AgentKG:
        return AgentKG(
            root,
            person_id=os.environ.get("AGENTKG_PERSON", "default"),
            session_id=os.environ.get("AGENTKG_SESSION") or None,
            embed_model=model or DEFAULT_MODEL,
            db_path=db,
            vectors_path=vectors,
        )

    server = make_server(
        open_kg, name="agentkg", kind="agent", version=__version__, instructions=PREAMBLE
    )
    server.canonical("query")(query)
    server.canonical("pack")(pack)
    for tool in EXTRA_TOOLS:
        server.tool()(tool)
    return server


def main(argv: list[str] | None = None) -> None:
    """Entry point for ``agentkg-mcp``: the same command as ``agentkg mcp``.

    :param argv: Arguments; ``None`` for ``sys.argv[1:]``.
    """
    from agent_kg.cli.main import mcp_command  # pylint: disable=import-outside-toplevel

    mcp_command.main(args=argv, prog_name="agentkg-mcp")


if __name__ == "__main__":
    main()
