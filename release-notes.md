# Release Notes — v0.7.0

> Released: 2026-07-07

This release gives AgentKG's context-pruning summarizer a real choice of engines. Alongside the default Anthropic backend, it can now drive local MLX (oMLX) and Ollama servers or the OpenAI cloud API through one shared, fleet-wide synthesis layer — so conversation summaries can run fully local and fast on Apple Silicon. It also trims the toolchain down to ruff + ty and cleans up release plumbing.

## What changed

**Pluggable summarization backends.** The pruning summarizer now supports four backends — `primary` (Anthropic, the default), `omlx`, `ollama`, and `openai`. The three new ones share the KGRAG fleet's `kg_utils.synthesis` layer over the OpenAI wire protocol, inheriting common defaults (oMLX uses `Qwen3-4B-Instruct-2507-MLX-8bit` at `localhost:8080`, matching GutenbergKG). Configuration moves to the fleet-wide `SYNTH_*` environment convention (`SYNTH_BACKEND` / `SYNTH_ENDPOINT` / `SYNTH_MODEL` / `SYNTH_API_KEY`). If a backend is unavailable, the summarizer degrades gracefully to a deterministic extractive fallback instead of failing.

**Leaner toolchain.** pylint is gone — ruff (lint + format) and ty (types) now cover everything. The pre-commit `pylint` hook, its extras and config, and every `# pylint: disable=` / dead `# noqa` directive have been removed.

**Release plumbing.** The unused automated PyPI-publish workflow was removed; PyPI releases are cut manually. Tag pushes now trigger only the GitHub Release workflow.

## Upgrading

**Breaking — CLI rename.** The command-line entry points dropped their hyphens: `agent-kg-query` → `agentkg-query`, and so on across the CLI. The PyPI package (`agent-kg`), import name (`agent_kg`), and MCP server id (`agent-kg`) are unchanged. Update any scripts, git hooks, or `.claude/settings.json` permission entries that call the old hyphenated names.

To use a local/cloud summarization backend, install the `local` extra (`pip install -e ".[local]"`, which adds `openai`) and set `SYNTH_BACKEND=omlx` (or `ollama` / `openai`). The default `primary` (Anthropic) backend is unchanged and needs no new setup.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
