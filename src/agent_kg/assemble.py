# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""assemble.py — Context assembly for AgentKG.

Implements the KG-based context assembly strategy that defeats context rot:
  1. Semantic retrieval, filtered by a relevance floor -- find nodes relevant
     to the current query, dropping low-confidence hits
  2. Live-session exclusion -- never echo the caller's own live conversation
     back to it
  3. Temporal spine -- when there is no live session, include the most recent
     N turns verbatim
  4. Open tasks -- always include open Task nodes
  5. Dating -- every recalled item is stamped with the date it was recorded
  6. Token budget -- pack in priority order until budget is reached

The result is a Markdown string ready for injection into a model's context,
structured to preserve decisions and open commitments while staying token-bounded.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from agent_kg.schema import Node, NodeKind

if TYPE_CHECKING:
    from agent_kg.store import AgentKGStore

_RECENT_WINDOW = 6  # verbatim recent turns always included
_CHARS_PER_TOKEN = 4  # rough approximation

# Relevance floors, calibrated against the default embedding model on a real
# graph (kgrag_priv): measured scores were irrelevant hits 0.68-0.76 and
# relevant hits 0.77-0.83 for turns, with summaries noisier (irrelevant ones
# reaching 0.79). Hits below the floor are dropped.
_MIN_TURN_SCORE = 0.77
_MIN_SUMMARY_SCORE = 0.80

# Harness event notifications (background task / subagent completion notices)
# reach the hook as if they were user prompts. Ingest now skips them, but older
# graphs hold them as turns and inside summaries, so recall filters them too.
_NOTIFICATION_START = re.compile(r"^\s*<task-notification>")
_NOTIFICATION_BLOCK = re.compile(r"<task-notification>.*?</task-notification>", re.S)
_ROLE_TAG = re.compile(r"\[(?:USER|ASSISTANT)\]")
# Minimum characters of real content a summary must keep once notification
# blocks are stripped from it, or it is dropped as pure harness noise.
_MIN_SUMMARY_CONTENT = 40


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _text_key(text: str) -> str:
    """Normalize turn text for duplicate detection.

    :param text: Raw turn text.
    :return: Whitespace-collapsed, case-folded key.
    """
    return " ".join(text.split()).casefold()


def _date(node: Node) -> str:
    """Render a node's creation time as a local-time date stamp.

    :param node: Node carrying a ``created_at`` timestamp.
    :return: Date formatted as ``YYYY-MM-DD``.
    """
    return node.created_at.astimezone().strftime("%Y-%m-%d")


def _clean_summary(text: str) -> str:
    """Strip harness notification blocks from a summary's text.

    :param text: Raw summary text.
    :return: Cleaned text, or "" if little but notification noise remains.
    """
    cleaned = _NOTIFICATION_BLOCK.sub(" ", text)
    if cleaned == text and "<task-notification>" not in text:
        return text
    # An unclosed block (the extractive fallback cut it mid-way) cannot be
    # separated from real content safely, so drop the summary.
    if "<task-notification>" in cleaned:
        return ""
    content = _ROLE_TAG.sub("", cleaned)
    if len(" ".join(content.split())) < _MIN_SUMMARY_CONTENT:
        return ""
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def assemble_context(
    store: AgentKGStore,
    query: str,
    budget: int = 4000,
    recent_window: int = _RECENT_WINDOW,
    session_id: str | None = None,
) -> str:
    """Assemble a token-budgeted context block from the conversation graph.

    :param store: The backing :class:`~agent_kg.store.AgentKGStore`.
    :param query: The current user query (used for semantic retrieval).
    :param budget: Approximate token budget for the assembled context.
    :param recent_window: Number of most-recent turns to always include verbatim.
    :param session_id: The caller's live session (None = no live session).
    :return: Markdown-formatted context string, or "" if nothing qualifies.
    """
    # A harness notification is not a question; recalling against it only
    # surfaces older notifications.
    if _NOTIFICATION_START.match(query):
        return ""

    parts: list[str] = []
    tokens_used = 0

    def _add(text: str) -> bool:
        nonlocal tokens_used
        cost = _approx_tokens(text)
        if tokens_used + cost > budget:
            return False
        parts.append(text)
        tokens_used += cost
        return True

    # ------------------------------------------------------------------
    # Determine the live session: a session_id only counts as "live" if it
    # actually has turns. An empty session (fresh CLI/hook invocation) is
    # treated as no live session, so recall still falls back to all sessions.
    # ------------------------------------------------------------------
    live_turns = store.get_all_turns(session_id=session_id) if session_id else []
    live = session_id if live_turns else None

    # ------------------------------------------------------------------
    # 1. Open tasks — always include (commitment preservation)
    # ------------------------------------------------------------------
    open_tasks = store.get_open_tasks()
    if open_tasks:
        task_lines = [f"- ({_date(t)}) {t.label or t.text}" for t in open_tasks[:10]]
        _add("## Open Tasks\n" + "\n".join(task_lines))

    # ------------------------------------------------------------------
    # 2. Semantically relevant summaries (compressed old context)
    # ------------------------------------------------------------------
    summaries = store.search(query, k=4, kind_filter=str(NodeKind.SUMMARY))
    if summaries:
        summary_texts = []
        for s in summaries:
            if s.get("score", 0.0) < _MIN_SUMMARY_SCORE:
                continue
            node = store.get_node(s["node_id"])
            if node is None or not node.text:
                continue
            if live is not None and node.session_id == live:
                continue
            text = _clean_summary(node.text)
            if not text:
                continue
            summary_texts.append(f"**Summary** ({_date(node)}): {text[:400]}")
        if summary_texts:
            _add("## Relevant Context (Compressed)\n" + "\n\n".join(summary_texts))

    # ------------------------------------------------------------------
    # 3. Semantically relevant turns (not recent, not live-session)
    # ------------------------------------------------------------------
    # When there is no live session, prefer the current session id for the
    # verbatim window, but fall back to all sessions: every CLI and hook
    # invocation opens a fresh session, so scoping strictly to it yields an
    # empty set and the exclusion below silently does nothing. Whichever list
    # wins feeds BOTH the exclusion set here and the verbatim section at the
    # end, so a turn cannot land in both.
    recent_turns: list[Node] = []
    if live is None:
        recent_turns = store.get_all_turns(session_id=session_id)[-recent_window:]
        if not recent_turns:
            recent_turns = store.get_all_turns(session_id=None)[-recent_window:]
    recent_ids = {t.id for t in recent_turns}

    # Turns are stored without content dedup, so the same text can exist under
    # several node ids. Track text as well as id, or duplicates each pay budget.
    seen_texts = {_text_key(t.text) for t in recent_turns}

    sem_hits = store.search(query, k=6, kind_filter=str(NodeKind.TURN))
    sem_turns = []
    for h in sem_hits:
        if h.get("score", 0.0) < _MIN_TURN_SCORE:
            continue
        if h["node_id"] in recent_ids:
            continue
        node = store.get_node(h["node_id"])
        if node is None:
            continue
        if live is not None and node.session_id == live:
            continue
        if _NOTIFICATION_START.match(node.text):
            continue
        key = _text_key(node.text)
        if key in seen_texts:
            continue
        seen_texts.add(key)
        sem_turns.append(node)

    if sem_turns:
        sem_lines = []
        for t in sem_turns[:4]:
            role_label = t.role.upper() if t.role else "UNKNOWN"
            sem_lines.append(f"**[{role_label}]** ({_date(t)}) {t.text[:300]}")
        _add("## Relevant Past Turns\n" + "\n\n".join(sem_lines))

    # ------------------------------------------------------------------
    # 4. Verbatim recent turns -- only emitted when there is no live session,
    #    the same list section 3 excluded against, deduplicated by text so
    #    repeated node ids collapse to one entry.
    # ------------------------------------------------------------------
    if recent_turns:
        recent_lines = []
        emitted: set[str] = set()
        for t in recent_turns:
            key = _text_key(t.text)
            if key in emitted:
                continue
            emitted.add(key)
            role_label = t.role.upper() if t.role else "UNKNOWN"
            recent_lines.append(f"**[{role_label}]** ({_date(t)}) {t.text}")
        _add("## Recent Conversation\n" + "\n\n".join(recent_lines))

    if not parts:
        return ""

    header = (
        f"# AgentKG Context (~{tokens_used} tokens)\n"
        "_Recalled from earlier sessions. Dated; may be stale -- verify before acting._\n\n"
    )
    return header + "\n\n".join(parts)
