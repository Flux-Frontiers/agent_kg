---
name: agent-kg
author: Eric G. Suchanek, PhD <suchanek@mac.com>
license: Elastic-2.0
description: >
  Expert knowledge for using AgentKG — conversational memory as a live, queryable knowledge
  graph. Use this skill when: working in a repo that has AgentKG installed (check for a
  .agentkg/ directory or agent-kg in pyproject.toml), querying past conversation context,
  understanding what a user has told you before, surfacing user preferences or commitments,
  running or debugging agent-kg CLI commands (agent-kg-ingest, agent-kg-query,
  agent-kg-assemble, agent-kg-prune, agent-kg-stats, agent-kg-analyze, agent-kg-sessions,
  agent-kg-snapshot, agent-kg-onboard, agent-kg-profile, agent-kg-mcp), setting up hooks to
  auto-ingest conversation turns, managing the UserProfile, or troubleshooting why profile
  or memory data is missing.
---

# AgentKG Skill

AgentKG stores conversational memory in a knowledge graph (SQLite + LanceDB) that persists
across sessions. Every user turn, assistant turn, topic, entity, intent, task, and user
preference is a node. Edges encode relationships. The result is a queryable, pruneable,
semantically searchable memory that survives context resets.

## Data Layout

```
<repo-root>/.agentkg/          ← per-repo conversation graph
  graph.sqlite                 ← nodes + edges (SQLite)
  lancedb/                     ← vector embeddings
  snapshots/                   ← point-in-time JSON snapshots

~/.kgrag/profiles/<person_id>/ ← GLOBAL user profile (never pruned)
  userprofile.sqlite           ← preference, expertise, style, commitment, interest, context nodes
```

The profile is **repo-independent** — it accumulates across every project the user works in.

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
| `commitment` | Standing rules ("always do X") (profile) |
| `expertise` | Domain knowledge areas (profile) |
| `interest` | Topics the user cares about (profile) |
| `style` | Formatting/docstring/verbosity preferences (profile) |
| `context` | Role, machine, projects context (profile) |

## CLI Commands

All commands accept `--repo <path>` (default `.`) and `--person <id>` (default `default`).
Always resolve `--repo` dynamically: `--repo "$(git rev-parse --show-toplevel)"`.

### Core workflow

```bash
# Ingest a turn (hooks do this automatically — call directly when needed)
agent-kg-ingest "text" --role user|assistant --repo . --person egs [--no-embed]

# Semantic search over the KG
agent-kg-query "authentication strategy" --k 10 --repo . --person egs

# Assemble a token-budgeted context block for a prompt
agent-kg-assemble "what did we decide about auth?" --budget 4000 --repo . --person egs

# Show graph statistics
agent-kg-stats --repo . --person egs

# Full Markdown analysis report
agent-kg-analyze --repo . --person egs

# List all sessions
agent-kg-sessions --repo . --person egs

# Capture a snapshot
agent-kg-snapshot --repo . --person egs [--label "before refactor"]
```

### Profile & onboarding

```bash
# Run the structured onboarding interview (interactive, populates ~/.kgrag/profiles/)
agent-kg-onboard --repo . --person egs [--update] [--skip-optional]

# Show the UserProfile as Markdown
agent-kg-profile --repo . --person egs
```

### Pruning (compression)

```bash
# Compress old turns into Summary nodes (run when turn count gets large)
agent-kg-prune --window 20 --repo . --person egs
```

`--window N` keeps the N most-recent turns verbatim; older turns are summarised.

### MCP server

```bash
agent-kg-mcp   # starts the MCP server (stdio transport)
```

## Hooks (Auto-Ingest)

The `.claude/settings.json` hooks ingest every prompt and session-end automatically:

```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "hooks": [{
        "type": "command",
        "command": "jq -r '.prompt' | { read -r p; REPO_ROOT=\"$(git rev-parse --show-toplevel)\"; agent-kg ingest \"$p\" --role user --repo \"$REPO_ROOT\" --person egs --no-embed; } 2>/dev/null || true",
        "async": true
      }]
    }],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "REPO_ROOT=\"$(git rev-parse --show-toplevel)\"; agent-kg ingest \"Session ended.\" --role assistant --repo \"$REPO_ROOT\" --person egs --no-embed 2>/dev/null || true",
        "async": true
      }]
    }]
  }
}
```

`--no-embed` defers embedding to a later consolidate pass — keeps hooks fast.

## Querying for Context (When to Use)

Before answering questions about past decisions, user preferences, or prior work:

```bash
# What did we decide about X?
agent-kg-assemble "X" --budget 4000 --repo . --person egs

# What does this user prefer?
agent-kg-profile --repo . --person egs

# Find relevant past turns
agent-kg-query "X" --k 8 --repo . --person egs
```

Use `assemble` when you need a formatted context block to prepend to a prompt.
Use `query` when you want raw ranked results to inspect.

## Common Issues

### Profile is empty after onboarding

The profile db is at `~/.kgrag/profiles/<person_id>/userprofile.sqlite`.
If it exists but has 0 rows, the interview likely ran with empty/piped stdin.
Re-run interactively and verify:

```bash
agent-kg-onboard --repo . --person egs
sqlite3 ~/.kgrag/profiles/egs/userprofile.sqlite \
  "SELECT kind, label FROM profile_nodes;"
```

### Semantic search returns score=0.000

Turns were ingested with `--no-embed`. The LanceDB index is empty.
Embeddings are populated when turns are ingested **without** `--no-embed`, or after
a consolidate pass. Run a few turns without `--no-embed` to populate the index.

### Wrong repo path in hooks

Always use `$(git rev-parse --show-toplevel)` — never a hardcoded path.
A broken path silently discards every ingested turn (the `2>/dev/null || true` swallows errors).

## Quick Health Check

```bash
agent-kg-stats --repo . --person egs          # should show node/edge counts
agent-kg-profile --repo . --person egs        # should show profile sections
sqlite3 ~/.kgrag/profiles/egs/userprofile.sqlite \
  "SELECT kind, COUNT(*) FROM profile_nodes GROUP BY kind;"
```
