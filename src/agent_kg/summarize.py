# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""summarize.py — Configurable LLM summarization backend for KG Context Pruning.

Supports four backends:
  ``primary``  — Anthropic Claude via the ``anthropic`` SDK (default; maximum
                 coherence with the session model).
  ``omlx``     — local oMLX / MLX server (OpenAI wire protocol; recommended
                 local backend, fastest on Apple Silicon).
  ``ollama``   — local Ollama (OpenAI wire protocol).
  ``openai``   — OpenAI cloud API.

The ``omlx`` / ``ollama`` / ``openai`` backends are delegated to the shared
``kg_utils.synthesis.TextSynthesizer`` (from ``kgmodule-utils[synthesis]``), so
they share the fleet-wide defaults — including the ``Qwen3-4B-Instruct-2507-MLX-8bit``
model at ``http://localhost:8080/v1`` for oMLX.

Configuration via ``agentkg.toml`` or environment variables (SYNTH_* convention,
shared across the KGRAG fleet):
  SYNTH_BACKEND                = "primary" | "omlx" | "ollama" | "openai"
  SYNTH_ENDPOINT               = base URL override (empty = backend default)
  SYNTH_MODEL                  = model-id override (empty = backend default)
  SYNTH_API_KEY                = bearer token / OpenAI key (openai backend)
  AGENTKG_SUMMARIZER_PRIMARY_MODEL = Claude model id for the ``primary`` backend
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Literal


@dataclass
class SummarizerConfig:
    """Configuration for the summarization backend.

    :param backend: ``"primary"`` (Anthropic), ``"omlx"``, ``"ollama"``, or ``"openai"``.
    :param primary_model: Claude model ID for the ``primary`` backend.
    :param synth_endpoint: Base URL override for the synth backends (empty = the
                           per-backend default resolved by ``kg_utils``).
    :param synth_model: Model-id override for the synth backends (empty = default).
    :param synth_api_key: Bearer token / OpenAI key for the ``openai`` backend.
    :param temperature: Sampling temperature (lower = more deterministic).
    :param max_tokens: Maximum tokens in the summary.
    """

    backend: Literal["primary", "omlx", "ollama", "openai"] = "primary"
    primary_model: str = "claude-haiku-4-5-20251001"
    synth_endpoint: str = ""
    synth_model: str = ""
    synth_api_key: str = ""
    temperature: float = 0.2
    max_tokens: int = 512

    @classmethod
    def from_env(cls) -> SummarizerConfig:
        """Load configuration from environment variables (SYNTH_* convention)."""
        return cls(
            backend=os.environ.get("SYNTH_BACKEND", "primary"),  # ty: ignore[invalid-argument-type]
            primary_model=os.environ.get(
                "AGENTKG_SUMMARIZER_PRIMARY_MODEL", "claude-haiku-4-5-20251001"
            ),
            synth_endpoint=os.environ.get("SYNTH_ENDPOINT", ""),
            synth_model=os.environ.get("SYNTH_MODEL", ""),
            synth_api_key=os.environ.get("SYNTH_API_KEY", "")
            or os.environ.get("OPENAI_API_KEY", ""),
        )


_SUMMARY_PROMPT = """\
Summarize the following conversation segment into 2-5 sentences.
Preserve all decisions made, open questions, and key facts.
Do not add new information. Write in third-person past tense.

CONVERSATION:
{text}

SUMMARY:"""


class Summarizer:
    """LLM-backed text summarizer with Anthropic + oMLX/Ollama/OpenAI support.

    :param config: Summarization backend configuration.
    """

    def __init__(self, config: SummarizerConfig | None = None) -> None:
        self._config = config or SummarizerConfig.from_env()

    def summarize(self, text: str) -> str:
        """Summarize ``text`` using the configured backend.

        Falls back to a simple extractive summary if the configured backend
        fails (missing dependency, unreachable endpoint, or empty output).

        :param text: Conversation text to summarize.
        :return: Summary string.
        """
        if not text or not text.strip():
            return ""
        prompt = _SUMMARY_PROMPT.format(text=text[:4000])
        if self._config.backend == "primary":
            result = self._call_primary(prompt)
        else:
            result = self._call_synth(prompt)
        if result:
            return result
        # Extractive fallback: first + last sentence(s)
        return self._extractive_fallback(text)

    def _call_primary(self, prompt: str) -> str | None:
        """Call the Anthropic API via the anthropic SDK."""
        try:
            import anthropic

            client = anthropic.Anthropic()
            msg = client.messages.create(
                model=self._config.primary_model,
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            block = msg.content[0] if msg.content else None
            return block.text.strip() if isinstance(block, anthropic.types.TextBlock) else None
        except Exception:
            return None

    def _call_synth(self, prompt: str) -> str | None:
        """Summarize via a shared ``kg_utils`` synth backend (omlx/ollama/openai).

        Builds a :class:`~kg_utils.synthesis.TextConfig` directly so empty
        endpoint/model fields inherit the fleet-wide per-backend defaults
        (e.g. ``Qwen3-4B-Instruct-2507-MLX-8bit`` at ``:8080/v1`` for oMLX).
        """
        try:
            from kg_utils.synthesis import (
                TextBackend,
                TextConfig,
                TextSynthesizer,
            )

            cfg = TextConfig(
                backend=TextBackend(self._config.backend),
                endpoint=self._config.synth_endpoint,
                model=self._config.synth_model,
                api_key=self._config.synth_api_key,
                max_tokens=self._config.max_tokens,
            )
            result = TextSynthesizer(cfg).complete(
                [{"role": "user", "content": prompt}],
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature,
            )
            return result or None
        except Exception:
            return None

    @staticmethod
    def _extractive_fallback(text: str) -> str:
        """Return the first and last sentence of ``text`` as a stub summary."""
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        if not sentences:
            return text[:200]
        if len(sentences) == 1:
            return sentences[0]
        return f"{sentences[0]} ... {sentences[-1]}"
