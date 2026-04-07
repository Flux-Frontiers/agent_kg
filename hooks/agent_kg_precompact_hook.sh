#!/bin/bash
# AGENT-KG PRE-COMPACT HOOK
#
# Claude Code "PreCompact" hook. Fires right before the conversation
# is compressed to free up context window space.
#
# Runs `agent-kg prune` SYNCHRONOUSLY so all current turns are compressed
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

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
if [ ! -d "$REPO_ROOT/.agentkg" ]; then
    echo "{}"
    exit 0
fi

echo "[$(date '+%H:%M:%S')] PreCompact triggered for session $SESSION_ID" >> "$STATE_DIR/hook.log"

# Run prune synchronously — summaries + embeddings must land before compaction
agent-kg prune --repo "$REPO_ROOT" --force >> "$STATE_DIR/hook.log" 2>&1

# Snapshot synchronously so the pre-compaction state is preserved
agent-kg snapshot --repo "$REPO_ROOT" --label "pre-compact" 2>/dev/null

echo "[$(date '+%H:%M:%S')] PreCompact complete for session $SESSION_ID" >> "$STATE_DIR/hook.log"

# Let compaction proceed
echo "{}"
