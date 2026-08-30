#!/bin/bash
# AGENT-KG PRE-COMPACT HOOK
#
# Claude Code "PreCompact" hook. Fires right before the conversation
# is compressed to free up context window space.
#
# Runs `agentkg prune` SYNCHRONOUSLY so all current turns are compressed
# into summaries (with embeddings) before the context window is wiped.
# Then snapshots the graph. Both complete before compaction proceeds.
#
# This is the safety net: without it, turns ingested since the last Stop
# (in-flight at compaction time) would be lost from the semantic index.
#
# === INSTALL ===
# In ~/.claude/settings.json (or .claude/settings.local.json):
#
#   "hooks": {
#     "PreCompact": [{
#       "hooks": [{
#         "type": "command",
#         "command": "/absolute/path/to/hooks/agent_kg_precompact_hook.sh",
#         "timeout": 60
#       }]
#     }]
#   }
#
# === INPUT (from Claude Code via stdin) ===
#   session_id — unique session identifier

STATE_DIR="$HOME/.agentkg/hook_state"
mkdir -p "$STATE_DIR"

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id','unknown'))" 2>/dev/null)
TRANSCRIPT_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('transcript_path',''))" 2>/dev/null)
TRANSCRIPT_PATH="${TRANSCRIPT_PATH/#\~/$HOME}"

# Resolve the repo this session belongs to. Never derive it from the process
# working directory alone: a hook inherits whatever directory the agent's shell
# last moved to, so a session that inspects a sibling repo would ingest into --
# and prune -- that repo instead of its own.
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT=$(python3 "$HOOK_DIR/resolve_repo_root.py" "$TRANSCRIPT_PATH" 2>/dev/null)
[ -n "$REPO_ROOT" ] || REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
if [ ! -d "$REPO_ROOT/.agentkg" ]; then
    echo "{}"
    exit 0
fi

# Resolve the agentkg CLI. Hook processes do not reliably inherit the login
# shell's PATH, so fall back to the default uv tool install location.
AGENTKG=$(command -v agentkg 2>/dev/null)
if [ -z "$AGENTKG" ] && [ -x "$HOME/.local/bin/agentkg" ]; then
    AGENTKG="$HOME/.local/bin/agentkg"
fi
if [ -z "$AGENTKG" ]; then
    echo "[$(date '+%H:%M:%S')] agentkg not found on PATH — skipping" >> "$STATE_DIR/hook.log"
    echo "{}"
    exit 0
fi

echo "[$(date '+%H:%M:%S')] PreCompact triggered for session $SESSION_ID" >> "$STATE_DIR/hook.log"

# Run prune synchronously — summaries + embeddings must land before compaction
"$AGENTKG" prune --repo "$REPO_ROOT" --force >> "$STATE_DIR/hook.log" 2>&1

# Snapshot synchronously so the pre-compaction state is preserved
"$AGENTKG" snapshot --repo "$REPO_ROOT" --label "pre-compact" 2>/dev/null

echo "[$(date '+%H:%M:%S')] PreCompact complete for session $SESSION_ID" >> "$STATE_DIR/hook.log"

# Let compaction proceed
echo "{}"
