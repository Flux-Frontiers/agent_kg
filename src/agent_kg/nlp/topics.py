# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0
# pylint: disable=import-outside-toplevel  # intentional lazy import of spaCy

"""topics.py — Topic extraction from Turn text for AgentKG.

Extracts candidate topic labels using spaCy noun chunks (when available)
or TF-IDF-style keyword heuristics as fallback.

Returns a list of topic label strings, deduplicated and ranked by salience.
"""

from __future__ import annotations

import re

_STOP_TOPICS = frozenset(
    {
        # Pronouns
        "i",
        "we",
        "you",
        "it",
        "they",
        "he",
        "she",
        "me",
        "us",
        "him",
        "her",
        "them",
        # Demonstratives / determiners
        "the",
        "a",
        "an",
        "that",
        "this",
        "these",
        "those",
        # Adverbs / filler
        "there",
        "here",
        "now",
        "then",
        "just",
        "also",
        "very",
        # Vague nouns
        "thing",
        "things",
        "way",
        "ways",
        "time",
        "times",
        "something",
        "anything",
        "nothing",
        "everything",
        "someone",
        "anyone",
        "no one",
        "everyone",
    }
)

# Patterns that indicate high-salience code topics
_CODE_TOPIC = re.compile(
    r"\b("
    r"(?:class|function|method|module|package|file|repo|codebase|test|endpoint|api|"
    r"schema|database|query|migration|deployment|pipeline|ci|cd|auth|oauth|"
    r"refactor|bug|fix|feature|pr|branch|commit|merge|cache|redis|postgres|"
    r"typescript|python|javascript|docker|kubernetes|aws|performance|memory|"
    r"security|logging|monitoring|error|exception|async|thread|queue|stream)"
    r")\b",
    re.I,
)


def _spacy_topics(text: str) -> list[str]:
    """Extract noun-chunk topics using spaCy."""
    try:
        from agent_kg.nlp.intent import _get_spacy_doc  # noqa: PLC0415

        doc = _get_spacy_doc(text)
        if doc is None:
            return []
        topics = []
        for chunk in doc.noun_chunks:
            label = chunk.root.lemma_.lower().strip()
            if len(label) < 3 or label in _STOP_TOPICS:
                continue
            # Use full chunk if short enough and meaningful
            full = chunk.text.strip().lower()
            if 3 <= len(full.split()) <= 4 and full not in _STOP_TOPICS:
                topics.append(full)
            else:
                topics.append(label)
        return list(dict.fromkeys(topics))  # preserve order, deduplicate
    except Exception:  # pylint: disable=broad-exception-caught
        return []


def _code_keywords(text: str) -> list[str]:
    """Extract code-domain keywords and CamelCase identifiers (no bigrams)."""
    topics: list[str] = []
    for m in _CODE_TOPIC.finditer(text):
        label = m.group(1).lower()
        if label not in topics:
            topics.append(label)
    for m in re.finditer(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b", text):
        label = m.group(1).lower()
        if label not in topics and len(label) >= 4:
            topics.append(label)
    return topics


def _keyword_topics(text: str) -> list[str]:
    """Heuristic keyword-based topic extraction — used only when spaCy unavailable."""
    topics = _code_keywords(text)
    # Bigrams as last resort when there are no code keywords or identifiers
    if not topics:
        words = re.findall(r"\b[a-z][a-z0-9]{2,}\b", text.lower())
        content_words = [w for w in words if w not in _STOP_TOPICS and len(w) >= 4]
        for i in range(len(content_words) - 1):
            bigram = f"{content_words[i]} {content_words[i + 1]}"
            if bigram not in topics:
                topics.append(bigram)
    return topics[:10]


def extract_topics(text: str) -> list[str]:
    """Extract topic labels from turn text.

    Uses spaCy noun chunks when available, always supplemented with
    code-domain keyword and CamelCase extraction. Falls back to the
    full keyword heuristic (including bigrams) when spaCy is unavailable.

    :param text: Raw turn text.
    :return: List of topic label strings, most salient first.
    """
    if not text or not text.strip():
        return []
    topics = _spacy_topics(text)
    if not topics:
        topics = _keyword_topics(text)
    else:
        # Always supplement spaCy chunks with code-domain keywords not yet captured
        seen = set(topics)
        for kw in _code_keywords(text):
            if kw not in seen:
                topics.append(kw)
                seen.add(kw)
    return [t for t in topics if t not in _STOP_TOPICS][:8]
