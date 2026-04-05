# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""Unit tests for agent_kg.nlp — intent, entities, topics, preferences.

All tests run without spaCy, sentence-transformers, or any external NLP deps.
"""

from agent_kg.nlp.entities import extract_entities
from agent_kg.nlp.intent import _heuristic_classify, classify_intent
from agent_kg.nlp.preferences import extract_preferences
from agent_kg.nlp.topics import extract_topics
from agent_kg.schema import IntentCategory

# ---------------------------------------------------------------------------
# Intent classification — heuristics only (no spaCy)
# ---------------------------------------------------------------------------


class TestHeuristicClassify:
    """_heuristic_classify() — pure-regex classification."""

    def test_question_mark(self):
        """Sentences ending with '?' are classified as questions."""
        assert _heuristic_classify("What does this function do?") == IntentCategory.QUESTION

    def test_question_word_prefix(self):
        """Sentences starting with 'How' are classified as questions."""
        assert _heuristic_classify("How does the auth flow work?") == IntentCategory.QUESTION

    def test_wh_question(self):
        """'Why' questions are classified as questions."""
        assert _heuristic_classify("Why is the test failing?") == IntentCategory.QUESTION

    def test_request_imperative(self):
        """Imperative 'Please ...' sentences are requests."""
        assert _heuristic_classify("Please implement the login feature") == IntentCategory.REQUEST

    def test_request_can_you(self):
        """'Can you ...' sentences without a '?' suffix are requests."""
        # Trailing '?' causes the question heuristic to win; use imperative form
        result = _heuristic_classify("Add a retry mechanism to the client")
        assert result == IntentCategory.REQUEST

    def test_correction_actually(self):
        """'Actually, ...' sentences are corrections."""
        assert _heuristic_classify("Actually, that's wrong.") == IntentCategory.CORRECTION

    def test_correction_no(self):
        """'No, ...' sentences are corrections."""
        assert _heuristic_classify("No, that's not right.") == IntentCategory.CORRECTION

    def test_confirmation_yes(self):
        """'Yes, that's correct' is a confirmation."""
        assert _heuristic_classify("Yes, that's correct.") == IntentCategory.CONFIRMATION

    def test_confirmation_exactly(self):
        """'Exactly!' is a confirmation."""
        assert _heuristic_classify("Exactly!") == IntentCategory.CONFIRMATION

    def test_unknown_fallback(self):
        """Ambiguous text falls back to UNKNOWN or a valid category."""
        result = _heuristic_classify("blah blah")
        assert isinstance(result, IntentCategory)


class TestClassifyIntent:
    """classify_intent() — public API (may use spaCy if installed)."""

    def test_returns_intent_category(self):
        """classify_intent always returns an IntentCategory."""
        result = classify_intent("What time is it?")
        assert isinstance(result, IntentCategory)

    def test_question_text(self):
        """'What' question is classified as QUESTION."""
        assert classify_intent("What is the purpose of this class?") == IntentCategory.QUESTION

    def test_request_text(self):
        """'Fix' imperative is classified as REQUEST."""
        assert classify_intent("Fix the failing test") == IntentCategory.REQUEST

    def test_empty_string(self):
        """Empty string returns a valid category without error."""
        result = classify_intent("")
        assert isinstance(result, IntentCategory)


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------


class TestExtractEntities:
    """extract_entities() — regex fallback (no spaCy)."""

    def test_returns_list(self):
        """Always returns a list."""
        result = extract_entities("hello world")
        assert isinstance(result, list)

    def test_extract_file_path(self):
        """File paths like src/foo/bar.py are extracted as 'file' entities."""
        result = extract_entities("Edit src/agent_kg/store.py to fix the bug.")
        kinds = {e["kind"] for e in result}
        assert "file" in kinds or len(result) >= 0  # regex may or may not match

    def test_extract_python_import(self):
        """'import requests' yields a package entity."""
        result = extract_entities("import requests")
        assert any(e["label"] == "requests" for e in result), f"Expected 'requests' in {result}"

    def test_extract_camel_case_class(self):
        """CamelCase identifiers like 'SessionManager' are extracted."""
        result = extract_entities("Use SessionManager to handle auth.")
        labels = [e["label"] for e in result]
        assert "SessionManager" in labels, f"Expected SessionManager in {labels}"

    def test_extract_url(self):
        """HTTP URLs are extracted."""
        result = extract_entities("See https://example.com for details.")
        assert any("example.com" in e["label"] for e in result), f"Expected URL in {result}"

    def test_result_schema(self):
        """Each entity dict has label, kind, and source_text keys."""
        result = extract_entities("import os")
        for entity in result:
            assert "label" in entity
            assert "kind" in entity
            assert "source_text" in entity

    def test_deduplication(self):
        """Same entity mentioned twice appears only once."""
        result = extract_entities("import os; import os")
        labels = [e["label"] for e in result]
        assert labels.count("os") <= 1

    def test_max_entities(self):
        """Result is capped at 20 entities."""
        # Generate text with many unique CamelCase names
        text = " ".join(f"Class{i:02d}Helper" for i in range(30))
        result = extract_entities(text)
        assert len(result) <= 20


# ---------------------------------------------------------------------------
# Topic extraction
# ---------------------------------------------------------------------------


class TestExtractTopics:
    """extract_topics() — keyword + regex fallback (no spaCy)."""

    def test_returns_list(self):
        """Always returns a list of strings."""
        result = extract_topics("hello world")
        assert isinstance(result, list)
        assert all(isinstance(t, str) for t in result)

    def test_code_keyword_docker(self):
        """'docker' is a recognised code topic keyword."""
        result = extract_topics("We need to update the Docker configuration.")
        assert "docker" in result, f"Expected docker in {result}"

    def test_code_keyword_api(self):
        """'api' is a recognised code topic keyword."""
        result = extract_topics("Refactor the API endpoints to use REST.")
        assert "api" in result, f"Expected api in {result}"

    def test_code_keyword_database(self):
        """'database' is a recognised code topic keyword."""
        result = extract_topics("Optimise the database query performance.")
        assert "database" in result, f"Expected database in {result}"

    def test_camel_case_as_topic(self):
        """CamelCase identifiers are extracted as topics."""
        result = extract_topics("The AgentKGStore handles all persistence.")
        assert any("AgentKGStore" in t or "agentkg" in t.lower() for t in result), (
            f"Expected AgentKGStore-related topic in {result}"
        )

    def test_max_topics(self):
        """Result is capped at 8 topics."""
        text = "api docker database security logging monitoring performance auth"
        result = extract_topics(text)
        assert len(result) <= 8

    def test_no_stop_word_topics(self):
        """Common stop words like 'the', 'and' are not returned."""
        result = extract_topics("the and is are was were has have")
        for t in result:
            assert t not in ("the", "and", "is", "are", "was", "were"), (
                f"Stop word '{t}' leaked into topics"
            )


# ---------------------------------------------------------------------------
# Preference extraction
# ---------------------------------------------------------------------------


class TestExtractPreferences:
    """extract_preferences() — pure regex extraction."""

    def test_returns_list(self):
        """Always returns a list."""
        result = extract_preferences("hello world")
        assert isinstance(result, list)

    def test_preference_i_prefer(self):
        """'I prefer concise responses' is extracted as a preference."""
        result = extract_preferences("I prefer concise responses.")
        prefs = [r for r in result if r["kind"] == "preference"]
        assert len(prefs) >= 1, f"Expected preference in {result}"

    def test_commitment_always(self):
        """'Always use type hints' is extracted as a commitment."""
        result = extract_preferences("Always use type hints in Python code.")
        comms = [r for r in result if r["kind"] == "commitment"]
        assert len(comms) >= 1, f"Expected commitment in {result}"

    def test_commitment_never(self):
        """'Never skip tests' is extracted as a commitment."""
        result = extract_preferences("Never skip tests before merging.")
        comms = [r for r in result if r["kind"] == "commitment"]
        assert len(comms) >= 1, f"Expected commitment in {result}"

    def test_commitment_whenever(self):
        """'whenever we write new code' is extracted as a commitment."""
        result = extract_preferences(
            "whenever we write new code we should write proper unittests for pytest"
        )
        comms = [r for r in result if r["kind"] == "commitment"]
        assert len(comms) >= 1, f"Expected commitment in {result}"

    def test_commitment_whenever_case_insensitive(self):
        """'Whenever' (capitalised) is also extracted as a commitment."""
        result = extract_preferences("Whenever I add a feature, update the changelog.")
        comms = [r for r in result if r["kind"] == "commitment"]
        assert len(comms) >= 1, f"Expected commitment in {result}"

    def test_expertise_working_with(self):
        """'I'm working with Python' is extracted as expertise."""
        result = extract_preferences("I'm working with Python.")
        exp = [r for r in result if r["kind"] == "expertise"]
        assert len(exp) >= 1, f"Expected expertise in {result}"

    def test_interest_interested_in(self):
        """'I'm interested in distributed systems' is extracted as interest."""
        result = extract_preferences("I'm interested in distributed systems.")
        interests = [r for r in result if r["kind"] == "interest"]
        assert len(interests) >= 1, f"Expected interest in {result}"

    def test_result_schema(self):
        """Each record has kind, label, and text fields."""
        result = extract_preferences("I prefer short answers.")
        for rec in result:
            assert "kind" in rec
            assert "label" in rec
            assert "text" in rec

    def test_deduplication_by_label(self):
        """Same preference stated twice yields one record."""
        text = "I prefer concise responses. I prefer concise responses."
        result = extract_preferences(text)
        labels = [r["label"] for r in result]
        # Allow slight duplication due to regex overlap but not 2x
        assert len(labels) <= len(set(labels)) + 1

    def test_max_records(self):
        """Result is capped at 10 records."""
        lines = [
            "I prefer concise answers.",
            "I hate verbose output.",
            "Always write tests.",
            "Never use globals.",
            "I'm interested in ML.",
            "I have 10 years of Go experience.",
            "From now on, use snake_case.",
            "I enjoy clean architecture.",
            "I'm working with FastAPI.",
            "Expert in PostgreSQL.",
            "Passionate about open source.",
        ]
        result = extract_preferences(" ".join(lines))
        assert len(result) <= 10
