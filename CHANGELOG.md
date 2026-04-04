# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Unit test suite (169 tests, 0 failures)** across 8 modules with no external
  dependency requirements: `test_schema`, `test_nlp`, `test_store`, `test_session`,
  `test_profile`, `test_snapshots`, `test_ingest` (SQLite-only via `embed=False`),
  and `test_consolidate`

### Fixed

- **`mcp/server.py` — MCP startup crash** (`asyncio.run(stdio_server(app))` passed
  an async-generator context manager where a coroutine was expected); replaced with
  a proper `_serve()` async function using `async with stdio_server() as (r, w)`
  and `app.run(r, w, ...)`
- **`query.py` — mypy `var-annotated` error** on the `results` accumulator; added
  explicit `list[dict]` type annotation
- **`ingest.py` — wrong import order** (`import re` appeared after first-party
  imports); moved to the stdlib block at the top of the module

### Changed

- **`store.py` / `index.py` — extracted shared `_make_node_schema()`** helper to
  eliminate the duplicated `pa.schema([...])` block that existed in both modules;
  `index.py` now imports `_make_node_schema` and `_EMBED_DIM` from `store`
- **`nlp/intent.py` — added `_get_spacy_doc(text)` helper** that encapsulates the
  repeated spaCy-model-load + `nlp(text[:1024])` pattern; `entities.py` and
  `topics.py` now call this helper instead of duplicating it
- **`store.py` / `index.py` — suppressed lancedb `table_names()` deprecation
  warning** with a `warnings.catch_warnings()` guard at each call site while the
  lancedb API stabilises

## [0.2.0] - 2026-04-04

### Added

- **`agent-kg init` command** — pre-downloads the embedding model and creates the
  global profile directory (`~/.kgrag/profiles/<person>/`) so the first `ingest`
  does not pause to fetch model weights
- **`agent-kg install-hooks` command** — writes a git `pre-commit` hook that
  rebuilds CodeKG + DocKG indices, captures metrics snapshots, and then runs the
  pre-commit framework checks; supports `--force` to overwrite and
  `AGENTKG_SKIP_SNAPSHOT=1` escape hatch
- **`analysis/agent_kg_analysis_20260404.md`** — full CodeKG architectural
  analysis report (baseline metrics, fan-in/fan-out, SIR ranking, docstring
  coverage, call chains, orphan detection)
- **`.claude/skills/agent-kg/SKILL.md`** — AgentKG Claude skill definition
  covering data layout, CLI reference, hooks configuration, common issues, and
  health-check recipes
- **`handoff.md`** — investigation notes for the UserProfile empty-on-first-run
  bug (wrong `--person` value, broken hook path)

### Changed

- **Version bump 0.1.0 → 0.2.0** (`pyproject.toml`, `src/agent_kg/__init__.py`,
  `poetry.lock`)
- **`--person` help text** expanded across all CLI commands to show the exact
  profile path (`~/.kgrag/profiles/<person>/`) and warn that the same value must
  be used consistently — surfaces the most common misconfiguration at the CLI
  level
- **`onboard` completion message** now prints the resolved profile path and
  repeats the `--person` consistency reminder so users know exactly where their
  data was written
- **README.md** rewritten from a two-line stub to a full project README:
  badges, feature list, quick-start, person-ID section, CLI reference table,
  installation guide, data layout, node-kind table, MCP server docs, hooks
  configuration, project structure, and license
- **`.pre-commit-config.yaml`** exclude patterns broadened to cover `.agentkg/`
  and `.dockg/` alongside the existing `.codekg/` exclusion (large-files check
  and detect-secrets baseline)

### Added (all source files)

- **Copyright headers** — `# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.`
  and `# SPDX-License-Identifier: Elastic-2.0` prepended to every `.py` file;
  attribution footers added to `handoff.md` and the analysis report; `author`
  and `license` fields added to `SKILL.md` frontmatter

## [0.1.0] - 2026-04-04

### Added

- Initial release: conversational memory as a persistent, queryable knowledge graph
- `AgentKG` / `AgentKGStore` — SQLite + LanceDB storage for turns, topics,
  entities, intents, tasks, and summaries
- `UserProfileStore` — globally persistent preference, expertise, style,
  commitment, interest, and context nodes stored at `~/.kgrag/profiles/<person>/`
- Structured onboarding interview (`agent-kg onboard`)
- Hybrid semantic + structural query and context assembly (`agent-kg query`,
  `agent-kg assemble`)
- KG Context Pruning: LLM compression of old turns into Summary nodes
  (`agent-kg prune`)
- Point-in-time temporal snapshots (`agent-kg snapshot`)
- MCP server exposing the full pipeline as structured tools (`agent-kg mcp`)
- Optional NLP pipeline: spaCy-backed topic, entity, and preference extraction
- Optional LLM summarizer backend via Anthropic API

[Unreleased]: https://github.com/Flux-Frontiers/agent_kg/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Flux-Frontiers/agent_kg/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Flux-Frontiers/agent_kg/releases/tag/v0.1.0
