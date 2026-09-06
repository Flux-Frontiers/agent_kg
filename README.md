
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![License: Elastic-2.0](https://img.shields.io/badge/License-Elastic%202.0-blue.svg)](https://www.elastic.co/licensing/elastic-license)
[![Version](https://img.shields.io/badge/version-0.9.0-blue.svg)](https://github.com/Flux-Frontiers/agent_kg/releases)
[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)
[![DOI](https://zenodo.org/badge/1186774406.svg)](https://zenodo.org/badge/latestdoi/1186774406)

**AgentKG** — Conversational Memory as a Live, Queryable Knowledge Graph

*Author: Eric G. Suchanek, PhD*

*Flux-Frontiers, Liberty TWP, OH*

---

## Overview

AgentKG stores every conversation turn, topic, entity, intent, task, and user preference as a node in a **persistent knowledge graph** (SQLite + sqlite-vec). Edges encode relationships between turns, sessions, and profile facts. The result is a queryable, prunable, semantically searchable memory that survives context resets and accumulates across projects.

The graph is split into two stores:

- **Per-repo conversation graph** (`.agentkg/`) — turns, topics, entities, intents, tasks, summaries
- **Global user profile** (`~/.kgrag/profiles/<person>/`) — preferences, expertise, style, commitments, interests; never pruned

Embeddings use `all-MiniLM-L6-v2` (384-dim) via `sentence-transformers` + sqlite-vec. Structure is treated as ground truth; semantic search is strictly a retrieval accelerant.

---

## Features

- **Incremental ingest** — every turn indexed in real-time; topics, entities, and intents extracted automatically via spaCy + keyword fallback
- **Hybrid query** — semantic seeding (sqlite-vec) + structural expansion (graph traversal)
- **Global UserProfile tree** — preference, expertise, style, commitment, interest, and context nodes accumulated across all repos
- **Structured onboarding** — four-phase interview populates the profile on first use
- **Implicit profile updates** — NLP pipeline extracts standing rules from natural language ("always do X", "I prefer Y")
- **Context assembly** — token-budgeted context block built from the graph for LLM prompt injection
- **KG Context Pruning** — old turns compressed into Summary nodes when the graph grows large
- **Temporal snapshots** — point-in-time JSON snapshots for diffing session state
- **MCP server** — exposes the full query pipeline as structured tools for AI agent integration
- **Script-based hooks** — three Claude Code hooks (UserPromptSubmit, Stop, PreCompact) deployed as shell scripts via `install-hooks`
- **One-line installer** -- `install-skill.sh` provisions the agent skill files, the `/agentkg` slash command, the hooks, the embedding model, and the MCP configs for Claude Code, Kilo Code, GitHub Copilot, and Cline

---

## Quick Start

```bash
# 1. Download the embedding model and create your profile directory
agentkg init --person <you>

# 2. Run the onboarding interview
agentkg onboard --person <you>

# 3. Check your profile
agentkg profile --person <you>
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
agentkg onboard    # writes to ~/.kgrag/profiles/<your-os-username>/
agentkg profile    # reads the same path ← correct

# Multi-user or named profiles: be explicit on profile commands only
agentkg onboard --person alice
agentkg profile --person alice
agentkg query "auth strategy"   # no --person needed here
```

If `agentkg profile` returns an empty `# UserProfile`, check which `--person` value
was used during `onboard`. The completion message prints the exact path.

---

## CLI Reference

All commands accept `--repo <path>` (default `.`). `--person <id>` defaults to your OS
username and is only needed for profile-scoped commands (`init`, `onboard`, `profile`,
`viz --profile`, `wipe --global`).

| Command | Description |
|---|---|
| `agentkg init` | Download embedding model and create profile directory (run first) |
| `agentkg install-hooks` | Deploy hook scripts and wire Claude Code settings.json |
| `agentkg onboard` | Run the structured UserProfile onboarding interview |
| `agentkg profile` | Show the UserProfile as Markdown |
| `agentkg ingest` | Add a turn to the conversation graph |
| `agentkg query` | Semantic search over the graph |
| `agentkg assemble` | Assemble a token-budgeted context block |
| `agentkg prune` | Compress old turns into Summary nodes |
| `agentkg stats` | Show graph node/edge counts |
| `agentkg analyze` | Print a full Markdown analysis report |
| `agentkg sessions` | List all sessions for this repo |
| `agentkg snapshot` | Capture a point-in-time snapshot |
| `agentkg mcp` | Start the MCP server (stdio transport) |

Each command also ships as a dedicated `agentkg-<name>` script — no `poetry run` needed:

```bash
agentkg-init     --person egs          # profile-scoped
agentkg-onboard  --person egs          # profile-scoped
agentkg-profile  --person egs          # profile-scoped
agentkg-stats    --repo .
agentkg-query    "authentication strategy" --k 8 --repo .
agentkg-assemble "what did we decide about auth?" --budget 4000 --repo .
agentkg-prune    --window 20 --repo .
agentkg-mcp
```

---

## Installation

**Requirements:** Python ≥ 3.12, < 3.14

### Bootstrap script (recommended)

To install AgentKG and wire it into your AI coding agents in one step, run
`install-skill.sh` from the repository you want to give memory to:

```bash
curl -fsSL https://raw.githubusercontent.com/Flux-Frontiers/agent_kg/main/scripts/install-skill.sh | bash
```

The script is idempotent. Re-run it to pick up a new release.

It performs nine steps:

1. Installs `SKILL.md` into the Claude Code, Kilo Code, and generic agent skill
   directories
2. Installs the `/agentkg` slash command into `~/.claude/commands/`
3. Installs the `/agentkg` slash command into the target repository for Cline
4. Installs `agent-kg` if the `agentkg` CLI is not already present
5. Runs `agentkg init` to download the embedding model, then installs the spaCy
   `en_core_web_sm` model
6. Runs `agentkg install-hooks` to deploy the three auto-ingest hooks
7. Writes `.mcp.json` for Claude Code and Kilo Code, and optionally registers a
   user-scope MCP server in `~/.claude.json`
8. Writes `.vscode/mcp.json` for GitHub Copilot
9. Writes `cline_mcp_settings.json` for Cline

Unlike the other KGRAG tools, there is no graph build step. The conversation graph
fills in as you converse.

To preview the changes without writing anything, use `--dry-run`:

```bash
bash scripts/install-skill.sh --dry-run
```

#### Options

| Flag | Description |
|---|---|
| `--providers <list>` | Comma-separated provider names, or `all` (default: `all`). Valid names: `claude`, `kilo`, `copilot`, `cline` |
| `--person <id>` | Profile ID under `~/.kgrag/profiles/` (default: your OS username) |
| `--hooks <mode>` | Where to wire the auto-ingest hooks: `global` (default), `claude`, or `none` |
| `--global-mcp` | Also register `agent-kg` as a user-scope MCP server in `~/.claude.json` |
| `--force` | Overwrite existing hook scripts and `settings.json` entries |
| `--skip-init` | Skip the embedding-model download |
| `--dry-run` | Print what would be done without making any changes |

Examples:

```bash
# Claude Code only, hooks scoped to this repo
bash scripts/install-skill.sh --providers claude --hooks claude

# Every provider, plus a user-scope MCP server for all repos
bash scripts/install-skill.sh --providers all --global-mcp --person egs
```

### Poetry

```bash
git clone https://github.com/Flux-Frontiers/agent_kg.git
cd agent_kg
poetry install
```

To install the `dockg` and `pycodekg` CLIs that this repository's pre-commit hook
and release workflow call, add the `kg` group:

```bash
poetry install --with dev,kg
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
The fallback never raises, so a missing model degrades extraction quality silently.
Verify the model is loadable in the same environment that owns the `agentkg` CLI:

```bash
python -c "import spacy; spacy.load('en_core_web_sm')" && echo OK
```

In a `uv`-managed environment, `spacy download` shells out to `uv pip`, which resolves
against the active environment rather than the target interpreter. It can report success
having installed the model elsewhere. If the check above fails after a download, install
the wheel directly into the interpreter that owns `agentkg`:

```bash
uv pip install --python "$(dirname "$(command -v agentkg)")/python" \
  "en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
```

`install-skill.sh` performs this check and falls back to the pinned wheel automatically.

---

## Data Layout

```
<repo-root>/.agentkg/
  graph.sqlite          # nodes + edges (conversation graph)
  vectors.sqlite        # vector embeddings
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
agentkg-mcp   # stdio transport
```

Configure in `.mcp.json` (Claude Code / Kilo Code):

```json
{
  "mcpServers": {
    "agent-kg": {
      "command": "agentkg",
      "args": ["mcp"],
      "env": {
        "AGENTKG_REPO": "/absolute/path/to/repo",
        "AGENTKG_PERSON": "egs"
      }
    }
  }
}
```

### Environment variables

The server takes no `--repo` or `--person` flags. Scope it with environment
variables instead:

| Variable | Default | Purpose |
|---|---|---|
| `AGENTKG_REPO` | `.` (the server's working directory) | Repository whose conversation graph the tools read |
| `AGENTKG_PERSON` | `default` | Profile ID under `~/.kgrag/profiles/` |
| `AGENTKG_SESSION` | unset | Session UUID to scope queries to |

Set `AGENTKG_PERSON` explicitly. It defaults to the literal string `default`, not to
your OS username, so leaving it unset reads an empty profile even when your real
profile is populated.

### Register once for every repository

To expose the memory tools in every repository without adding a per-repo `.mcp.json`,
register the server at user scope in `~/.claude.json`:

```bash
bash scripts/install-skill.sh --global-mcp --person egs
```

Leave `AGENTKG_REPO` unset in a user-scope entry. The server then resolves `.` against
each project's working directory, so one entry serves every repository. Point `command`
at an absolute path rather than a single repository's `.venv`, because MCP servers do
not reliably inherit the login shell `PATH`.

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
agentkg install-hooks --global

# Or wire into .claude/settings.json for this repo only
agentkg install-hooks --claude

# Force-overwrite existing hooks
agentkg install-hooks --global --force
```

`install-skill.sh` runs this step for you. Use `agentkg install-hooks` directly to
change the hook wiring without re-running the full installer.

The installer:
1. Copies the three `.sh` scripts and the `resolve_repo_root.py` helper from the
   package into `~/.agentkg/hooks/` (executable)
2. Merges `UserPromptSubmit`, `Stop`, and `PreCompact` entries into the target `settings.json`

The scripts are portable. Each resolves the repository from the session transcript
using `resolve_repo_root.py`, falls back to `git rev-parse --show-toplevel`, and only
fires when a `.agentkg/` directory is present.

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
│   ├── install-skill.sh              # one-line installer (skill, hooks, MCP configs)
│   └── generate_wiki.py              # GitHub wiki generator
├── .claude/
│   ├── commands/
│   │   └── agentkg.md                # /agentkg slash command
│   └── skills/
│       └── agent-kg/
│           └── SKILL.md              # agent skill reference
├── src/
│   └── agent_kg/
│       ├── __init__.py
│       ├── graph.py                  # AgentKG orchestrator
│       ├── store.py                  # SQLite + sqlite-vec storage
│       ├── index.py                  # sqlite-vec semantic indexing
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
│       │   ├── agent_kg_precompact_hook.sh
│       │   └── resolve_repo_root.py  # repo resolution helper used by all three
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
