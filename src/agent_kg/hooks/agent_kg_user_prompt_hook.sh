#!/bin/bash
# AGENT-KG USER PROMPT HOOK
#
# Claude Code "UserPromptSubmit" hook.
# Ingests the user turn into the AgentKG conversation graph.
#
# === INSTALL ===
# In ~/.claude/settings.json (or .claude/settings.local.json):
#
#   "hooks": {
#     "UserPromptSubmit": [{
#       "hooks": [{
#         "type": "command",
#         "command": "/absolute/path/to/hooks/agent_kg_user_prompt_hook.sh"
#       }]
#     }]
#   }
#
# === INPUT (from Claude Code via stdin) ===
#   prompt       — the user's raw message text
#   session_id   — unique session identifier

INPUT=$(cat)

PROMPT=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('prompt',''))" 2>/dev/null)

# Resolve repo root; skip if not in a git repo with an .agentkg dir
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
if [ ! -d "$REPO_ROOT/.agentkg" ]; then
    echo "{}"
    exit 0
fi

# Ingest user turn — embeddings enabled (fast enough for user turns)
if [ -n "$PROMPT" ]; then
    agent-kg ingest "$PROMPT" --role user --repo "$REPO_ROOT" 2>/dev/null || true
fi

echo "{}"
