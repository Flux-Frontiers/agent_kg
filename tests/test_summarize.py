# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""Unit tests for agent_kg.summarize — Summarizer backend dispatch and fallback."""

from __future__ import annotations

from unittest.mock import patch

from agent_kg.summarize import Summarizer, SummarizerConfig

# ---------------------------------------------------------------------------
# SummarizerConfig.from_env
# ---------------------------------------------------------------------------


def test_from_env_defaults(monkeypatch) -> None:
    for var in ("SYNTH_BACKEND", "SYNTH_ENDPOINT", "SYNTH_MODEL", "SYNTH_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    cfg = SummarizerConfig.from_env()
    assert cfg.backend == "primary"
    assert cfg.primary_model == "claude-haiku-4-5-20251001"
    assert cfg.synth_endpoint == ""
    assert cfg.synth_model == ""


def test_from_env_reads_synth_convention(monkeypatch) -> None:
    monkeypatch.setenv("SYNTH_BACKEND", "omlx")
    monkeypatch.setenv("SYNTH_ENDPOINT", "http://box:9000/v1")
    monkeypatch.setenv("SYNTH_MODEL", "my-model")
    monkeypatch.setenv("SYNTH_API_KEY", "sk-abc")  # pragma: allowlist secret
    cfg = SummarizerConfig.from_env()
    assert cfg.backend == "omlx"
    assert cfg.synth_endpoint == "http://box:9000/v1"
    assert cfg.synth_model == "my-model"
    assert cfg.synth_api_key == "sk-abc"  # pragma: allowlist secret


def test_from_env_api_key_falls_back_to_openai_env(monkeypatch) -> None:
    monkeypatch.delenv("SYNTH_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")  # pragma: allowlist secret
    cfg = SummarizerConfig.from_env()
    assert cfg.synth_api_key == "sk-openai"  # pragma: allowlist secret


# ---------------------------------------------------------------------------
# Extractive fallback
# ---------------------------------------------------------------------------


def test_empty_text_returns_empty() -> None:
    assert Summarizer(SummarizerConfig(backend="primary")).summarize("") == ""
    assert Summarizer(SummarizerConfig(backend="primary")).summarize("   ") == ""


def test_extractive_fallback_first_and_last() -> None:
    out = Summarizer._extractive_fallback("First one. Middle bit. Last one.")
    assert out == "First one. ... Last one."


def test_extractive_fallback_single_sentence() -> None:
    assert Summarizer._extractive_fallback("Only one sentence here") == "Only one sentence here"


# ---------------------------------------------------------------------------
# synth backends (omlx / ollama / openai) — delegated to kg_utils
# ---------------------------------------------------------------------------


def test_synth_backend_returns_completion() -> None:
    with patch("kg_utils.synthesis.TextSynthesizer.complete", return_value="A tidy summary."):
        result = Summarizer(SummarizerConfig(backend="omlx")).summarize("We agreed on the plan.")
    assert result == "A tidy summary."


def test_synth_backend_builds_config_from_summarizer_config() -> None:
    captured = {}

    def _fake_complete(self, messages, *, model=None, max_tokens=None, temperature=0.7):
        captured["endpoint"] = self._cfg.endpoint
        captured["model"] = self._cfg.model
        captured["backend"] = self._cfg.backend.value
        captured["max_tokens"] = max_tokens
        captured["temperature"] = temperature
        return "ok"

    cfg = SummarizerConfig(
        backend="omlx",
        synth_endpoint="http://host:8080/v1",
        synth_model="custom-mlx",
        max_tokens=256,
        temperature=0.1,
    )
    with patch("kg_utils.synthesis.TextSynthesizer.complete", _fake_complete):
        Summarizer(cfg).summarize("Some conversation text.")
    assert captured["backend"] == "omlx"
    assert captured["endpoint"] == "http://host:8080/v1"
    assert captured["model"] == "custom-mlx"
    assert captured["max_tokens"] == 256
    assert captured["temperature"] == 0.1


def test_synth_backend_none_falls_back_to_extractive() -> None:
    with patch("kg_utils.synthesis.TextSynthesizer.complete", return_value=None):
        result = Summarizer(SummarizerConfig(backend="omlx")).summarize(
            "First fact. Second fact. Third fact."
        )
    assert result == "First fact. ... Third fact."


def test_synth_backend_exception_falls_back_to_extractive() -> None:
    with patch(
        "kg_utils.synthesis.TextSynthesizer.complete",
        side_effect=RuntimeError("connection refused"),
    ):
        result = Summarizer(SummarizerConfig(backend="omlx")).summarize(
            "Alpha happened. Beta happened."
        )
    assert result == "Alpha happened. ... Beta happened."


def test_omlx_default_model_and_endpoint_inherited() -> None:
    """With no overrides, oMLX inherits the fleet-wide kg_utils defaults."""
    captured = {}

    def _fake_complete(self, messages, *, model=None, max_tokens=None, temperature=0.7):
        captured["endpoint"] = self._cfg.resolved_endpoint()
        captured["model"] = self._cfg.resolved_model()
        return "ok"

    with patch("kg_utils.synthesis.TextSynthesizer.complete", _fake_complete):
        Summarizer(SummarizerConfig(backend="omlx")).summarize("text here")
    assert captured["endpoint"] == "http://localhost:8080/v1"
    assert captured["model"] == "Qwen3-4B-Instruct-2507-MLX-8bit"


# ---------------------------------------------------------------------------
# primary backend (Anthropic) — failure path
# ---------------------------------------------------------------------------


def test_primary_backend_none_falls_back_to_extractive() -> None:
    # Patch the backend call itself so this does not require the optional
    # ``anthropic`` package to be installed (it is not in the CI test extras).
    with patch.object(Summarizer, "_call_primary", return_value=None):
        result = Summarizer(SummarizerConfig(backend="primary")).summarize(
            "Decision made. Question raised."
        )
    assert result == "Decision made. ... Question raised."
