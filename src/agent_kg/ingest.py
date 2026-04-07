# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""ingest.py — Phase 1 incremental turn ingestion for AgentKG.

On every conversation turn:
  1. Create a Turn node
  2. Run NLP pipeline (intent, entities, topics)
  3. Deduplicate entities + topics against existing nodes
  4. Create/update linked nodes (Intent, Entity, Topic, Task)
  5. Add structural edges (FOLLOWS, ADDRESSES, EXPRESSES, MENTIONS, CREATES)
  6. Embed all new nodes into LanceDB (async-friendly: called by caller)

Also handles implicit UserProfile updates (preferences, commitments, expertise)
by delegating to the profile module.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from agent_kg.nlp import classify_intent, extract_entities, extract_preferences, extract_topics
from agent_kg.schema import Edge, EdgeRelation, Node, NodeKind, TaskStatus

# Tags injected by Claude Code (IDE context, system reminders, hook markers) that
# should be stripped from text before NLP to prevent topic/entity pollution.
_XML_TAG = re.compile(r"<[a-zA-Z_][\w_-]*(?:\s[^>]*)?>.*?</[a-zA-Z_][\w_-]*>", re.DOTALL)
_SELF_CLOSING_TAG = re.compile(r"<[a-zA-Z_][\w_-]*(?:\s[^>]*)?/>")
_SESSION_SENTINEL = re.compile(r"^\s*Session ended\.\s*$", re.MULTILINE)

# Slash commands (e.g. /changelog-commit) start with / followed by a word character.
_SLASH_COMMAND = re.compile(r"^\s*/\w")

# Minimum characters required after XML tag stripping to be worth ingesting.
# Set to 2 to catch truly empty turns (pure system-tag content) without
# rejecting any short but valid turn like "Hi." or "OK".
_MIN_CONTENT_CHARS = 2


def _should_skip_turn(text: str) -> bool:
    """Return True if this turn should be silently skipped at ingest time.

    Turns that are noise from the Claude Code harness — slash commands,
    near-empty turns after tag stripping, session sentinels — pollute the
    graph with unhelpful nodes and degrade search quality.

    :param text: Raw turn text (before any cleaning).
    :return: True if the turn should not be ingested.
    """
    # Skip slash commands (e.g. /changelog-commit, /release)
    if _SLASH_COMMAND.match(text):
        return True
    # Skip session-end sentinels
    if _SESSION_SENTINEL.match(text):
        return True
    # Skip turns that are effectively empty after stripping XML tags
    stripped = _XML_TAG.sub("", text)
    stripped = _SELF_CLOSING_TAG.sub("", stripped).strip()
    if len(stripped) < _MIN_CONTENT_CHARS:
        return True
    return False


def _clean_for_nlp(text: str) -> str:
    """Strip system/IDE context tags before NLP processing.

    Removes ``<ide_opened_file>``, ``<system-reminder>``, and other
    XML-like tags injected by the Claude Code harness, as well as
    session-end sentinel lines.  The raw ``text`` is still stored on the
    Turn node; only NLP extraction runs on the cleaned version.

    :param text: Raw turn text, potentially containing system tags.
    :return: Cleaned text suitable for intent/topic/entity extraction.
    """
    cleaned = _XML_TAG.sub(" ", text)
    cleaned = _SELF_CLOSING_TAG.sub(" ", cleaned)
    cleaned = _SESSION_SENTINEL.sub(" ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


if TYPE_CHECKING:
    from agent_kg.session import Session
    from agent_kg.store import AgentKGStore

# --- Task extraction heuristics ------------------------------------------------

_TASK_IMPERATIVE = re.compile(
    r"^\s*(?:please\s+)?(?:can\s+you\s+|could\s+you\s+|would\s+you\s+)?"
    r"((?:add|create|write|implement|build|fix|update|remove|delete|refactor|"
    r"run|test|deploy|generate|make|set\s+up|configure|install|check|review)"
    r"\s+.{5,80}?)(?:\.|$)",
    re.I,
)

_TASK_RESOLUTION = re.compile(
    r"\b(?:done|finished|completed|fixed|resolved|implemented|added|removed|"
    r"working\s+now|looks\s+good|that\s+works?)\b",
    re.I,
)


def _extract_tasks(text: str) -> list[str]:
    """Extract candidate task descriptions from imperative sentences."""
    tasks = []
    for m in _TASK_IMPERATIVE.finditer(text):
        desc = m.group(1).strip().rstrip(".,;!")
        if len(desc) >= 8:
            tasks.append(desc)
    return tasks[:3]


def _looks_like_resolution(text: str) -> bool:
    """Return True if this turn appears to resolve/complete a task."""
    return bool(_TASK_RESOLUTION.search(text))


# -------------------------------------------------------------------------------


class IngestResult:
    """Result of ingesting a single turn.

    :param turn_node: The created Turn node.
    :param intent_node: The created Intent node (may be None).
    :param topic_nodes: Topic nodes created or merged.
    :param entity_nodes: Entity nodes created or merged.
    :param task_nodes: Task nodes created.
    :param edges_created: Number of new edges added.
    :param profile_updates: Preference/commitment/expertise records found.
    """

    def __init__(self) -> None:
        self.turn_node: Node | None = None
        self.intent_node: Node | None = None
        self.topic_nodes: list[Node] = []
        self.entity_nodes: list[Node] = []
        self.task_nodes: list[Node] = []
        self.edges_created: int = 0
        self.profile_updates: list[dict[str, Any]] = []
        self.skipped: bool = False

    def __repr__(self) -> str:
        if self.skipped:
            return "IngestResult(skipped=True)"
        return (
            f"IngestResult(topics={len(self.topic_nodes)}, "
            f"entities={len(self.entity_nodes)}, tasks={len(self.task_nodes)}, "
            f"profile_updates={len(self.profile_updates)})"
        )


def ingest_turn(
    text: str,
    role: str,
    session: Session,
    store: AgentKGStore,
    embed: bool = True,
) -> IngestResult:
    """Ingest a single conversation turn into the AgentKG.

    Phase 1 — runs synchronously. Embedding (LanceDB writes) is included
    when ``embed=True`` (default). Set ``embed=False`` for deferred batch
    embedding via :func:`~agent_kg.consolidate.consolidate`.

    :param text: Raw turn text.
    :param role: ``"user"`` or ``"assistant"``.
    :param session: Active :class:`~agent_kg.session.Session`.
    :param store: Backing :class:`~agent_kg.store.AgentKGStore`.
    :param embed: Whether to write embeddings immediately (default True).
    :return: :class:`IngestResult` with all created/merged nodes.
    """
    result = IngestResult()

    # Skip noise turns (slash commands, empty-after-stripping, session sentinels)
    if _should_skip_turn(text):
        result.skipped = True
        return result

    now = datetime.now(UTC)
    turn_idx = session.next_turn_index()

    # Clean text for NLP (strips IDE/system tags); raw text kept on Turn node.
    nlp_text = _clean_for_nlp(text)

    # ------------------------------------------------------------------
    # 1. Create Turn node
    # ------------------------------------------------------------------
    token_count = len(text.split())  # rough approximation
    turn_node = Node(
        kind=NodeKind.TURN,
        label=text[:80],
        text=text,
        role=role,
        turn_index=turn_idx,
        token_count=token_count,
        session_id=session.id,
        created_at=now,
        updated_at=now,
        first_seen=now,
        last_seen=now,
    )
    store.upsert_node(turn_node)
    if embed:
        store.embed_node(turn_node)
    result.turn_node = turn_node

    # ------------------------------------------------------------------
    # 2. FOLLOWS edge from previous turn
    # ------------------------------------------------------------------
    all_turns = store.get_all_turns(session_id=session.id)
    prev_turns = [t for t in all_turns if t.turn_index < turn_idx and t.id != turn_node.id]
    if prev_turns:
        prev = max(prev_turns, key=lambda t: t.turn_index)
        store.add_edge(
            Edge(source_id=prev.id, target_id=turn_node.id, relation=EdgeRelation.FOLLOWS)
        )
        result.edges_created += 1

    # ------------------------------------------------------------------
    # 3. Intent classification
    # ------------------------------------------------------------------
    category = classify_intent(nlp_text)
    intent_node = Node(
        kind=NodeKind.INTENT,
        label=str(category),
        text=text[:200],
        category=str(category),
        session_id=session.id,
        created_at=now,
        updated_at=now,
        first_seen=now,
        last_seen=now,
    )
    store.upsert_node(intent_node)
    store.add_edge(
        Edge(source_id=turn_node.id, target_id=intent_node.id, relation=EdgeRelation.EXPRESSES)
    )
    result.intent_node = intent_node
    result.edges_created += 1

    # ------------------------------------------------------------------
    # 4. Topic extraction + dedup
    # ------------------------------------------------------------------
    topic_labels = extract_topics(nlp_text)
    seen_topic_labels: set[str] = set()
    for label in topic_labels:
        key = label.lower().strip()
        if key in seen_topic_labels:
            continue
        seen_topic_labels.add(key)
        # Try to merge with existing topic
        existing = store.find_similar_node(label, NodeKind.TOPIC, threshold=0.88)
        if existing:
            store.update_node_field(existing.id, "last_seen", now.isoformat())
            topic_node = existing
        else:
            topic_node = Node(
                kind=NodeKind.TOPIC,
                label=label,
                text=label,
                session_id=session.id,
                created_at=now,
                updated_at=now,
                first_seen=now,
                last_seen=now,
            )
            store.upsert_node(topic_node)
            if embed:
                store.embed_node(topic_node)
        store.add_edge(
            Edge(source_id=turn_node.id, target_id=topic_node.id, relation=EdgeRelation.ADDRESSES)
        )
        result.topic_nodes.append(topic_node)
        result.edges_created += 1

    # ------------------------------------------------------------------
    # 5. Entity extraction + dedup
    # ------------------------------------------------------------------
    entities = extract_entities(nlp_text)
    seen_entity_labels: set[str] = set()
    for ent in entities:
        label = ent["label"]
        key = label.lower().strip()
        if key in seen_entity_labels:
            continue
        seen_entity_labels.add(key)
        kind_str = ent.get("kind", "concept")
        existing = store.find_similar_node(label, NodeKind.ENTITY, threshold=0.90)
        if existing:
            store.update_node_field(existing.id, "last_seen", now.isoformat())
            entity_node = existing
        else:
            entity_node = Node(
                kind=NodeKind.ENTITY,
                label=label,
                text=label,
                source=kind_str,
                session_id=session.id,
                created_at=now,
                updated_at=now,
                first_seen=now,
                last_seen=now,
            )
            store.upsert_node(entity_node)
            if embed:
                store.embed_node(entity_node)
        store.add_edge(
            Edge(source_id=turn_node.id, target_id=entity_node.id, relation=EdgeRelation.MENTIONS)
        )
        result.entity_nodes.append(entity_node)
        result.edges_created += 1

    # ------------------------------------------------------------------
    # 6. Task extraction (user turns only)
    # ------------------------------------------------------------------
    if role == "user":
        task_descs = _extract_tasks(nlp_text)
        for desc in task_descs:
            task_node = Node(
                kind=NodeKind.TASK,
                label=desc[:80],
                text=desc,
                status=str(TaskStatus.OPEN),
                session_id=session.id,
                created_at=now,
                updated_at=now,
                first_seen=now,
                last_seen=now,
            )
            store.upsert_node(task_node)
            if embed:
                store.embed_node(task_node)
            store.add_edge(
                Edge(source_id=turn_node.id, target_id=task_node.id, relation=EdgeRelation.CREATES)
            )
            result.task_nodes.append(task_node)
            result.edges_created += 1

    # 6b. Task resolution detection
    if _looks_like_resolution(nlp_text):
        open_tasks = store.get_open_tasks()
        for task in open_tasks:
            # Naively resolve the most recent open task
            store.update_node_field(task.id, "status", str(TaskStatus.COMPLETED))
            store.add_edge(
                Edge(source_id=turn_node.id, target_id=task.id, relation=EdgeRelation.RESOLVES)
            )
            result.edges_created += 1
            break  # only resolve the most recent

    # ------------------------------------------------------------------
    # 7. Profile update signals (user turns only)
    # ------------------------------------------------------------------
    if role == "user":
        prefs = extract_preferences(nlp_text)
        result.profile_updates = prefs

    session.record_turn()
    return result
