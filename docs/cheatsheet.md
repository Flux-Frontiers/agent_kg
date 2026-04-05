# AgentKG Cheatsheet

*Copyright © 2026 Eric G. Suchanek, PhD. All rights reserved. [Elastic License 2.0](https://www.elastic.co/licensing/elastic-license)*

---

## The `--person` Rule

`--person` identifies the **global user profile** at `~/.kgrag/profiles/<person>/`.
The default is your OS login name (`getpass.getuser()`), so it is correct automatically
on a single-user machine.

**Only profile-scoped commands need an explicit `--person`:**
`init`, `onboard`, `profile`, `viz --profile`, `wipe --global`.

Local graph commands (`query`, `assemble`, `stats`, `sessions`, `snapshot`, `prune`,
`ingest`, `analyze`) are **repo-scoped** — `--person` has no effect on what data
they read or write.

```bash
# These two always refer to the same profile on a single-user machine:
agent-kg onboard    # uses getpass.getuser() → correct
agent-kg profile    # same default → correct

# Explicit only needed on shared machines or with named profiles:
agent-kg onboard --person alice
agent-kg profile --person alice
```

---

## Storage Layout

```
<repo-root>/
  .agentkg/
    graph.sqlite          ← conversation graph (turns, topics, entities, tasks)
    lancedb/              ← vector embeddings
    snapshots/            ← point-in-time JSON snapshots

~/.kgrag/profiles/<person>/
  userprofile.sqlite      ← global user profile (never pruned)
```

---

## First-Time Setup

```bash
# 1. Pre-download the embedding model + create profile directory
agent-kg init --person egs

# 2. Build your profile via the structured interview
agent-kg onboard --person egs

# 3. Verify it took
agent-kg profile --person egs

# 4. (Optional) Install the git pre-commit hook
agent-kg install-hooks
```

---

## Core Workflow

### Ingest a turn

```bash
agent-kg ingest "We decided to use OAuth2 with PKCE." --role user
agent-kg ingest "Understood, I'll implement it that way." --role assistant

# Defer embedding (fast — run consolidate later)
agent-kg ingest "quick note" --role user --no-embed
```

Slash commands, `"Session ended."`, and IDE-tag-only turns are silently skipped.

### Semantic search

```bash
agent-kg query "authentication strategy" --k 10

# Also search profile nodes (preferences, commitments, style)
agent-kg query "docstring style" --k 8 --include-profile
```

### Assemble a token-budgeted context block

```bash
# Returns Markdown ready to prepend to a prompt
agent-kg assemble "what did we decide about auth?" --budget 4000
```

### Prune old turns into Summary nodes

```bash
# Keeps 20 most-recent turns verbatim; compresses the rest
agent-kg prune --window 20

# Single-session graph: bypass the "cold turns" gate
agent-kg prune --window 20 --force
```

---

## Inspection & Diagnostics

```bash
# Node/edge counts
agent-kg stats

# Full Markdown analysis report
agent-kg analyze

# List all sessions for this repo
agent-kg sessions

# Show the UserProfile (profile-scoped — --person needed if non-default)
agent-kg profile --person egs
```

### Quick health check

```bash
agent-kg stats
agent-kg profile --person egs
sqlite3 ~/.kgrag/profiles/egs/userprofile.sqlite \
  "SELECT kind, COUNT(*) FROM profile_nodes GROUP BY kind;"
```

---

## Snapshots

```bash
# Capture a snapshot (stored in .agentkg/snapshots/)
agent-kg snapshot
agent-kg snapshot --label "before refactor"
```

---

## Wipe

```bash
# Wipe only this repo's conversation graph (repo-scoped, --person not needed)
agent-kg wipe --local

# Wipe the global user profile (profile-scoped — specify --person if non-default)
agent-kg wipe --global --person egs

# Wipe both without a confirmation prompt
agent-kg wipe --local --global --yes
```

---

## UserProfile (onboarding & updates)

```bash
# Full structured interview (4 phases)
agent-kg onboard --person egs

# Update / refine existing profile
agent-kg onboard --person egs --update

# Skip the optional Personal phase
agent-kg onboard --person egs --skip-optional
```

Profile picks up **implicit updates** automatically during normal ingest —
phrases like *"always do X"* or *"I prefer Y"* are extracted and stored
without needing to re-run the interview.

---

## MCP Server

```bash
agent-kg mcp   # stdio transport
```

`.mcp.json` config (Claude Code / Kilo Code):

```json
{
  "mcpServers": {
    "agent-kg": { "command": "agent-kg-mcp" }
  }
}
```

---

## Hooks (Auto-Ingest Every Prompt)

Add to `.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "hooks": [{
        "type": "command",
        "command": "PROMPT=$(jq -r '.prompt'); REPO_ROOT=\"$(git rev-parse --show-toplevel)\"; agent-kg-ingest \"$PROMPT\" --role user --repo \"$REPO_ROOT\" --no-embed 2>/dev/null || true",
        "async": true
      }]
    }],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "REPO_ROOT=\"$(git rev-parse --show-toplevel)\"; agent-kg-snapshot --repo \"$REPO_ROOT\" --label \"session-end\" 2>/dev/null || true",
        "async": true
      }]
    }]
  }
}
```

- `PROMPT=$(jq -r '.prompt')` captures the **full** multiline prompt (not just the first line)
- `--no-embed` keeps hooks fast — embeddings are populated during a later consolidate pass
- The Stop hook snapshots instead of ingesting a synthetic turn

---

## All Options Reference

| Option | Commands | Default | Notes |
|---|---|---|---|
| `--person TEXT` | `init`, `onboard`, `profile`, `viz --profile`, `wipe --global` | OS username | Only needed for profile-scoped commands or non-default named profiles |
| `--repo PATH` | most | `.` | Use `$(git rev-parse --show-toplevel)` in scripts |
| `--role user\|assistant` | `ingest` | `user` | |
| `--session UUID` | `ingest`, `assemble`, `prune` | auto | Resume a specific session |
| `--no-embed` | `ingest` | off | Defer embedding; run consolidate later |
| `--include-profile` | `query` | off | Also search profile nodes (preferences, style, commitments) |
| `--k INT` | `query` | `8` | Number of results |
| `--budget INT` | `assemble` | `4000` | Token budget for context block |
| `--window INT` | `prune` | `20` | Keep N most-recent turns verbatim |
| `--force` | `prune` | off | Bypass "cold turns" readiness check |
| `--label TEXT` | `snapshot` | none | Human-readable snapshot label |
| `--update` | `onboard` | off | Re-run to refine preferences |
| `--skip-optional` | `onboard` | off | Skip Personal phase |
| `--local` | `wipe` | off | Wipe `.agentkg/` conversation graph |
| `--global` | `wipe` | off | Wipe `~/.kgrag/profiles/<person>/` |
| `--yes` / `-y` | `wipe` | off | Skip confirmation prompt |
| `--force` | `install-hooks` | off | Overwrite existing pre-commit hook |
| `--model TEXT` | `init` | `all-MiniLM-L6-v2` | Embedding model to pre-download |

---

## Node Kinds

| Kind | Where stored | What it holds |
|---|---|---|
| `turn` | local graph | Raw user/assistant message |
| `topic` | local graph | N-gram topics from turns |
| `entity` | local graph | Named entities (people, tools, projects) |
| `intent` | local graph | Classified intent per turn |
| `task` | local graph | Action items extracted from conversation |
| `summary` | local graph | Compressed summaries (after prune) |
| `preference` | global profile | Coding/style preferences |
| `commitment` | global profile | Standing rules ("always do X") |
| `expertise` | global profile | Domain knowledge areas |
| `interest` | global profile | Topics the user cares about |
| `style` | global profile | Formatting/verbosity preferences |
| `context` | global profile | Role, machine, active projects |

---

## Common Issues

### Profile is empty after onboarding

```bash
# Check where data actually went
sqlite3 ~/.kgrag/profiles/egs/userprofile.sqlite \
  "SELECT kind, label FROM profile_nodes;"

# If the file is missing, re-run interactively (stdin must be a TTY)
agent-kg onboard --person egs
```

### Prune says "Not enough cold turns to prune yet"

Pruning normally requires turns from completed (closed) sessions. Use `--force` to
prune the current session anyway:

```bash
agent-kg prune --window 20 --force
```

### Semantic search returns `score=0.000`

Turns were ingested with `--no-embed`. Run without that flag or trigger a consolidate pass:

```bash
agent-kg ingest "test" --role user   # populates LanceDB
```

### Wrong repo path in hooks

Always use `$(git rev-parse --show-toplevel)` — never a hardcoded path.
A wrong path silently discards every turn (`2>/dev/null || true` swallows the error).

### Skip the pre-commit snapshot

```bash
AGENTKG_SKIP_SNAPSHOT=1 git commit ...
```
