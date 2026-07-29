# Automated Temporal Snapshots (Git Hooks)

AgentKG captures snapshots automatically through **git hooks and Claude Code hooks** —
not a GitHub Actions workflow. There are two distinct snapshot streams.

## How It Works

Hooks are installed with:

```bash
agentkg install-hooks --repo .     # git pre-commit hook (tracked graph snapshots)
agentkg install-hooks --claude     # Claude Code hooks for THIS repo (conversation snapshots)
agentkg install-hooks --global     # Claude Code hooks for ALL repos
```

### 1. Tracked graph snapshots — git pre-commit hook

The pre-commit hook (`.git/hooks/pre-commit`, installed by `agentkg install-hooks`) runs
**before** the quality checks on every commit. It:

1. Captures the staged tree hash (`git write-tree`) and current branch.
2. If `pycodekg` is available: rebuilds the PyCodeKG index and runs
   `pycodekg snapshot save --tree-hash <hash> --branch <branch>`, then stages
   `.pycodekg/snapshots/`.
3. If `dockg` is available and a `docs/` directory exists: rebuilds the DocKG index and
   runs `dockg snapshot save …`, then stages `.dockg/snapshots/`.
4. Runs the `pre-commit` framework checks (ruff, ty, detect-secrets, …).

These snapshots capture **code/doc graph** metrics and **are committed** to the repo.

Skip a snapshot on a given commit with:

```bash
AGENTKG_SKIP_SNAPSHOT=1 git commit -m "…"
```

### 2. Conversation snapshots — `agentkg snapshot` / Claude Code hooks

AgentKG's own conversation-memory snapshots are written to `<repo>/.agentkg/snapshots/<timestamp>.json`.
This directory is **private and git-ignored** (it holds conversation data). They are produced by:

- The CLI: `agentkg snapshot --repo . [--label <label>]`
- The Claude Code `Stop` hook — snapshots asynchronously at session end (`--label session-end`).
- The Claude Code `PreCompact` hook — prunes + snapshots **synchronously** before context
  compaction, so no turns are lost.

## Snapshot Contents

A conversation snapshot (`capture()` in `agent_kg/snapshots.py`) stores:

- **timestamp** — ISO 8601 UTC
- **version** / **label** — version string and optional human label
- **node_count** / **edge_count** — totals
- **kind_counts** — node counts by kind (turn, topic, entity, intent, task, summary, …)
- **turn_count** / **summary_count** / **open_task_count** / **session_count**
- **pruning_pass** — highest pruning pass seen

## Viewing Results

### Conversation snapshots (CLI)

```bash
# Capture one now
agentkg snapshot --repo . --label "pre-refactor"
```

Example output:

```
Snapshot captured: 2026-06-13T20:15:00+00:00
  Nodes: 412, Edges: 538
  Turns: 96, Summaries: 7
```

### Tracked graph snapshots (git history)

```bash
git log --oneline -- .pycodekg/snapshots/
git log --oneline -- .dockg/snapshots/
```

## Programmatic Access

```python
from pathlib import Path
from agent_kg.snapshots import capture, list_snapshots, diff_snapshots

snaps_dir = Path(".agentkg/snapshots")

# All snapshots for this repo, newest first
snapshots = list_snapshots(snaps_dir)

# Compare two snapshot dicts
delta = diff_snapshots(snapshots[1], snapshots[0])
```

> `agent_kg.snapshots` exposes functions (`capture`, `list_snapshots`, `diff_snapshots`) —
> there is no `SnapshotManager` class.

## What Gets Committed

| Path | Tracked? | Captured by |
|---|---|---|
| `.pycodekg/snapshots/*.json` | ✅ committed | git pre-commit hook (`pycodekg snapshot save`) |
| `.dockg/snapshots/*.json` | ✅ committed | git pre-commit hook (`dockg snapshot save`) |
| `.agentkg/snapshots/*.json` | ❌ git-ignored (private) | `agentkg snapshot` / Claude Code `Stop` + `PreCompact` hooks |

## Troubleshooting

### No graph snapshot was committed
- `pycodekg`/`dockg` may not be installed in the environment — the hook skips them silently.
  Install the KG integrations by hand: `pip install doc-kg pycode-kg`.
- Run `pycodekg build --repo .` once to initialize the index, then commit again.
- Confirm the hook is installed: `cat .git/hooks/pre-commit` (re-install with
  `agentkg install-hooks --repo . --force`).

### Conversation snapshot is empty
- The graph has no turns yet — ingest some first (`agentkg ingest …`) or let the Claude
  Code hooks run.

### A commit is taking too long
- Index rebuilds run in the pre-commit hook. Use `AGENTKG_SKIP_SNAPSHOT=1 git commit …` to
  skip on a one-off commit.
