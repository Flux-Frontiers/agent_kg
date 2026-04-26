# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0
# pylint: disable=line-too-long,import-outside-toplevel

"""intent.py — Intent classification for AgentKG Turn nodes.

Two-stage pipeline:
  Stage 1 — Syntactic signals via spaCy (if available).
  Stage 2 — Regex/keyword heuristics as fallback.

Result is one of: question | request | instruction | code_request | bug_report | task |
                  correction | confirmation | clarification | context | feedback | unknown
"""

from __future__ import annotations

import re
from typing import Any

from agent_kg.schema import IntentCategory

# Regex patterns for heuristic classification
_QUESTION_PATTERNS = [
    re.compile(
        r"^\s*(what|who|where|when|why|how|which|is|are|was|were|do|does|did|can|could|should|would|will)\b",
        re.I,
    ),
    re.compile(r"\?\s*$"),
]
_CORRECTION_PATTERNS = [
    re.compile(
        r"\b(no,?\s+)?(actually|that'?s?\s+(not|wrong|incorrect)|don'?t|shouldn'?t|never|stop|don'?t\s+do|i\s+said)\b",
        re.I,
    ),
    re.compile(r"^\s*(no|nope|wrong|incorrect|not\s+quite|not\s+right)\b", re.I),
]
_CONFIRMATION_PATTERNS = [
    re.compile(
        r"^\s*(yes|yeah|yep|correct|exactly|right|that'?s?\s+(right|correct|good|perfect)|looks?\s+good|perfect|great|nice|ok|okay)\b",
        re.I,
    ),
]
_REQUEST_PATTERNS = [
    re.compile(
        r"^\s*(please|can\s+you|could\s+you|would\s+you|make|create|add|remove|update|change|fix|write|implement|build|run|show|tell|explain|help|give)\b",
        re.I,
    ),
]
_CLARIFICATION_PATTERNS = [
    re.compile(
        r"\b(what\s+do\s+you\s+mean|clarif|explain\s+further|more\s+detail|elaborate|not\s+sure\s+i\s+understand)\b",
        re.I,
    ),
]
_FEEDBACK_PATTERNS = [
    re.compile(
        r"\b(looks?\s+(good|great|nice|bad|wrong)|that\s+(works|worked|helped|didn'?t\s+work)|good\s+job|well\s+done|thanks?|thank\s+you)\b",
        re.I,
    ),
]
_INSTRUCTION_PATTERNS = [
    # Direct imperative directives that modify existing state: "get rid of that",
    # "perform @file", "remove X", "disable Y", "turn off Z"
    # Excludes add/fix/change/update/replace/set — those are covered by REQUEST_PATTERNS.
    re.compile(
        r"^\s*(remove|delete|rename|move|revert|get\s+rid\s+of|"
        r"perform|apply|switch|enable|disable|turn\s+(on|off))\b",
        re.I,
    ),
]
_CODE_REQUEST_PATTERNS = [
    re.compile(
        r"^\s*(write|implement|build|create|generate|scaffold|code|make\s+a|make\s+me|"
        r"develop|define|declare|stub|draft)\b",
        re.I,
    ),
    re.compile(
        r"\b(write\s+(a|the|some)\s+(function|class|method|test|script|module|handler|"
        r"endpoint|decorator|schema|migration|query|util|helper))\b",
        re.I,
    ),
]
_BUG_REPORT_PATTERNS = [
    re.compile(
        r"\b(bug|traceback|crash(ed|ing)?|broken|doesn'?t\s+work|not\s+working|"
        r"wrong\s+output|unexpected\s+(behavior|result|output)|raises?|throws?|"
        r"AttributeError|TypeError|ValueError|KeyError|"
        r"ImportError|ModuleNotFoundError|RuntimeError|IndexError|NameError)\b",
        re.I,
    ),
]
_TASK_PATTERNS = [
    re.compile(
        r"\b(todo|to.do|to-do|task|ticket|issue|story|milestone|action\s+item|"
        r"follow.?up|track|assign|open\s+(an?\s+)?(issue|ticket)|create\s+(an?\s+)?ticket)\b",
        re.I,
    ),
]


def _try_spacy(text: str) -> IntentCategory | None:
    """Use spaCy syntactic parsing for intent classification.

    Returns None if spaCy is not installed or parse fails.
    """
    try:
        nlp = _get_spacy_model()
        if nlp is None:
            return None
        doc = nlp(text[:512])
        # Interrogative: aux-inversion or wh-word as first token
        first_tok = doc[0] if doc else None
        if first_tok and first_tok.tag_ in ("WP", "WRB", "WDT", "WP$"):
            return IntentCategory.QUESTION
        # Sentence-level detection
        for sent in doc.sents:
            root = sent.root
            if root.dep_ == "ROOT":
                # Interrogative aux inversion: aux before subject
                children = list(root.children)
                has_aux = any(c.dep_ in ("aux", "auxpass") for c in children)
                has_nsubj = any(c.dep_ in ("nsubj", "nsubjpass") for c in children)
                if has_aux and not has_nsubj and text.strip().endswith("?"):
                    return IntentCategory.QUESTION
                # Imperative: base-form verb, no subject
                if root.pos_ == "VERB" and root.tag_ == "VB" and not has_nsubj:
                    return IntentCategory.REQUEST
        return None
    except Exception:  # pylint: disable=broad-exception-caught
        return None


_SENTINEL = object()
_SPACY_MODEL: object | None = _SENTINEL


def _get_spacy_model():
    global _SPACY_MODEL  # noqa: PLW0603
    if _SPACY_MODEL is _SENTINEL:
        try:
            import spacy  # noqa: PLC0415

            _SPACY_MODEL = spacy.load("en_core_web_sm")
        except Exception:  # pylint: disable=broad-exception-caught
            _SPACY_MODEL = None
    return _SPACY_MODEL


def _get_spacy_doc(text: str) -> Any:
    """Return a spaCy Doc for *text* (truncated to 1024 chars), or ``None``."""
    nlp = _get_spacy_model()
    if nlp is None:
        return None
    return nlp(text[:1024])


def _heuristic_classify(text: str) -> IntentCategory:
    """Regex/keyword heuristic fallback classifier."""
    stripped = text.strip()
    for pattern in _CORRECTION_PATTERNS:
        if pattern.search(stripped):
            return IntentCategory.CORRECTION
    for pattern in _CONFIRMATION_PATTERNS:
        if pattern.search(stripped):
            return IntentCategory.CONFIRMATION
    for pattern in _CLARIFICATION_PATTERNS:
        if pattern.search(stripped):
            return IntentCategory.CLARIFICATION
    for pattern in _FEEDBACK_PATTERNS:
        if pattern.search(stripped):
            return IntentCategory.FEEDBACK
    for pattern in _QUESTION_PATTERNS:
        if pattern.search(stripped):
            return IntentCategory.QUESTION
    for pattern in _BUG_REPORT_PATTERNS:
        if pattern.search(stripped):
            return IntentCategory.BUG_REPORT
    for pattern in _CODE_REQUEST_PATTERNS:
        if pattern.search(stripped):
            return IntentCategory.CODE_REQUEST
    for pattern in _TASK_PATTERNS:
        if pattern.search(stripped):
            return IntentCategory.TASK
    for pattern in _INSTRUCTION_PATTERNS:
        if pattern.search(stripped):
            return IntentCategory.INSTRUCTION
    for pattern in _REQUEST_PATTERNS:
        if pattern.search(stripped):
            return IntentCategory.REQUEST
    # Long sentences with no signal -> context provision
    if len(stripped.split()) > 15 and not stripped.endswith("?"):
        return IntentCategory.CONTEXT
    return IntentCategory.UNKNOWN


def classify_intent(text: str) -> IntentCategory:
    """Classify the intent of a user or assistant turn.

    :param text: Raw turn text.
    :return: An :class:`~agent_kg.schema.IntentCategory` value.
    """
    if not text or not text.strip():
        return IntentCategory.UNKNOWN
    # Stage 1: spaCy syntactic signals
    spacy_result = _try_spacy(text)
    if spacy_result is not None:
        return spacy_result
    # Stage 2: heuristic fallback
    return _heuristic_classify(text)
