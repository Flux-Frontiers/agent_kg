"""query.py — Semantic query and snippet pack for AgentKG.

Delegates to the sqlite-vec semantic index in AgentKGStore.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from agent_kg.schema import NodeKind

if TYPE_CHECKING:
    from agent_kg.store import AgentKGStore


def query(
    store: AgentKGStore,
    q: str,
    k: int = 8,
    kind_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Semantic query over the conversation graph.

    :param store: The backing store.
    :param q: Natural-language query string.
    :param k: Number of results.
    :param kind_filter: Optional NodeKind string to restrict results.
    :return: List of ``{node_id, kind, text, session_id, score}`` dicts,
             enriched with full node data from SQLite.
    """
    hits = store.search(q, k=k, kind_filter=kind_filter)
    enriched = []
    for h in hits:
        node = store.get_node(h["node_id"])
        if node:
            enriched.append(
                {
                    "node_id": h["node_id"],
                    "kind": h["kind"],
                    "text": node.text or node.label,
                    "label": node.label,
                    "role": node.role,
                    "turn_index": node.turn_index,
                    "session_id": h["session_id"],
                    "score": h["score"],
                    "status": node.status,
                    "created_at": node.created_at.isoformat(),
                    "metadata": node.temporal(),
                }
            )
        else:
            enriched.append(h)
    return enriched


def pack(
    store: AgentKGStore,
    q: str,
    k: int = 8,
) -> list[dict[str, Any]]:
    """Retrieve conversation snippets for LLM context packing.

    Returns formatted text blocks ready for injection into a prompt,
    prioritising Summaries and Turns over structural nodes.

    :param store: The backing store.
    :param q: Natural-language query string.
    :param k: Number of snippets to return.
    :return: List of ``{node_id, kind, content, score}`` dicts.
    """
    results: list[dict[str, Any]] = []
    # Prefer summaries first (they represent compressed history)
    summaries = store.search(q, k=k // 2 + 1, kind_filter=str(NodeKind.SUMMARY))
    turns = store.search(q, k=k, kind_filter=str(NodeKind.TURN))

    seen: set[str] = set()

    def _add(hits: list[dict], prefix: str = "") -> None:
        for h in hits:
            if h["node_id"] in seen or len(results) >= k:
                return
            seen.add(h["node_id"])
            node = store.get_node(h["node_id"])
            content = node.text if node else h.get("text", "")
            if prefix and node and node.role:
                content = f"[{node.role.upper()}] {content}"
            results.append(
                {
                    "node_id": h["node_id"],
                    "kind": h["kind"],
                    "content": content,
                    "score": h["score"],
                    "metadata": node.temporal() if node else {},
                }
            )

    _add(summaries, prefix="summary")
    _add(turns, prefix="turn")

    # Fill remaining slots with any other relevant nodes
    if len(results) < k:
        others = store.search(q, k=k - len(results))
        _add(others)

    return results


#: Most nodes a single hop may expand from, so a hub topic cannot fan out
#: across the whole graph -- the same cap doc_kg's expansion uses.
_MAX_FRONTIER = 5_000


def expand(
    store: AgentKGStore,
    seeds: Sequence[tuple[str, float]],
    *,
    hop: int,
    rels: Sequence[str] | None = None,
) -> list[tuple[str, float, int, str]]:
    """Return the nodes up to *hop* edges from *seeds*, ranked after them.

    Edges are followed in both directions. Each node reached is recorded once,
    at its smallest hop distance, scored ``seed_score / (1 + hops)`` from the
    seed it was first reached from, and ordered by hop distance, then by that
    seed's score, then by id.

    :param store: The backing store.
    :param seeds: ``(node_id, score)`` pairs, best first.
    :param hop: Hops to expand.
    :param rels: Relations to follow, or ``None`` for all of them.
    :return: ``(node_id, score, hop, via_seed)`` for every node reached, seeds
        excluded.
    """
    seed_score = dict(seeds)
    seen: set[str] = set(seed_score)
    via: dict[str, str] = {nid: nid for nid in seed_score}
    frontier = [nid for nid, _ in seeds]
    reached: list[tuple[str, float, int, str]] = []
    for h in range(1, hop + 1):
        found: list[tuple[str, float, int, str]] = []
        for nid in frontier[:_MAX_FRONTIER]:
            for e in store.edges_touching(nid, rels=rels):
                other = e["dst"] if e["src"] == nid else e["src"]
                if other in seen:
                    continue
                seen.add(other)
                via[other] = via[nid]
                found.append((other, seed_score[via[nid]] / (1 + h), h, via[nid]))
        found.sort(key=lambda t: (-seed_score[t[3]], t[0]))
        reached += found
        frontier = [t[0] for t in found]
    return reached


def _expanded(
    store: AgentKGStore, node_id: str, score: float, hops: int, via_seed: str, *, content: bool
) -> dict[str, Any] | None:
    """Shape a node reached by :func:`expand` like a :func:`query` hit or a :func:`pack` snippet."""
    node = store.get_node(node_id)
    if node is None:
        return None
    if content:
        shaped: dict[str, Any] = {
            "node_id": node_id,
            "kind": str(node.kind),
            "content": node.text or node.label,
        }
    else:
        shaped = {
            "node_id": node_id,
            "kind": str(node.kind),
            "text": node.text or node.label,
            "label": node.label,
            "role": node.role,
            "turn_index": node.turn_index,
            "session_id": node.session_id,
            "status": node.status,
            "created_at": node.created_at.isoformat(),
        }
    return shaped | {"score": score, "metadata": node.temporal(), "hop": hops, "via_seed": via_seed}


def with_neighbourhood(
    store: AgentKGStore,
    hits: list[dict[str, Any]],
    *,
    hop: int,
    max_nodes: int | None,
    rels: Sequence[str] | None,
    content: bool = False,
) -> list[dict[str, Any]]:
    """Mark *hits* as seeds and append the nodes *hop* edges from them.

    With ``hop=0`` the hits come back unchanged apart from their ``hop`` and
    ``via_seed`` keys, so the old results are preserved exactly.

    :param store: The backing store.
    :param hits: Seed hits from :func:`query` or :func:`pack`, best first.
    :param hop: Hops to expand.
    :param max_nodes: Most results, seeds included; ``None`` for no cap.
    :param rels: Relations to follow, or ``None`` for all of them.
    :param content: Shape expanded nodes as :func:`pack` snippets, not hits.
    :return: The seeds, then the expanded nodes.
    """
    out = [{**h, "hop": 0, "via_seed": h["node_id"]} for h in hits]
    if hop:
        seeds = [(h["node_id"], h.get("score", 0.0)) for h in hits]
        for nid, score, hops, via_seed in expand(store, seeds, hop=hop, rels=rels):
            shaped = _expanded(store, nid, score, hops, via_seed, content=content)
            if shaped is not None:
                out.append(shaped)
    return out if max_nodes is None else out[:max_nodes]
