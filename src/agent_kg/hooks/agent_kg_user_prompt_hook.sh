#!/bin/bash
# AGENT-KG USER PROMPT HOOK
#
# Claude Code "UserPromptSubmit" hook. Does two jobs:
#
#   write side - ingests the user turn into the AgentKG conversation graph
#   read side  - assembles a token-budgeted context block from the graph and
#                returns it as additionalContext, so recalled memory reaches
#                the model on the same turn
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
#   prompt       - the user's raw message text
#   session_id   - unique session identifier
#
# === OUTPUT ===
#   JSON on stdout. Anything this script writes to stdout is injected into the
#   model's context, so every subcommand below is redirected to /dev/null and
#   the only thing printed is the final JSON object.

# Assembly budget, in tokens, for the injected context block.
BUDGET=1200
# Prompts shorter than this skip assembly entirely. Acknowledgements ("ok",
# "go ahead") almost never benefit from recall, and assembly costs ~2s.
MIN_CHARS=25

INPUT=$(cat)

PROMPT=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('prompt',''))" 2>/dev/null)
SESSION_ID=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id',''))" 2>/dev/null)
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
# shell's PATH, so fall back to the default uv tool install location before
# giving up. Without this the hook exits 0 having silently done nothing.
AGENTKG=$(command -v agentkg 2>/dev/null)
if [ -z "$AGENTKG" ] && [ -x "$HOME/.local/bin/agentkg" ]; then
    AGENTKG="$HOME/.local/bin/agentkg"
fi
if [ -z "$AGENTKG" ]; then
    echo "{}"
    exit 0
fi

# --- write side: ingest the user turn (embeddings on; fast enough here) ---
if [ -n "$PROMPT" ]; then
    "$AGENTKG" ingest "$PROMPT" --role user --repo "$REPO_ROOT" \
        ${SESSION_ID:+--session "$SESSION_ID"} >/dev/null 2>&1 || true
fi

# --- read side: assemble recalled context for this prompt ---
if [ "${#PROMPT}" -lt "$MIN_CHARS" ]; then
    echo "{}"
    exit 0
fi

CONTEXT=$("$AGENTKG" assemble "$PROMPT" --repo "$REPO_ROOT" --budget "$BUDGET" \
    ${SESSION_ID:+--session "$SESSION_ID"} 2>/dev/null)
if [ -z "$CONTEXT" ]; then
    echo "{}"
    exit 0
fi

# Pass through the environment rather than argv: the block is multi-line and
# contains arbitrary recalled text. json.dumps handles the escaping.
CONTEXT="$CONTEXT" python3 -c '
import json, os
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": os.environ["CONTEXT"],
    }
}))
' 2>/dev/null || echo "{}"
