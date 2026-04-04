
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![License: Elastic-2.0](https://img.shields.io/badge/License-Elastic%202.0-blue.svg)](https://www.elastic.co/licensing/elastic-license)
[![Version](https://img.shields.io/badge/version-0.2.0-blue.svg)](https://github.com/Flux-Frontiers/agent_kg/releases)
[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)

**AgentKG** — Conversational Memory as a Live, Queryable Knowledge Graph

*Author: Eric G. Suchanek, PhD*

*Flux-Frontiers, Liberty TWP, OH*

---

## Overview

AgentKG stores every conversation turn, topic, entity, intent, task, and user preference as a node in a **persistent knowledge graph** (SQLite + LanceDB). Edges encode relationships between turns, sessions, and profile facts. The result is a queryable, pruneable, semantically searchable memory that survives context resets and accumulates across projects.

The graph is split into two stores:

- **Per-repo conversation graph** (`.agentkg/`) — turns, topics, entities, intents, tasks, summaries
- **Global user profile** (`~/.kgrag/profiles/<person>/`) — preferences, expertise, style, commitments, interests; never pruned

Embeddings use `all-MiniLM-L6-v2` (384-dim) via `sentence-transformers` + LanceDB. Structure is treated as ground truth; semantic search is strictly a retrieval accelerant.

---

## Features

- **Incremental ingest** — every turn indexed in real-time; topics, entities, and intents extracted automatically
- **Hybrid query** — semantic seeding (LanceDB) + structural expansion (graph traversal)
- **Global UserProfile tree** — preference, expertise, style, commitment, interest, and context nodes accumulated across all repos
- **Structured onboarding** — four-phase interview populates the profile on first use
- **Implicit profile updates** — NLP pipeline extracts standing rules from natural language ("always do X", "I prefer Y")
- **Context assembly** — token-budgeted context block built from the graph for LLM prompt injection
- **KG Context Pruning** — old turns compressed into Summary nodes when the graph grows large
- **Temporal snapshots** — point-in-time JSON snapshots for diffing session state
- **MCP server** — exposes the full query pipeline as structured tools for AI agent integration

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

Every command accepts a `--person` flag that identifies whose profile to read/write.
The default is `"default"`. Profiles are stored globally at:

```
~/.kgrag/profiles/<person>/userprofile.sqlite
```

**You must use the same `--person` value across all commands or your profile will not be found.**

```bash
# These two commands refer to different profiles:
agent-kg onboard --person egs   # writes to ~/.kgrag/profiles/egs/
agent-kg profile                 # reads from ~/.kgrag/profiles/default/  ← wrong!

# Correct usage:
agent-kg onboard --person egs
agent-kg profile --person egs
```

If `agent-kg profile` returns an empty `# UserProfile`, check which `--person` value
was used during `onboard`. The completion message prints the exact path.

---

## CLI Reference

All commands accept `--repo <path>` (default `.`) and `--person <id>` (default `"default"`).

| Command | Description |
|---|---|
| `agent-kg init` | Download embedding model and create profile directory (run first) |
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
agent-kg-init     --person egs
agent-kg-onboard  --person egs
agent-kg-profile  --person egs
agent-kg-stats    --repo . --person egs
agent-kg-query    "authentication strategy" --k 8 --repo . --person egs
agent-kg-assemble "what did we decide about auth?" --budget 4000 --repo . --person egs
agent-kg-prune    --window 20 --repo . --person egs
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
poetry install -E nlp    # spaCy NLP pipeline (richer topic/entity extraction)
poetry install -E llm    # Anthropic summarizer backend
poetry install -E all    # everything
```

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

Add these hooks to `.claude/settings.json` to ingest every prompt automatically:

```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "hooks": [{
        "type": "command",
        "command": "jq -r '.prompt' | { read -r p; REPO_ROOT=\"$(git rev-parse --show-toplevel)\"; agent-kg-ingest \"$p\" --role user --repo \"$REPO_ROOT\" --person egs --no-embed; } 2>/dev/null || true",
        "async": true
      }]
    }],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "REPO_ROOT=\"$(git rev-parse --show-toplevel)\"; agent-kg-ingest \"Session ended.\" --role assistant --repo \"$REPO_ROOT\" --person egs --no-embed 2>/dev/null || true",
        "async": true
      }]
    }]
  }
}
```

`--no-embed` defers embedding to a later consolidate pass — keeps hooks fast.

---

## Project Structure

```
agent_kg/
├── README.md
├── pyproject.toml
├── src/
│   └── agent_kg/
│       ├── __init__.py
│       ├── graph.py          # AgentKG orchestrator
│       ├── store.py          # SQLite + LanceDB storage
│       ├── index.py          # LanceDB semantic indexing
│       ├── ingest.py         # Phase 1 incremental turn ingest
│       ├── profile.py        # Global UserProfile tree
│       ├── onboard.py        # Structured onboarding interview
│       ├── session.py        # Session lifecycle
│       ├── query.py          # Hybrid semantic + graph query
│       ├── assemble.py       # Token-budgeted context assembly
│       ├── prune.py          # KG Context Pruning
│       ├── consolidate.py    # Deferred embedding consolidation
│       ├── summarize.py      # LLM-backed summarization
│       ├── snapshots.py      # Point-in-time snapshot capture
│       ├── schema.py         # Node/Edge dataclasses
│       ├── kg.py             # High-level KG facade
│       ├── cli/
│       │   ├── main.py       # Click CLI entry points
│       │   └── __init__.py
│       ├── mcp/
│       │   └── server.py     # MCP server
│       └── nlp/              # NLP pipeline (optional)
└── tests/
```

---

## License

[Elastic License 2.0](https://www.elastic.co/licensing/elastic-license) — see [LICENSE](LICENSE).

Free to use, modify, and distribute. You may not offer the software as a hosted or managed service to third parties. Commercial use internally is permitted.
