
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![License: Elastic-2.0](https://img.shields.io/badge/License-Elastic%202.0-blue.svg)](https://www.elastic.co/licensing/elastic-license)
[![Version](https://img.shields.io/badge/version-0.5.1-blue.svg)](https://github.com/Flux-Frontiers/agent_kg/releases)
[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)

**AgentKG** — Conversational Memory as a Live, Queryable Knowledge Graph

*Author: Eric G. Suchanek, PhD*

*Flux-Frontiers, Liberty TWP, OH*

---

## Overview

AgentKG stores every conversation turn, topic, entity, intent, task, and user preference as a node in a **persistent knowledge graph** (SQLite + LanceDB). Edges encode relationships between turns, sessions, and profile facts. The result is a queryable, prunable, semantically searchable memory that survives context resets and accumulates across projects.

The graph is split into two stores:

- **Per-repo conversation graph** (`.agentkg/`) — turns, topics, entities, intents, tasks, summaries
- **Global user profile** (`~/.kgrag/profiles/<person>/`) — preferences, expertise, style, commitments, interests; never pruned

Embeddings use `all-MiniLM-L6-v2` (384-dim) via `sentence-transformers` + LanceDB. Structure is treated as ground truth; semantic search is strictly a retrieval accelerant.

---

## Features

- **Incremental ingest** — every turn indexed in real-time; topics, entities, and intents extracted automatically via spaCy + keyword fallback
- **Hybrid query** — semantic seeding (LanceDB) + structural expansion (graph traversal)
- **Global UserProfile tree** — preference, expertise, style, commitment, interest, and context nodes accumulated across all repos
- **Structured onboarding** — four-phase interview populates the profile on first use
- **Implicit profile updates** — NLP pipeline extracts standing rules from natural language ("always do X", "I prefer Y")
- **Context assembly** — token-budgeted context block built from the graph for LLM prompt injection
- **KG Context Pruning** — old turns compressed into Summary nodes when the graph grows large
- **Temporal snapshots** — point-in-time JSON snapshots for diffing session state
- **MCP server** — exposes the full query pipeline as structured tools for AI agent integration
- **Script-based hooks** — three Claude Code hooks (UserPromptSubmit, Stop, PreCompact) deployed as shell scripts via `install-hooks`

---

## Quick Start

```bash
# 1. Download the embedding model and create your profile directory
agent-kg init --person <you>

# 2. Run the onboarding interview
agent-kg onboard --person <you>

# 3. Check your profile
agent-kg profile --person <you>
```

Embeddings are on by default. `init` pre-warms the model cache so the first `ingest` does not pause to download.

---

## Person ID

`--person` identifies the **global user profile** at `~/.kgrag/profiles/<person>/`.
The default is your OS login name (`getpass.getuser()`), which is correct automatically
on a single-user machine — you rarely need to set it explicitly.

**`--person` only affects profile-scoped commands:** `init`, `onboard`, `profile`,
`viz --profile`, `wipe --global`. Local graph commands (`query`, `assemble`, `stats`,
`sessions`, `snapshot`, `prune`, `ingest`, `analyze`) are repo-scoped and ignore it.

```bash
# Single-user machine: default is correct, no flag needed
agent-kg onboard    # writes to ~/.kgrag/profiles/<your-os-username>/
agent-kg profile    # reads the same path ← correct

# Multi-user or named profiles: be explicit on profile commands only
agent-kg onboard --person alice
agent-kg profile --person alice
agent-kg query "auth strategy"   # no --person needed here
```

If `agent-kg profile` returns an empty `# UserProfile`, check which `--person` value
was used during `onboard`. The completion message prints the exact path.

---

## CLI Reference

All commands accept `--repo <path>` (default `.`). `--person <id>` defaults to your OS
username and is only needed for profile-scoped commands (`init`, `onboard`, `profile`,
`viz --profile`, `wipe --global`).

| Command | Description |
|---|---|
| `agent-kg init` | Download embedding model and create profile directory (run first) |
| `agent-kg install-hooks` | Deploy hook scripts and wire Claude Code settings.json |
| `agent-kg onboard` | Run the structured UserProfile onboarding interview |
| `agent-kg profile` | Show the UserProfile as Markdown |
| `agent-kg ingest` | Add a turn to the conversation graph |
| `agent-kg query` | Semantic search over the graph |
| `agent-kg assemble` | Assemble a token-budgeted context block |
| `agent-kg prune` | Compress old turns into Summary nodes |
| `agent-kg stats` | Show graph node/edge counts |
| `agent-kg analyze` | Print a full Markdown analysis report |
| `agent-kg sessions` | List all sessions for this repo |
| `agent-kg snapshot` | Capture a point-in-time snapshot |
| `agent-kg mcp` | Start the MCP server (stdio transport) |

Each command also ships as a dedicated `agent-kg-<name>` script — no `poetry run` needed:

```bash
agent-kg-init     --person egs          # profile-scoped
agent-kg-onboard  --person egs          # profile-scoped
agent-kg-profile  --person egs          # profile-scoped
agent-kg-stats    --repo .
agent-kg-query    "authentication strategy" --k 8 --repo .
agent-kg-assemble "what did we decide about auth?" --budget 4000 --repo .
agent-kg-prune    --window 20 --repo .
agent-kg-mcp
```

---

## Installation

**Requirements:** Python ≥ 3.12, < 3.14

### Poetry (recommended)

```bash
git clone https://github.com/Flux-Frontiers/agent_kg.git
cd agent_kg
poetry install
```

### As a dependency

```toml
[tool.poetry.dependencies]
agent-kg = {git = "https://github.com/Flux-Frontiers/agent_kg.git"}
```

### Optional extras

```bash
poetry install -E llm    # Anthropic summarizer backend
poetry install -E viz    # Streamlit explorer UI + pyvis graph visualization
poetry install -E local  # httpx for local LLM backends
poetry install -E all    # everything above
```

spaCy is a **required** dependency (not an extra) — it is always installed and drives topic and entity extraction. The `en_core_web_sm` model must be downloaded separately:

```bash
python -m spacy download en_core_web_sm
```

Without the model, extraction falls back to keyword/regex heuristics automatically.

---

## Data Layout

```
<repo-root>/.agentkg/
  graph.sqlite          # nodes + edges (conversation graph)
  lancedb/              # vector embeddings
  snapshots/            # point-in-time JSON snapshots

~/.kgrag/profiles/<person>/
  userprofile.sqlite    # global UserProfile tree (never pruned)
```

---

## Node Kinds

| Kind | What it stores |
|---|---|
| `turn` | Raw user/assistant message text |
| `topic` | N-gram topics extracted from turns |
| `entity` | Named entities (people, tools, projects) |
| `intent` | Classified intent category per turn |
| `task` | Action items extracted from conversation |
| `summary` | Pruned turn summaries (after prune pass) |
| `preference` | User coding/style preferences (profile) |
| `commitment` | Standing rules — "always do X" (profile) |
| `expertise` | Domain knowledge areas (profile) |
| `interest` | Topics the user cares about (profile) |
| `style` | Formatting/docstring/verbosity preferences (profile) |
| `context` | Role, machine, projects context (profile) |
| `education` | Educational background entries (profile) |

---

## MCP Server

AgentKG ships a **Model Context Protocol (MCP) server** that exposes the full query pipeline as structured tools for AI agents.

```bash
agent-kg-mcp   # stdio transport
```

Configure in `.mcp.json` (Claude Code / Kilo Code):

```json
{
  "mcpServers": {
    "agent-kg": {
      "command": "agent-kg-mcp"
    }
  }
}
```

---

## Hooks (Auto-Ingest)

AgentKG ships three Claude Code hook scripts that are deployed by the installer:

| Hook | Script | What it does |
|---|---|---|
| `UserPromptSubmit` | `agent_kg_user_prompt_hook.sh` | Ingests each user turn with embeddings |
| `Stop` | `agent_kg_stop_hook.sh` | Ingests assistant turn; runs `prune` async every 20 exchanges; snapshots |
| `PreCompact` | `agent_kg_precompact_hook.sh` | Runs `prune` + snapshot **synchronously** before context compaction — ensures no turns are lost |

### Install

```bash
# Deploy scripts to ~/.agentkg/hooks/ and wire into ~/.claude/settings.json (all repos)
agent-kg install-hooks --global

# Or wire into .claude/settings.json for this repo only
agent-kg install-hooks --claude

# Force-overwrite existing hooks
agent-kg install-hooks --global --force
```

The installer:
1. Copies the three `.sh` scripts from the package into `~/.agentkg/hooks/` (executable)
2. Merges `UserPromptSubmit`, `Stop`, and `PreCompact` entries into the target `settings.json`

The scripts are portable — they use `git rev-parse --show-toplevel` to locate the repo and only fire when a `.agentkg/` directory is present.

### Hook state and logs

```
~/.agentkg/hook_state/
  hook.log                          # timestamped log of all hook activity
  <session_id>_last_consolidate     # exchange counter for periodic prune
```

---

## Project Structure

```
agent_kg/
├── README.md
├── pyproject.toml
├── hooks/                            # reference copies of hook scripts
│   ├── agent_kg_user_prompt_hook.sh
│   ├── agent_kg_stop_hook.sh
│   └── agent_kg_precompact_hook.sh
├── scripts/
│   └── generate_wiki.py              # GitHub wiki generator
├── src/
│   └── agent_kg/
│       ├── __init__.py
│       ├── graph.py                  # AgentKG orchestrator
│       ├── store.py                  # SQLite + LanceDB storage
│       ├── index.py                  # LanceDB semantic indexing
│       ├── ingest.py                 # Phase 1 incremental turn ingest
│       ├── user_profile.py           # Global UserProfile tree
│       ├── onboard.py                # Structured onboarding interview
│       ├── session.py                # Session lifecycle
│       ├── query.py                  # Hybrid semantic + graph query
│       ├── assemble.py               # Token-budgeted context assembly
│       ├── prune.py                  # KG Context Pruning
│       ├── consolidate.py            # Deferred embedding consolidation
│       ├── summarize.py              # LLM-backed summarization
│       ├── snapshots.py              # Point-in-time snapshot capture
│       ├── schema.py                 # Node/Edge dataclasses
│       ├── kg.py                     # High-level KG facade
│       ├── app.py                    # Streamlit explorer UI
│       ├── viz.py                    # Visualization helpers (Rich + pyvis)
│       ├── hooks/                    # bundled hook scripts (deployed by install-hooks)
│       │   ├── agent_kg_user_prompt_hook.sh
│       │   ├── agent_kg_stop_hook.sh
│       │   └── agent_kg_precompact_hook.sh
│       ├── cli/
│       │   ├── main.py               # Click CLI entry points
│       │   └── __init__.py
│       ├── mcp/
│       │   └── server.py             # MCP server
│       └── nlp/                      # NLP pipeline (spaCy + regex fallback)
│           ├── entities.py
│           ├── intent.py
│           ├── preferences.py
│           └── topics.py
└── tests/
```

---

## License

[Elastic License 2.0](https://www.elastic.co/licensing/elastic-license) — see [LICENSE](LICENSE).

Free to use, modify, and distribute. You may not offer the software as a hosted or managed service to third parties. Commercial use internally is permitted.
