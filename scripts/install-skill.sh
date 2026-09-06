#!/usr/bin/env bash
# =============================================================================
# install-skill.sh -- Bootstrap the AgentKG AI integration layer
#
# Installs the AgentKG SKILL.md reference files and the /agentkg slash command
# for AI agents, initializes the embedding model and user profile, deploys the
# auto-ingest hooks, then configures MCP server integration for the requested
# providers.
#
# Supported providers:
#   claude   -- Claude Code    (.mcp.json, shared with Kilo Code)
#   kilo     -- Kilo Code      (.mcp.json, shared with Claude Code)
#   copilot  -- GitHub Copilot (.vscode/mcp.json)
#   cline    -- Cline          (cline_mcp_settings.json + repo slash command)
#
# Usage (from a target repo, no clone needed):
#   curl -fsSL https://raw.githubusercontent.com/Flux-Frontiers/agent_kg/main/scripts/install-skill.sh | bash
#
# With options:
#   curl -fsSL .../install-skill.sh | bash -s -- --providers all
#   bash scripts/install-skill.sh --providers claude,copilot --person egs
#   bash scripts/install-skill.sh --hooks claude --dry-run
#
# Flags:
#   --providers <list>   Comma-separated provider names, or "all" (default: all)
#   --person <id>        Profile ID under ~/.kgrag/profiles/ (default: OS username)
#   --hooks <mode>       Where to wire the Claude Code auto-ingest hooks:
#                          global -- ~/.claude/settings.json, all repos (default)
#                          claude -- <repo>/.claude/settings.json, this repo only
#                          none   -- skip hook installation
#   --force              Overwrite existing hook scripts and settings.json entries
#   --skip-init          Skip the embedding-model download (agentkg init)
#   --global-mcp         Also register agent-kg as a user-scope MCP server in
#                        ~/.claude.json, so every repo gets the memory tools
#                        without a per-repo .mcp.json entry
#   --dry-run            Print what would be done without making any changes
#
# What it does:
#   1. Installs SKILL.md into the Claude Code, Kilo Code, and generic agent
#      skill directories
#   2. Installs the /agentkg slash command into ~/.claude/commands/
#   3. Installs the /agentkg slash command into the target repo for Cline
#   4. Installs agent-kg if the agentkg CLI is not found:
#        a. pip install from the latest GitHub release wheel (no git needed)
#        b. pip install from git+https (fallback, needs git)
#   5. Runs `agentkg init` to download the embedding model and create the
#      profile directory, plus the spaCy en_core_web_sm model
#   6. Runs `agentkg install-hooks` to deploy the three auto-ingest hooks
#   7. Writes the provider MCP configs as requested
#   8. Prints a final summary and the remaining manual steps
#
# Note: unlike PyCodeKG, there is no graph build step. The AgentKG conversation
# graph is populated incrementally by the hooks as you converse.
#
# Author: Eric G. Suchanek, PhD
# =============================================================================

set -eo pipefail

# -- Parse arguments ----------------------------------------------------------
PROVIDERS_ARG="all"
PERSON=""
HOOKS_MODE="global"
FORCE_FLAG=""
SKIP_INIT=""
GLOBAL_MCP=""
DRY_RUN=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --providers)   PROVIDERS_ARG="${2:-all}"; shift 2 ;;
        --providers=*) PROVIDERS_ARG="${1#*=}";   shift   ;;
        --person)      PERSON="${2:-}";           shift 2 ;;
        --person=*)    PERSON="${1#*=}";          shift   ;;
        --hooks)       HOOKS_MODE="${2:-global}"; shift 2 ;;
        --hooks=*)     HOOKS_MODE="${1#*=}";      shift   ;;
        --force)       FORCE_FLAG="1";            shift   ;;
        --skip-init)   SKIP_INIT="1";             shift   ;;
        --global-mcp)  GLOBAL_MCP="1";            shift   ;;
        --dry-run)     DRY_RUN="1";               shift   ;;
        *)
            echo "Unknown flag: $1"
            echo "Usage: $0 [--providers all|claude,kilo,copilot,cline] [--person ID]"
            echo "          [--hooks global|claude|none] [--force] [--skip-init]"
            echo "          [--global-mcp] [--dry-run]"
            exit 1
            ;;
    esac
done

case "$HOOKS_MODE" in
    global|claude|none) ;;
    *)
        echo "Unknown --hooks mode: $HOOKS_MODE  (valid: global, claude, none)"
        exit 1
        ;;
esac

[ -z "$PERSON" ] && PERSON="$(id -un)"

# Run a command, or in dry-run mode just print what would be executed.
_exec() {
    if [ -n "$DRY_RUN" ]; then
        echo "  [dry-run] $*"
    else
        "$@"
    fi
}

# Normalise providers to a set of boolean flags
DO_CLAUDE=0; DO_KILO=0; DO_COPILOT=0; DO_CLINE=0

_enable_provider() {
    case "$1" in
        all)     DO_CLAUDE=1; DO_KILO=1; DO_COPILOT=1; DO_CLINE=1 ;;
        claude)  DO_CLAUDE=1  ;;
        kilo)    DO_KILO=1    ;;
        copilot) DO_COPILOT=1 ;;
        cline)   DO_CLINE=1   ;;
        *)
            echo "Unknown provider: $1  (valid: all, claude, kilo, copilot, cline)"
            exit 1
            ;;
    esac
}

IFS=',' read -ra _PLIST <<< "$PROVIDERS_ARG"
for _p in "${_PLIST[@]}"; do
    _enable_provider "$(echo "$_p" | tr -d ' ')"
done

REPO="Flux-Frontiers/agent_kg"
BRANCH="main"
RAW_BASE="https://raw.githubusercontent.com/${REPO}/${BRANCH}"

# Install to Claude Code, Kilo Code, and other agent skill directories
SKILL_DIRS=(
    "${HOME}/.claude/skills/agent-kg"
    "${HOME}/.kilocode/skills/agent-kg"
    "${HOME}/.agents/skills/agent-kg"
)

# Global Claude Code command files to install to ~/.claude/commands/.
# AgentKG-specific commands only -- changelog-commit and release are fleet-wide
# and already live in ~/.claude/commands.
CLAUDE_COMMAND_FILES=(
    "agentkg.md"
)

# -- Detect if we are running from inside the repo ----------------------------
# BASH_SOURCE[0] is unbound when piped via curl | bash.
# Use ${BASH_SOURCE:-} (no array index), which is safe even when unset.
_BASH_SOURCE="${BASH_SOURCE:-}"
if [ -n "$_BASH_SOURCE" ] && [ "$_BASH_SOURCE" != "bash" ]; then
    SCRIPT_DIR="$(cd "$(dirname "$_BASH_SOURCE")" && pwd)"
    REPO_ROOT="$(dirname "$SCRIPT_DIR")"
else
    # Running via curl | bash -- no local clone available
    SCRIPT_DIR=""
    REPO_ROOT=""
fi
LOCAL_SKILL="${REPO_ROOT:+${REPO_ROOT}/.claude/skills/agent-kg/SKILL.md}"

# The target repo is where the user ran the script from (CWD).
TARGET_REPO="${PWD}"
GRAPH_DB="${TARGET_REPO}/.agentkg/graph.sqlite"
VECTORS_DB="${TARGET_REPO}/.agentkg/vectors.sqlite"
PROFILE_DIR="${HOME}/.kgrag/profiles/${PERSON}"

echo "==================================================="
echo "         AgentKG Integration Installer"
echo "==================================================="
echo ""
[ -n "$DRY_RUN" ] && echo "  *** DRY RUN -- no changes will be made ***"
echo "  Target repo: ${TARGET_REPO}"
echo "  Person ID:   ${PERSON}"
echo "  Hooks:       ${HOOKS_MODE}"
_PNAMES=""
[ "$DO_CLAUDE"  = "1" ] && _PNAMES="${_PNAMES} claude"
[ "$DO_KILO"    = "1" ] && _PNAMES="${_PNAMES} kilo"
[ "$DO_COPILOT" = "1" ] && _PNAMES="${_PNAMES} copilot"
[ "$DO_CLINE"   = "1" ] && _PNAMES="${_PNAMES} cline"
echo "  Providers:  ${_PNAMES}"
echo ""

# -- Step 1: Install skill files to agent directories -------------------------
echo "-- Step 1: Installing skill files -----------------"
echo ""

for SKILL_DIR in "${SKILL_DIRS[@]}"; do
    _exec mkdir -p "$SKILL_DIR"

    if [ -f "$LOCAL_SKILL" ]; then
        if [ "${FIRST_RUN:-1}" = "1" ]; then
            echo "-> Local repo detected at: $REPO_ROOT"
            echo "   Copying skill files from local clone..."
            FIRST_RUN=0
        fi
        _exec cp "$LOCAL_SKILL" "${SKILL_DIR}/SKILL.md"
        # Copy the references/ tree if this version of the skill ships one.
        if [ -d "${REPO_ROOT}/.claude/skills/agent-kg/references" ]; then
            _exec mkdir -p "${SKILL_DIR}/references"
            _exec cp -R "${REPO_ROOT}/.claude/skills/agent-kg/references/." \
                        "${SKILL_DIR}/references/"
        fi
    else
        if [ "${FIRST_RUN:-1}" = "1" ]; then
            echo "-> No local clone detected. Downloading from GitHub..."
            FIRST_RUN=0
        fi
        if [ -n "$DRY_RUN" ]; then
            echo "  [dry-run] would download ${RAW_BASE}/.claude/skills/agent-kg/SKILL.md -> ${SKILL_DIR}/SKILL.md"
        elif command -v curl &>/dev/null; then
            curl -fsSL "${RAW_BASE}/.claude/skills/agent-kg/SKILL.md" -o "${SKILL_DIR}/SKILL.md"
        elif command -v wget &>/dev/null; then
            wget -q "${RAW_BASE}/.claude/skills/agent-kg/SKILL.md" -O "${SKILL_DIR}/SKILL.md"
        else
            echo "ERROR: Neither curl nor wget found. Install one and retry."
            exit 1
        fi
    fi

    # Verify (skip in dry-run -- files may not exist yet)
    if [ -z "$DRY_RUN" ] && [ ! -s "${SKILL_DIR}/SKILL.md" ]; then
        echo "ERROR: Installation failed for ${SKILL_DIR}"
        exit 1
    fi

    echo "  [ok] ${SKILL_DIR}/SKILL.md"
done

# -- Step 2: Install Claude Code commands to ~/.claude/commands/ --------------
echo ""
echo "-- Step 2: Installing Claude Code commands --------"
echo ""

CLAUDE_CMD_DIR="${HOME}/.claude/commands"
_exec mkdir -p "$CLAUDE_CMD_DIR"

for _CMD_FILE in "${CLAUDE_COMMAND_FILES[@]}"; do
    _DST="${CLAUDE_CMD_DIR}/${_CMD_FILE}"
    _LOCAL_CMD="${REPO_ROOT:+${REPO_ROOT}/.claude/commands/${_CMD_FILE}}"

    if [ -n "$_LOCAL_CMD" ] && [ -f "$_LOCAL_CMD" ]; then
        _exec cp "$_LOCAL_CMD" "$_DST"
        echo "  [ok] Copied from local repo -> ${_DST}"
    else
        if [ -n "$DRY_RUN" ]; then
            echo "  [dry-run] would download ${RAW_BASE}/.claude/commands/${_CMD_FILE} -> ${_DST}"
        elif command -v curl &>/dev/null; then
            curl -fsSL "${RAW_BASE}/.claude/commands/${_CMD_FILE}" -o "$_DST"
            echo "  [ok] Downloaded -> ${_DST}"
        elif command -v wget &>/dev/null; then
            wget -q "${RAW_BASE}/.claude/commands/${_CMD_FILE}" -O "$_DST"
            echo "  [ok] Downloaded -> ${_DST}"
        else
            echo "  [warn] Neither curl nor wget found -- skipping ${_CMD_FILE}"
        fi
    fi
done

# -- Step 3: Install Cline slash command into the target repo -----------------
echo ""
echo "-- Step 3: Installing Cline slash command ---------"
echo ""

if [ "$DO_CLINE" = "1" ]; then
    CLINE_CMD_DIR="${TARGET_REPO}/.claude/commands"
    CLINE_CMD_FILE="${CLINE_CMD_DIR}/agentkg.md"
    _LOCAL_CMD="${REPO_ROOT:+${REPO_ROOT}/.claude/commands/agentkg.md}"

    _exec mkdir -p "$CLINE_CMD_DIR"

    if [ -f "$CLINE_CMD_FILE" ] && [ -z "$FORCE_FLAG" ]; then
        echo "  [ok] ${CLINE_CMD_FILE} already exists -- skipping (--force to overwrite)"
    elif [ -n "$_LOCAL_CMD" ] && [ -f "$_LOCAL_CMD" ]; then
        _exec cp "$_LOCAL_CMD" "$CLINE_CMD_FILE"
        echo "  [ok] Copied from local repo -> ${CLINE_CMD_FILE}"
    else
        if [ -n "$DRY_RUN" ]; then
            echo "  [dry-run] would download ${RAW_BASE}/.claude/commands/agentkg.md -> ${CLINE_CMD_FILE}"
        elif command -v curl &>/dev/null; then
            curl -fsSL "${RAW_BASE}/.claude/commands/agentkg.md" -o "$CLINE_CMD_FILE"
            echo "  [ok] Downloaded -> ${CLINE_CMD_FILE}"
        elif command -v wget &>/dev/null; then
            wget -q "${RAW_BASE}/.claude/commands/agentkg.md" -O "$CLINE_CMD_FILE"
            echo "  [ok] Downloaded -> ${CLINE_CMD_FILE}"
        else
            echo "  [warn] Neither curl nor wget found -- skipping Cline command install"
        fi
    fi
else
    echo "  -- Skipped (cline not selected)"
fi

# -- Step 4: Install agent-kg if not already present --------------------------
echo ""
echo "-- Step 4: Checking agent-kg installation ---------"
echo ""

# Resolve the latest GitHub release wheel URL (requires curl or wget + python3).
# Returns an empty string if no release exists yet.
_latest_wheel_url() {
    local _api="https://api.github.com/repos/${REPO}/releases/latest"
    local _json=""
    if command -v curl &>/dev/null; then
        _json="$(curl -fsSL "$_api" 2>/dev/null || true)"
    elif command -v wget &>/dev/null; then
        _json="$(wget -qO- "$_api" 2>/dev/null || true)"
    fi
    [ -z "$_json" ] && return
    python3 - <<PYEOF
import json
try:
    data = json.loads('''$_json''')
    whl = next((a["browser_download_url"] for a in data.get("assets", [])
                if a["name"].endswith(".whl")), None)
    if whl:
        print(whl)
except Exception:
    pass
PYEOF
}

AGENTKG_BIN=""

# Probe for an existing installation in order of priority:
#   1. Local .venv in the target repo (Poetry project that added agent-kg)
#   2. Local .venv in the agent_kg source repo (running the script from the repo)
#   3. Importable in the active Python environment
#   4. On $PATH
if [ -x "${TARGET_REPO}/.venv/bin/agentkg" ]; then
    AGENTKG_BIN="${TARGET_REPO}/.venv/bin/agentkg"
    echo "  [ok] Found agentkg in local venv: ${AGENTKG_BIN}"
elif [ -n "${REPO_ROOT}" ] && [ -x "${REPO_ROOT}/.venv/bin/agentkg" ]; then
    AGENTKG_BIN="${REPO_ROOT}/.venv/bin/agentkg"
    echo "  [ok] Found agentkg in source venv: ${AGENTKG_BIN}"
elif python3 -c "import agent_kg" &>/dev/null 2>&1; then
    AGENTKG_BIN="$(python3 -c "import sysconfig; print(sysconfig.get_path('scripts'))")/agentkg"
    [ -x "$AGENTKG_BIN" ] || AGENTKG_BIN="agentkg"   # fallback to PATH entry
    echo "  [ok] Found agent_kg in Python environment -- agentkg: ${AGENTKG_BIN}"
elif command -v agentkg &>/dev/null; then
    AGENTKG_BIN="$(command -v agentkg)"
    echo "  [ok] Found agentkg on PATH: ${AGENTKG_BIN}"
fi

if [ -z "$AGENTKG_BIN" ]; then
    if [ -n "$DRY_RUN" ]; then
        echo "  [dry-run] would install agent-kg from GitHub (wheel or git source)"
        AGENTKG_BIN="agentkg"
    else
        WHEEL_URL="$(_latest_wheel_url || true)"
        if [ -n "$WHEEL_URL" ]; then
            echo "  -> Installing agent-kg from GitHub release wheel..."
            pip install --quiet "agent-kg @ ${WHEEL_URL}"
        else
            echo "  -> Installing agent-kg from GitHub source..."
            pip install --quiet "agent-kg @ git+https://github.com/${REPO}.git"
        fi
        AGENTKG_BIN="$(command -v agentkg 2>/dev/null || true)"
        if [ -n "$AGENTKG_BIN" ]; then
            echo "  [ok] Installed agent-kg -- agentkg at: ${AGENTKG_BIN}"
        else
            echo "  [fail] Installation failed. Install manually:"
            echo "      pip install 'agent-kg @ git+https://github.com/${REPO}.git'"
            exit 1
        fi
    fi
fi

# The interpreter that owns AGENTKG_BIN -- used for `python -m spacy download`
# so the model lands in the same environment as agent_kg itself.
_PY_BIN="$(dirname "$AGENTKG_BIN")/python"
[ -x "$_PY_BIN" ] || _PY_BIN="python3"

# -- Step 5: Initialize the embedding model and profile directory -------------
# `agentkg init` creates ~/.kgrag/profiles/<person>/ and downloads the
# sentence-transformers model into the shared kg_utils cache, so the first
# ingest does not stall on a download. It is idempotent: an already-cached
# model is detected and reused.
echo ""
echo "-- Step 5: Initializing model and profile ---------"
echo ""

if [ -n "$SKIP_INIT" ]; then
    echo "  -- Skipped (--skip-init)"
elif [ -n "$DRY_RUN" ]; then
    echo "  [dry-run] would run: agentkg init --person ${PERSON}"
    echo "  [dry-run] would run: python -m spacy download en_core_web_sm"
else
    echo "  -> Downloading the embedding model (first run may take a minute)..."
    "$AGENTKG_BIN" init --person "$PERSON"

    # spaCy is a hard dependency, but its model ships separately. Without it
    # topic and entity extraction silently degrades to regex heuristics, so
    # install it here -- but never fail the whole install over it.
    #
    # `spacy download` is tried first but cannot be trusted on its own: when a
    # uv-managed environment is the target, spaCy shells out to `uv pip`, which
    # resolves against the *active* environment rather than "$_PY_BIN" and can
    # report success having installed the model somewhere else entirely. So the
    # real test is a load, and the fallback pins the wheel directly.
    echo ""
    echo "  -> Ensuring the spaCy en_core_web_sm model is present..."
    _SPACY_WHEEL="https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
    _spacy_ok() { "$_PY_BIN" -c "import spacy; spacy.load('en_core_web_sm')" &>/dev/null; }

    if _spacy_ok; then
        echo "  [ok] en_core_web_sm already installed"
    else
        "$_PY_BIN" -m spacy download en_core_web_sm &>/dev/null || true
        if ! _spacy_ok; then
            # Install the wheel straight into the interpreter that owns agentkg.
            if command -v uv &>/dev/null; then
                uv pip install --python "$_PY_BIN" "en_core_web_sm @ ${_SPACY_WHEEL}" &>/dev/null || true
            else
                "$_PY_BIN" -m pip install --quiet "en_core_web_sm @ ${_SPACY_WHEEL}" || true
            fi
        fi
        if _spacy_ok; then
            echo "  [ok] en_core_web_sm installed"
        else
            echo "  [warn] Could not install en_core_web_sm -- extraction will fall"
            echo "         back to keyword/regex heuristics. Install it later with:"
            echo "           ${_PY_BIN} -m pip install 'en_core_web_sm @ ${_SPACY_WHEEL}'"
        fi
    fi
fi

# -- Step 6: Deploy the auto-ingest hooks -------------------------------------
# Deploys the three shell scripts to ~/.agentkg/hooks/ and merges the
# UserPromptSubmit / Stop / PreCompact entries into the target settings.json.
# Without these the conversation graph never gets populated.
echo ""
echo "-- Step 6: Installing auto-ingest hooks -----------"
echo ""

if [ "$HOOKS_MODE" = "none" ]; then
    echo "  -- Skipped (--hooks none)"
else
    _HOOK_ARGS=("install-hooks" "--repo" "$TARGET_REPO" "--${HOOKS_MODE}")
    [ -n "$FORCE_FLAG" ] && _HOOK_ARGS+=("--force")

    if [ -n "$DRY_RUN" ]; then
        echo "  [dry-run] would run: agentkg ${_HOOK_ARGS[*]}"
    else
        "$AGENTKG_BIN" "${_HOOK_ARGS[@]}"
    fi
fi

# -- Step 7: Write .mcp.json (Claude Code + Kilo Code) ------------------------
# The AgentKG MCP server takes no --repo flag; it is scoped entirely through
# the AGENTKG_REPO and AGENTKG_PERSON environment variables.
echo ""
echo "-- Step 7: Configuring .mcp.json (Claude Code + Kilo Code) --"
echo ""

MCP_JSON="${TARGET_REPO}/.mcp.json"

if [ "$DO_KILO" = "0" ] && [ "$DO_CLAUDE" = "0" ]; then
    echo "  -- Skipped (neither claude nor kilo selected)"
elif [ -n "$DRY_RUN" ]; then
    echo "  [dry-run] would upsert the agent-kg entry in ${MCP_JSON}"
else
    _exec mkdir -p "$(dirname "$MCP_JSON")"
    python3 - "$MCP_JSON" "$TARGET_REPO" "$AGENTKG_BIN" "$PERSON" <<'PYEOF'
import json, os, sys

mcp_json, target_repo, agentkg_bin, person = sys.argv[1:5]

data = {}
if os.path.exists(mcp_json):
    with open(mcp_json) as f:
        data = json.load(f)

data.setdefault("mcpServers", {})["agent-kg"] = {
    "command": agentkg_bin,
    "args": ["mcp"],
    "env": {"AGENTKG_REPO": target_repo, "AGENTKG_PERSON": person},
}

with open(mcp_json, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PYEOF
    echo "  [ok] Upserted the agent-kg entry in ${MCP_JSON}"
fi

# -- Step 7b: Register agent-kg as a user-scope MCP server --------------------
# ~/.claude.json is Claude Code's user-scope config. An entry here serves every
# repo, so AGENTKG_REPO is deliberately left unset: the server then defaults to
# "." and resolves against each project's cwd. AGENTKG_PERSON must be set, as
# the server defaults it to "default" rather than the OS username and would
# otherwise read an empty profile.
echo ""
echo "-- Step 7b: Registering the user-scope MCP server --"
echo ""

CLAUDE_USER_JSON="${HOME}/.claude.json"

if [ -z "$GLOBAL_MCP" ]; then
    echo "  -- Skipped (pass --global-mcp to register agent-kg for all repos)"
elif [ ! -f "$CLAUDE_USER_JSON" ]; then
    echo "  [warn] ${CLAUDE_USER_JSON} not found -- is Claude Code installed?"
elif [ -n "$DRY_RUN" ]; then
    echo "  [dry-run] would upsert the agent-kg entry in ${CLAUDE_USER_JSON}"
else
    # A user-scope entry must not point into a single repo's .venv, and MCP
    # servers do not reliably inherit the login shell PATH, so prefer the
    # absolute path to the fleet-wide uv tool install over a bare "agentkg".
    _GLOBAL_BIN="${HOME}/.local/bin/agentkg"
    [ -x "$_GLOBAL_BIN" ] || _GLOBAL_BIN="$AGENTKG_BIN"

    # This file also holds per-project history, so back it up before touching it.
    _exec cp "$CLAUDE_USER_JSON" "${CLAUDE_USER_JSON}.bak"
    python3 - "$CLAUDE_USER_JSON" "$PERSON" "$_GLOBAL_BIN" <<'PYEOF'
import json, sys

claude_json, person, global_bin = sys.argv[1:4]

with open(claude_json) as f:
    data = json.load(f)

data.setdefault("mcpServers", {})["agent-kg"] = {
    "command": global_bin,
    "args": ["mcp"],
    "env": {"AGENTKG_PERSON": person},
}

with open(claude_json, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PYEOF
    echo "  [ok] Upserted the agent-kg entry in ${CLAUDE_USER_JSON}"
    echo "       (backup: ${CLAUDE_USER_JSON}.bak)"
fi

# -- Step 8: Write .vscode/mcp.json (GitHub Copilot) --------------------------
echo ""
echo "-- Step 8: Configuring .vscode/mcp.json (GitHub Copilot) --"
echo ""

VSCODE_DIR="${TARGET_REPO}/.vscode"
VSCODE_MCP="${VSCODE_DIR}/mcp.json"

if [ "$DO_COPILOT" = "0" ]; then
    echo "  -- Skipped (copilot not selected)"
elif [ -n "$DRY_RUN" ]; then
    echo "  [dry-run] would upsert the agent-kg entry in ${VSCODE_MCP}"
else
    _exec mkdir -p "$VSCODE_DIR"
    python3 - "$VSCODE_MCP" "$TARGET_REPO" "$AGENTKG_BIN" "$PERSON" <<'PYEOF'
import json, os, sys

vscode_mcp, target_repo, agentkg_bin, person = sys.argv[1:5]

data = {}
if os.path.exists(vscode_mcp):
    with open(vscode_mcp) as f:
        data = json.load(f)

data.setdefault("servers", {})["agent-kg"] = {
    "type": "stdio",
    "command": agentkg_bin,
    "args": ["mcp"],
    "env": {"AGENTKG_REPO": target_repo, "AGENTKG_PERSON": person},
}

with open(vscode_mcp, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PYEOF
    echo "  [ok] Upserted the agent-kg entry in ${VSCODE_MCP}"
fi

# -- Step 9: Write Cline MCP settings -----------------------------------------
echo ""
echo "-- Step 9: Configuring Cline MCP settings ---------"
echo ""

if [ "$DO_CLINE" = "1" ]; then
    CLINE_SETTINGS=""
    _CLINE_MAC="${HOME}/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
    _CLINE_LINUX="${HOME}/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
    if [ -f "$_CLINE_MAC" ]; then
        CLINE_SETTINGS="$_CLINE_MAC"
    elif [ -f "$_CLINE_LINUX" ]; then
        CLINE_SETTINGS="$_CLINE_LINUX"
    fi

    if [ -z "$CLINE_SETTINGS" ]; then
        echo "  [warn] cline_mcp_settings.json not found -- is Cline installed?"
        echo "         Expected: ${_CLINE_MAC}"
    elif [ -n "$DRY_RUN" ]; then
        echo "  [dry-run] would upsert agent-kg-$(basename "$TARGET_REPO") in ${CLINE_SETTINGS}"
    else
        python3 - "$CLINE_SETTINGS" "$TARGET_REPO" "$(basename "$TARGET_REPO")" \
                 "$AGENTKG_BIN" "$PERSON" <<'PYEOF'
import json, sys

cline_settings, target_repo, repo_name, agentkg_bin, person = sys.argv[1:6]
server_key = f"agent-kg-{repo_name}"

with open(cline_settings) as f:
    data = json.load(f)

data.setdefault("mcpServers", {})[server_key] = {
    "command": agentkg_bin,
    "args": ["mcp"],
    "env": {"AGENTKG_REPO": target_repo, "AGENTKG_PERSON": person},
}

with open(cline_settings, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
print(f"  [ok] Upserted {server_key} in {cline_settings}")
PYEOF
    fi
else
    echo "  -- Skipped (cline not selected)"
fi

# -- Done ---------------------------------------------------------------------
echo ""
if [ -n "$DRY_RUN" ]; then
    echo "==================================================="
    echo "   AgentKG dry-run complete -- no changes made."
    echo "==================================================="
else
    echo "==================================================="
    echo "   AgentKG installed and configured successfully!"
    echo "==================================================="
fi
echo ""
echo "  Repo:     ${TARGET_REPO}"
echo "  Graph:    ${GRAPH_DB}"
echo "  Vectors:  ${VECTORS_DB}"
echo "  Profile:  ${PROFILE_DIR}"
echo ""
echo "  Claude command installed:"
echo "    [ok] ~/.claude/commands/agentkg.md"
echo ""
echo "  Providers configured:"
( [ "$DO_CLAUDE" = "1" ] || [ "$DO_KILO" = "1" ] ) && echo "    [ok] Claude Code + Kilo Code  (.mcp.json)"
[ "$DO_COPILOT" = "1" ] && echo "    [ok] GitHub Copilot           (.vscode/mcp.json)"
[ "$DO_CLINE"   = "1" ] && echo "    [ok] Cline                    (.claude/commands/agentkg.md + cline_mcp_settings.json)"
echo ""
echo "  Next steps:"
echo "    1. Run the onboarding interview to populate your profile:"
echo "         ${AGENTKG_BIN} onboard --person ${PERSON}"
echo "    2. Reload VS Code to activate the MCP servers:"
echo "         Cmd+Shift+P -> 'Developer: Reload Window'"
echo ""
echo "  The conversation graph fills in as you converse -- there is no build"
echo "  step. Check it any time with:"
echo "    ${AGENTKG_BIN} stats --repo ${TARGET_REPO}"
echo ""
[ "$DO_COPILOT" = "1" ] && echo "  GitHub Copilot: VS Code will prompt you to trust the agent-kg server on first use."
echo ""
echo "  Full docs: https://github.com/Flux-Frontiers/agent_kg/blob/main/README.md"
