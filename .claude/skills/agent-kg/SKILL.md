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
  agent-kg-snapshot, agent-kg-onboard, agent-kg-profile, agent-kg-viz, agent-kg-wipe,
  agent-kg-mcp), setting up hooks to auto-ingest conversation turns, managing the
  UserProfile, or troubleshooting why profile or memory data is missing.
---

# AgentKG Skill

AgentKG stores conversational memory in a knowledge graph (SQLite + LanceDB) that persists
across sessions. Every user turn, assistant turn, topic, entity, intent, task, and user
preference is a node. Edges encode relationships. The result is a queryable, prunable,
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

All commands accept `--repo <path>` (default `.`) and `--person <id>` (default: OS username).
Always resolve `--repo` dynamically: `--repo "$(git rev-parse --show-toplevel)"`.

**`--person` is only needed** when you have multiple named profiles or are on a shared machine.
Local graph operations (`query`, `assemble`, `stats`, `sessions`, `snapshot`, `prune`) are
repo-scoped — `--person` does not affect what conversation data is searched.
`--person` matters for `profile`, `onboard`, `viz --profile`, and `wipe --global`, which
directly access `~/.kgrag/profiles/<person>/`.

### Core workflow

```bash
# Ingest a turn (hooks do this automatically — call directly when needed)
# Slash commands, "Session ended.", and IDE-tag-only turns are silently skipped.
agent-kg-ingest "text" --role user|assistant --repo .  [--no-embed]

# Semantic search over the conversation graph
agent-kg-query "authentication strategy" --k 10 --repo .

# Also search profile nodes (preferences, commitments, expertise, style)
agent-kg-query "docstring style" --k 8 --repo . --include-profile

# Assemble a token-budgeted context block for a prompt
agent-kg-assemble "what did we decide about auth?" --budget 4000 --repo .

# Show graph statistics
agent-kg-stats --repo .

# Full Markdown analysis report
agent-kg-analyze --repo .

# List all sessions
agent-kg-sessions --repo .

# Capture a snapshot
agent-kg-snapshot --repo . [--label "before refactor"]
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
agent-kg-prune --window 20 --repo .

# Force pruning even when all turns are in the current session
agent-kg-prune --window 20 --repo . --force
```

`--window N` keeps the N most-recent turns verbatim; older turns are summarised.
`--force` bypasses the "cold turns" readiness check — needed when all turns are in one session.

### Visualization

```bash
# Terminal trees (no extra deps)
agent-kg-viz --repo .

# Interactive HTML for the conversation graph
agent-kg-viz --agent --html --repo .

# Interactive HTML for the profile
agent-kg-viz --profile --html --repo . --person egs

# Full Streamlit explorer (requires pip install "agent-kg[viz]")
agent-kg-viz --serve --repo .
```

### Wipe

```bash
# Erase the local conversation graph only
agent-kg-wipe --local --repo .

# Erase the global user profile (all repos)
agent-kg-wipe --global --person egs

# Skip confirmation prompt
agent-kg-wipe --local --global --yes
```

### MCP server

```bash
agent-kg-mcp   # starts the MCP server (stdio transport)
```

## Hooks (Auto-Ingest)

The `.claude/settings.json` hooks ingest every prompt automatically and snapshot at session end:

```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "hooks": [{
        "type": "command",
        "command": "PROMPT=$(jq -r '.prompt'); REPO_ROOT=\"$(git rev-parse --show-toplevel)\"; agent-kg ingest \"$PROMPT\" --role user --repo \"$REPO_ROOT\" --person egs --no-embed 2>/dev/null || true",
        "async": true
      }]
    }],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "REPO_ROOT=\"$(git rev-parse --show-toplevel)\"; agent-kg snapshot --repo \"$REPO_ROOT\" --person egs --label \"session-end\" 2>/dev/null || true",
        "async": true
      }]
    }]
  }
}
```

Key points:
- `PROMPT=$(jq -r '.prompt')` captures the **full** multiline prompt (not just the first line)
- `--no-embed` defers embedding to a later consolidate pass — keeps hooks fast
- The Stop hook captures a metrics snapshot instead of ingesting a synthetic turn
- Slash commands (`/foo`) and turns that are empty after stripping IDE tags are silently skipped by the ingest pipeline — no graph pollution

## Querying for Context

Choose the right tool for the query type:

| What you need | Command |
|---|---|
| Past architectural decision, prior work | `agent-kg-assemble "topic" --budget 4000` |
| User preferences, style, commitments | `agent-kg-profile` |
| Preferences via query interface | `agent-kg-query "style pref" --include-profile` |
| Raw ranked hits to inspect scores | `agent-kg-query "topic" --k 8` |

```bash
# What did we decide about X? (best for architectural/decision recall)
agent-kg-assemble "X" --budget 4000 --repo .

# What does this user prefer? (direct profile read — always start here)
agent-kg-profile --repo . --person egs

# Find relevant past turns + matching profile nodes in one call
agent-kg-query "X" --k 8 --repo . --include-profile
```

## Common Issues

### Prune says "Not enough cold turns to prune yet"

Pruning normally requires turns from completed (closed) sessions — "cold turns".
If all turns are in the current session, use `--force`:

```bash
agent-kg-prune --window 20 --repo . --person egs --force
```

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
Run a consolidate pass or ingest a few turns without `--no-embed` to populate embeddings.

### Wrong repo path in hooks

Always use `$(git rev-parse --show-toplevel)` — never a hardcoded path.
A broken path silently discards every ingested turn (the `2>/dev/null || true` swallows errors).

## Quick Health Check

```bash
agent-kg-stats --repo .                        # node/edge counts by kind
agent-kg-profile --repo . --person egs        # profile sections populated?
sqlite3 ~/.kgrag/profiles/egs/userprofile.sqlite \
  "SELECT kind, COUNT(*) FROM profile_nodes GROUP BY kind;"
```
