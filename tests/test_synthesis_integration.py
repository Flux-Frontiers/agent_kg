# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""Integration tests for the synthesis summarization backends — real round-trips.

Unlike ``test_summarize.py`` (which mocks the LLM boundary), these exercise the
full path: ``Summarizer`` → ``kg_utils.synthesis.TextSynthesizer`` → ``openai``
client → a live OpenAI-wire inference server.

Every test is parametrized across all three synth backends (``omlx``, ``ollama``,
``openai``) and marked ``integration`` so CI skips them (``pytest -m "not
integration"``). Each parametrization skips gracefully when its backend is not
reachable (no local server, or no API key for ``openai``), so a plain local
``pytest`` run is always safe.

Run locally against whatever servers you have up::

    pytest -m integration tests/test_synthesis_integration.py -v
    # override a backend's endpoint/model:
    OMLX_ENDPOINT=http://localhost:8080/v1 \
    OLLAMA_ENDPOINT=http://localhost:11434/v1 \
    OPENAI_API_KEY=sk-... \
        pytest -m integration tests/test_synthesis_integration.py -v
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("openai", reason="openai not installed — skipping synthesis integration tests")

from kg_utils.synthesis import TextBackend, TextConfig, TextSynthesizer

from agent_kg.summarize import Summarizer, SummarizerConfig

# Per-backend local defaults; the model falls back to the server's first
# advertised model when the preferred one is not installed.
_LOCAL_ENDPOINT = {
    "omlx": "http://localhost:8080/v1",
    "ollama": "http://localhost:11434/v1",
}
_PREFERRED_MODEL = {
    "omlx": "Qwen3-4B-Instruct-2507-MLX-8bit",
    "ollama": "hf.co/unsloth/Qwen3-4B-Instruct-2507-GGUF:Q8_0",
}

# A short conversation with concrete, checkable facts and an explicit open question.
_CONVERSATION = (
    "User: Let's use Postgres for the metadata store and Redis for the cache. "
    "Assistant: Agreed — I'll set up the Postgres schema first. "
    "User: One open question — do we shard by tenant or by region? "
    "Assistant: Let's decide that after we benchmark the single-node setup."
)


def _list_models(cfg: SummarizerConfig) -> list[str]:
    """Return the models the backend in ``cfg`` advertises (empty on failure)."""
    tc = TextConfig(
        backend=TextBackend(cfg.backend),
        endpoint=cfg.synth_endpoint,
        model=cfg.synth_model,
        api_key=cfg.synth_api_key,
    )
    try:
        return TextSynthesizer(tc).list_models()
    except Exception:  # noqa: BLE001
        return []


@pytest.fixture(params=["omlx", "ollama", "openai"])
def summarizer_cfg(request: pytest.FixtureRequest) -> SummarizerConfig:
    """Resolve a reachable ``SummarizerConfig`` for the parametrized backend, or skip.

    Honors ``SYNTH_*`` plus per-backend ``OMLX_ENDPOINT`` / ``OLLAMA_ENDPOINT``
    overrides; ``openai`` requires ``SYNTH_API_KEY`` / ``OPENAI_API_KEY``.
    """
    backend = request.param

    if backend == "openai":
        api_key = os.environ.get("SYNTH_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
        if not api_key:
            pytest.skip("openai backend needs SYNTH_API_KEY / OPENAI_API_KEY")
        cfg = SummarizerConfig(
            backend="openai",
            synth_endpoint=os.environ.get("SYNTH_ENDPOINT", ""),
            synth_model=os.environ.get("SYNTH_MODEL", ""),
            synth_api_key=api_key,
        )
        if not _list_models(cfg):
            pytest.skip("openai endpoint unreachable or key rejected")
        return cfg

    endpoint = os.environ.get(f"{backend.upper()}_ENDPOINT") or _LOCAL_ENDPOINT[backend]
    models = _list_models(SummarizerConfig(backend=backend, synth_endpoint=endpoint))
    if not models:
        pytest.skip(f"no {backend} server reachable at {endpoint}")
    preferred = os.environ.get("SYNTH_MODEL") or _PREFERRED_MODEL[backend]
    model = preferred if preferred in models else models[0]
    return SummarizerConfig(backend=backend, synth_endpoint=endpoint, synth_model=model)


@pytest.mark.integration
def test_list_models_returns_ids(summarizer_cfg: SummarizerConfig) -> None:
    models = _list_models(summarizer_cfg)
    assert models
    assert all(isinstance(m, str) and m for m in models)


@pytest.mark.integration
def test_summarize_real_roundtrip(summarizer_cfg: SummarizerConfig) -> None:
    summary = Summarizer(summarizer_cfg).summarize(_CONVERSATION)

    # Non-empty, and NOT the deterministic extractive fallback → the LLM ran.
    assert summary.strip()
    assert summary != Summarizer._extractive_fallback(_CONVERSATION)
    # A real summary is a synthesis, not a verbatim echo of the transcript.
    assert summary.strip() != _CONVERSATION.strip()
    assert "User:" not in summary and "Assistant:" not in summary


@pytest.mark.integration
def test_summary_preserves_a_salient_fact(summarizer_cfg: SummarizerConfig) -> None:
    summary = Summarizer(summarizer_cfg).summarize(_CONVERSATION).lower()
    # The prompt asks to preserve key facts; at least one named term should survive.
    assert any(term in summary for term in ("postgres", "redis", "shard", "benchmark", "cache"))


@pytest.mark.integration
def test_thinking_blocks_stripped(summarizer_cfg: SummarizerConfig) -> None:
    summary = Summarizer(summarizer_cfg).summarize(_CONVERSATION)
    # kg_utils strips <think>…</think> from every backend's output.
    assert "<think>" not in summary
    assert "</think>" not in summary
