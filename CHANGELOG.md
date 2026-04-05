# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`agent-kg viz` command** — visualize the conversation graph and/or UserProfile
  tree as Rich terminal trees, interactive pyvis HTML, or a full Streamlit browser
  explorer (`agent-kg viz --serve`); supports `--agent`, `--profile`, `--html`,
  `--out`, and `--port` flags
- **`src/agent_kg/app.py` — Streamlit Explorer** — three-tab browser UI (Agent
  Graph, Profile Graph, Stats) backed by pyvis interactive network graphs; loads
  directly from SQLite without any external server
- **`src/agent_kg/viz.py` — visualization helpers** — `build_agent_html()`,
  `build_profile_html()`, `render_agent_tree_rich()`, `render_profile_tree_rich()`,
  and `write_html()` extracted into a dedicated module for reuse by both CLI and app
- **`agent-kg wipe` command** — safely erase the local conversation graph
  (`--local`) and/or the global user profile (`--global`) with a confirmation
  prompt; `--yes` skips the prompt for scripted use
- **`viz` extras group** — `pyvis` (≥0.3.2) and `streamlit` (≥1.35.0) as optional
  dependencies; install with `pip install "agent-kg[viz]"`
- **`kgrag` extras group** — `code-kg` and `doc-kg` moved from required to optional;
  install with `pip install "agent-kg[kgrag]"`
- **`[tool.codekg]` and `[tool.dockg]` config sections** in `pyproject.toml` — sets
  `include = ["src"]` for CodeKG and standard `exclude` patterns for DocKG
- **`analysis/agent_kg_analysis_20260405.md`** — second CodeKG architectural
  analysis with updated metrics (3 973 nodes, 5 044 edges, 90.3% docstring coverage,
  grade B/80)
- **`assessments/AssessmentProtocol_AgentKG.md`** — reproducible assessment
  protocol covering orientation, semantic recall, profile, prune, comparison to
  baseline, and extraction quality analysis phases
- **`assessments/AgentKG_assessment_claude_sonnet_4_6_2026-04-04.md`** — initial
  assessment (3.1/5) identifying the two critical bugs: hook multiline capture and
  LanceDB distance metric
- **`assessments/AgentKG_assessment_claude_sonnet_4_6_2026-04-05.md`** — follow-up
  assessment (4/5) after bug fixes; confirms semantic scores now range 0.50–0.81 for
  relevant queries and < 0.25 for unrelated queries
- **`docs/cheatsheet.md`** — quick-reference card for common CLI workflows
- **New CLI entrypoints** — `agent-kg-wipe` and `agent-kg-viz` registered in
  `[tool.poetry.scripts]`

### Fixed

- **Hook — multiline prompt capture** (`read -r p` captured only the first line of
  multi-line prompts); replaced with `PROMPT=$(jq -r '.prompt')` so the full prompt
  text is always ingested and embedded correctly
- **`store.py` — LanceDB cosine metric** (default L2 metric on normalized vectors
  caused `score = 1 − L2_distance` to clamp near 0 for all but the closest match);
  added `.metric("cosine")` to the vector search call — scores now range 0.50–0.81
  for relevant content vs. < 0.25 for unrelated queries
- **Unit test suite (169 tests, 0 failures)** across 8 modules with no external
  dependency requirements: `test_schema`, `test_nlp`, `test_store`, `test_session`,
  `test_profile`, `test_snapshots`, `test_ingest` (SQLite-only via `embed=False`),
  and `test_consolidate`
- **`mcp/server.py` — MCP startup crash** (`asyncio.run(stdio_server(app))` passed
  an async-generator context manager where a coroutine was expected); replaced with
  a proper `_serve()` async function using `async with stdio_server() as (r, w)`
  and `app.run(r, w, ...)`
- **`query.py` — mypy `var-annotated` error** on the `results` accumulator; added
  explicit `list[dict]` type annotation
- **`ingest.py` — wrong import order** (`import re` appeared after first-party
  imports); moved to the stdlib block at the top of the module

### Changed

- **`--person` default** changed from the literal string `"default"` to
  `getpass.getuser()` (the OS login name) across all CLI commands — eliminates the
  most common misconfiguration on single-user machines
- **Session-end hook** changed from ingesting a `"Session ended."` turn to running
  `agent-kg snapshot --label "session-end"` — avoids polluting the graph with
  synthetic turns and captures a clean point-in-time snapshot instead
- **`spacy`** promoted from optional to a required dependency (was `optional = true`)
- **`code-kg` and `doc-kg`** demoted to optional (`kgrag` extras group) — most users
  do not need the full KG stack for basic conversational memory
- **`all` extras** updated to include `pyvis`, `streamlit`, `code-kg`, and `doc-kg`
- **`nlp/intent.py` — expanded intent taxonomy** with four coding-assistant-specific
  categories: `instruction`, `code_request`, `bug_report`, and `task`; reduced
  `unknown` classification from 44% to 0% in test corpus
- **`store.py` / `index.py` — extracted shared `_make_node_schema()`** helper to
  eliminate the duplicated `pa.schema([...])` block that existed in both modules;
  `index.py` now imports `_make_node_schema` and `_EMBED_DIM` from `store`
- **`nlp/intent.py` — added `_get_spacy_doc(text)` helper** that encapsulates the
  repeated spaCy-model-load + `nlp(text[:1024])` pattern; `entities.py` and
  `topics.py` now call this helper instead of duplicating it
- **`store.py` / `index.py` — suppressed lancedb `table_names()` deprecation
  warning** with a `warnings.catch_warnings()` guard at each call site while the
  lancedb API stabilises
- **`docs/structural_importance.md`** removed — superseded by the CodeKG analysis
  reports in `analysis/`

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
