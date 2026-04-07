#!/bin/bash
# AGENT-KG STOP HOOK
#
# Claude Code "Stop" hook. After every assistant response:
#   1. Ingests the assistant turn into the graph (--no-embed for speed)
#   2. Every CONSOLIDATE_INTERVAL human exchanges, runs `agent-kg prune`
#      asynchronously to compress old turns into summaries
#   3. Snapshots the graph asynchronously
#
# === INSTALL ===
# In ~/.claude/settings.json (or .claude/settings.local.json):
#
#   "hooks": {
#     "Stop": [{
#       "hooks": [{
#         "type": "command",
#         "command": "/absolute/path/to/hooks/agent_kg_stop_hook.sh",
#         "timeout": 30
#       }]
#     }]
#   }
#
# === INPUT (from Claude Code via stdin) ===
#   session_id              — unique session identifier
#   stop_hook_active        — true if we already blocked this cycle
#   last_assistant_message  — the assistant's response text
#   transcript_path         — path to the JSONL session transcript

CONSOLIDATE_INTERVAL=20   # Run prune every N human messages
STATE_DIR="$HOME/.agentkg/hook_state"
mkdir -p "$STATE_DIR"

INPUT=$(cat)

SESSION_ID=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id','unknown'))" 2>/dev/null)
MSG=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('last_assistant_message',''))" 2>/dev/null)
TRANSCRIPT_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('transcript_path',''))" 2>/dev/null)

# Expand ~ in transcript path
TRANSCRIPT_PATH="${TRANSCRIPT_PATH/#\~/$HOME}"

# Resolve repo root; skip if no .agentkg
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
if [ ! -d "$REPO_ROOT/.agentkg" ]; then
    echo "{}"
    exit 0
fi

# 1. Ingest assistant turn (--no-embed: consolidation pass handles embeddings)
if [ -n "$MSG" ]; then
    agent-kg ingest "$MSG" --role assistant --repo "$REPO_ROOT" --no-embed 2>/dev/null || true
fi

# 2. Count human messages in transcript to decide whether to consolidate
EXCHANGE_COUNT=0
if [ -f "$TRANSCRIPT_PATH" ]; then
    EXCHANGE_COUNT=$(python3 - "$TRANSCRIPT_PATH" <<'PYEOF'
import json, sys
count = 0
with open(sys.argv[1]) as f:
    for line in f:
        try:
            entry = json.loads(line)
            msg = entry.get('message', {})
            if isinstance(msg, dict) and msg.get('role') == 'user':
                content = msg.get('content', '')
                if isinstance(content, str) and '<command-message>' in content:
                    continue
                count += 1
        except Exception:
            pass
print(count)
PYEOF
2>/dev/null)
fi

LAST_CONSOLIDATE_FILE="$STATE_DIR/${SESSION_ID}_last_consolidate"
LAST_CONSOLIDATE=0
if [ -f "$LAST_CONSOLIDATE_FILE" ]; then
    LAST_CONSOLIDATE=$(cat "$LAST_CONSOLIDATE_FILE")
fi

SINCE_LAST=$((EXCHANGE_COUNT - LAST_CONSOLIDATE))

echo "[$(date '+%H:%M:%S')] Stop session=$SESSION_ID exchanges=$EXCHANGE_COUNT since_last_consolidate=$SINCE_LAST" >> "$STATE_DIR/hook.log"

# 3. Periodic consolidation (prune old turns → summaries, populate embeddings)
if [ "$SINCE_LAST" -ge "$CONSOLIDATE_INTERVAL" ] && [ "$EXCHANGE_COUNT" -gt 0 ]; then
    echo "$EXCHANGE_COUNT" > "$LAST_CONSOLIDATE_FILE"
    echo "[$(date '+%H:%M:%S')] Triggering consolidation at exchange $EXCHANGE_COUNT" >> "$STATE_DIR/hook.log"
    agent-kg prune --repo "$REPO_ROOT" --force >> "$STATE_DIR/hook.log" 2>&1 &
fi

# 4. Async snapshot
agent-kg snapshot --repo "$REPO_ROOT" --label "session-end" 2>/dev/null &

echo "{}"
