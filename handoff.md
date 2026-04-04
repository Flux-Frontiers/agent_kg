# AgentKG Handoff — Profile Bug Investigation

*Copyright © 2026 Eric G. Suchanek, PhD. All rights reserved. [Elastic License 2.0](https://www.elastic.co/licensing/elastic-license)*

## What We Were Doing

Investigating why `agent-kg profile` returns an empty `# UserProfile` even though
the user reports having run `agent-kg onboard`.

## Diagnosis So Far

### Profile storage path

`UserProfileStore` (defined in `src/agent_kg/profile.py:55`) stores data at:

```
~/.kgrag/profiles/<person_id>/userprofile.sqlite
```

This is **global** — independent of `--repo`. Correct path for person `egs`:

```
/Users/egs/.kgrag/profiles/egs/userprofile.sqlite
```

### What we found on disk

```
/Users/egs/.kgrag/profiles/egs/
  userprofile.sqlite   — 24 576 bytes, schema exists, profile_nodes has 0 rows
  profile.sqlite       — 0 bytes (ghost file, wrong name)
```

The schema (`profile_nodes`, `profile_edges`) is correct. The tables exist. But
`SELECT COUNT(*) FROM profile_nodes` returns 0 — onboarding wrote nothing.

### Most likely cause

Two candidates:

1. **Silent write failure** — `upsert()` commits correctly but something upstream
   prevented answers from reaching it. Check if the `input()` call in
   `onboard.py:106` read empty strings (e.g. non-interactive TTY, piped stdin).
   Every blank answer hits `if not answer: continue` and is silently skipped.

2. **Stale binary** — If a previous `agent-kg` binary (from before the sync) was
   on PATH, it may have written to a different profile path and the current code
   is looking somewhere else. Verify with `which agent-kg` and `agent-kg --version`.

### What was NOT the cause

- Filename mismatch: `profile.py` consistently uses `userprofile.sqlite` —
  the 0-byte `profile.sqlite` is a ghost from an earlier draft, not the active file.
- NodeKind string encoding: `NodeKind` is a `StrEnum` so `str(NodeKind.PREFERENCE)`
  == `"preference"` — storage and retrieval are consistent.
- `--repo` path: profile location doesn't depend on `--repo` at all.

## Recommended Fix / Next Step

Re-run onboarding interactively and confirm rows appear:

```bash
agent-kg onboard --repo . --person egs
# answer at least one question
sqlite3 ~/.kgrag/profiles/egs/userprofile.sqlite \
  "SELECT kind, label FROM profile_nodes;"
```

If rows appear now but didn't before, the previous run had empty/piped stdin.
If rows still don't appear, add a debug print inside `upsert()` to confirm it
is being called with the expected arguments.

## Repo State

The external `agent_kg` repo (`/Users/egs/repos/agent_kg/`) was just fully synced
from the evolved internal version in `kgrag/src/agent_kg/`. All files match.

Changes made this session:
- `pyproject.toml` — added all 12 `agent-kg-*` entry points + `agent-kg-mcp`
- `.gitignore` — added `.agentkg/` block
- `.claude/settings.json` — created with correct hooks using
  `$(git rev-parse --show-toplevel)` for `--repo` (was broken `/home/user/KGRAG`)
- `src/agent_kg/index.py` — ported `ConversationIndex` (LanceDB semantic index)
- `src/agent_kg/kg.py` — re-export shim for `AgentKG` import compatibility
