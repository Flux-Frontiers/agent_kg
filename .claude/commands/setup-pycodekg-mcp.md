# PyCodeKG MCP Setup & Verification

Set up the PyCodeKG MCP server for a target repository and configure it for use with Claude Code and/or Claude Desktop. Execute the following steps in sequence.

## Command Argument Handling

This command accepts an optional repository path argument:

**Usage:**
- `/setup-pycodekg-mcp` — Interactive mode; prompts for the target repository path
- `/setup-pycodekg-mcp /path/to/repo` — Set up PyCodeKG MCP for the specified repository

---

## Step 0: Resolve the Target Repository

1. If a path argument was provided, use it as `REPO_ROOT`.
2. If no argument was provided, ask the user:
   > "Which repository do you want to index with PyCodeKG? Please provide the absolute path."
3. Verify the path exists and contains at least one `.py` file:
   ```bash
   find "$REPO_ROOT" -name "*.py" -not -path "*/.venv/*" -not -path "*/__pycache__/*" | head -5
   ```
4. If no Python files are found, stop and report the issue.

All artifact paths default relative to `REPO_ROOT`:
- `DB_PATH` → `$REPO_ROOT/.pycodekg/graph.sqlite`
- `LANCEDB_DIR` → `$REPO_ROOT/.pycodekg/lancedb`

Do not pass `--db` or `--lancedb` flags — the commands default to `.pycodekg/` automatically.

---

## Step 1: Verify PyCodeKG Installation

Prefer `poetry run` for all CLI calls. If `poetry run` fails with a **Python version
conflict** (e.g. "Current Python version is not allowed by the project"), fall back to
the `.venv` binaries directly — they are already built against the correct interpreter.

Establish the runner upfront:

```bash
# Try poetry run first
poetry run pycodekg --version 2>&1
```

If that prints a version, set `RUNNER="poetry run"`. If it errors with a Python version
conflict, set `RUNNER=""` and use `.venv/bin/pycodekg` directly for all subsequent calls:

```bash
# Fallback — use .venv binary directly
$REPO_ROOT/.venv/bin/pycodekg --version
```

Use whichever runner succeeds for all remaining steps. Document which runner was used in
the final report.

1. Check that the `pycodekg` entry point resolves:
   ```bash
   $RUNNER pycodekg --version   # or $REPO_ROOT/.venv/bin/pycodekg --version
   ```
2. If not found, check whether the package is installed:
   ```bash
   $RUNNER python -m pip show pycode-kg 2>/dev/null   # or .venv/bin/pip show pycode-kg
   ```
3. If missing, instruct the user to install it:
   ```bash
   poetry add "pycode-kg @ git+https://github.com/Flux-Frontiers/pycode_kg.git"
   ```
   Then stop — the user must install before continuing.

4. Confirm the `mcp` Python package is importable (it is a required dependency, not an optional extra):
   ```bash
   $RUNNER python -c "import mcp; print('mcp OK')"
   ```
   If this fails, run `poetry install` and retry. There is no `[mcp]` extra to add.

5. Check the PyCodeKG version:
   ```bash
   $RUNNER python -c "import pycode_kg; print(pycode_kg.__version__)"
   ```

---

## Step 2: Build the Knowledge Graph (SQLite)

1. Check whether `DB_PATH` already exists:
   ```bash
   ls -lh "$REPO_ROOT/.pycodekg/graph.sqlite" 2>/dev/null
   ```
2. If it exists, ask the user:
   > "A knowledge graph already exists at `$REPO_ROOT/.pycodekg/graph.sqlite`. Rebuild it from scratch (wipe), or keep the existing graph?"
   - **Wipe**: proceed with `--wipe`
   - **Keep**: skip to Step 3

3. Run the static analysis build:
   ```bash
   $RUNNER pycodekg build-sqlite --repo "$REPO_ROOT" --wipe
   ```
4. Verify the database was created and is non-empty:
   ```bash
   sqlite3 "$REPO_ROOT/.pycodekg/graph.sqlite" "SELECT COUNT(*) FROM nodes; SELECT COUNT(*) FROM edges;"
   ```
5. Report the node and edge counts. If both are zero, warn the user — the repo may have no indexable Python files.

---

## Step 3: Build the Semantic Index (LanceDB)

1. Check whether `LANCEDB_DIR` already exists and is non-empty:
   ```bash
   ls "$REPO_ROOT/.pycodekg/lancedb" 2>/dev/null
   ```
2. If it exists and the user chose to keep the SQLite graph (Step 2), ask:
   > "A vector index already exists at `$REPO_ROOT/.pycodekg/lancedb`. Rebuild it?"
   - **Yes**: proceed with `--wipe`
   - **No**: skip to Step 4

3. Run the embedding build:
   ```bash
   $RUNNER pycodekg build-lancedb --repo "$REPO_ROOT" --wipe
   ```
   Note: use `--sqlite` (not `--db`) if specifying a non-default SQLite path.

4. Confirm the LanceDB directory was populated:
   ```bash
   ls -lh "$REPO_ROOT/.pycodekg/lancedb"
   ```
5. Report the number of indexed vectors (shown in the command output).

---

## Step 4: Smoke-Test the Query Pipeline

Run a quick end-to-end test to confirm the full pipeline works before configuring any agent:

1. Run a graph stats check:
   ```bash
   $RUNNER python -c "
   from pycode_kg import PyCodeKG
   kg = PyCodeKG(repo_root='$REPO_ROOT')
   import json; print(json.dumps(kg.stats(), indent=2))
   "
   ```

2. Run a sample query (must be run from `$REPO_ROOT` so `.pycodekg/` defaults resolve):
   ```bash
   cd "$REPO_ROOT" && $RUNNER pycodekg query "module structure"
   ```

3. If either command errors, diagnose and report the issue before proceeding.

---

## Step 5: Configure MCP Clients

Configure the per-repo `.mcp.json`, Claude Desktop (`claude_desktop_config.json`) if applicable, and install the PyCodeKG skill globally.

The PyCodeKG MCP server is started with `pycodekg mcp --repo <REPO_ROOT>`. Always use absolute paths.

### MCP config by agent — quick reference

| Agent | Config file | Per-repo? | Key name |
|-------|-------------|-----------|----------|
| **GitHub Copilot** | `.vscode/mcp.json` | ✅ Yes | `"servers"` |
| **Kilo Code** | `.mcp.json` (project root) | ✅ Yes | `"mcpServers"` |
| **Claude Code** | `.mcp.json` (project root) | ✅ Yes | `"mcpServers"` |
| **Cline** | `~/...saoudrizwan.claude-dev/settings/cline_mcp_settings.json` | ❌ Global only | `"mcpServers"` |
| **Claude Desktop** | `~/Library/Application Support/Claude/claude_desktop_config.json` | ❌ Global only | `"mcpServers"` |

> ⚠️ **Do NOT add `pycodekg` to any global settings file.**
> Global files are shared across all windows — hardcoded paths point every window to the same repo.
> Use per-repo config files instead.

> ⚠️ **Cline does NOT support per-repo config.**
> Options: use Kilo Code instead, or add a uniquely-named entry per repo in `cline_mcp_settings.json` and toggle via the Cline MCP panel.

### 5a: GitHub Copilot (.vscode/mcp.json)

Uses `"servers"` key and requires `"type": "stdio"`.

1. Check if `.vscode/mcp.json` exists in `$REPO_ROOT`:
   ```bash
   cat "$REPO_ROOT/.vscode/mcp.json" 2>/dev/null
   ```

2. If it exists, check for an existing `pycodekg` entry under `servers`.
   - If one exists, ask the user to replace or keep it.

3. The `pycodekg` entry to add/update:
   ```json
   {
     "servers": {
       "pycodekg": {
         "type": "stdio",
         "command": "<venv_path>/bin/pycodekg",
         "args": ["mcp", "--repo", "<REPO_ROOT>"]
       }
     }
   }
   ```

4. Merge into the existing `servers` object — do not overwrite other entries.

5. After saving, VS Code will prompt you to trust the MCP server — click **Trust** to activate it.

### 5b: Kilo Code / Claude Code (.mcp.json)

1. Check if `.mcp.json` exists in `$REPO_ROOT`:
   ```bash
   cat "$REPO_ROOT/.mcp.json" 2>/dev/null
   ```

2. If it exists, check for an existing `pycodekg` entry under `mcpServers`.
   - If one exists, ask the user to replace or keep it.

3. Get the venv binary path:
   ```bash
   poetry env info --path
   # binary: <venv_path>/bin/pycodekg
   ```

4. The `pycodekg` entry to add/update:
   ```json
   "pycodekg": {
     "command": "<venv_path>/bin/pycodekg",
     "args": ["mcp", "--repo", "<REPO_ROOT>"]
   }
   ```

5. Merge into the existing `mcpServers` object — do not overwrite other entries.

6. **Verify the global settings file does NOT contain a `pycodekg` entry:**
   - Kilo Code global config: `~/Library/Application Support/Code/User/globalStorage/kilocode.kilo-code/settings/mcp_settings.json`
   - Claude Code global config: `~/.claude/settings.json`
   - If a `pycodekg` entry exists in either global file, remove it.

### 5c: Claude Desktop (claude_desktop_config.json)

Claude Desktop does not have Poetry on its PATH — use the absolute venv binary.

1. Config path:
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Linux**: `~/.config/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

2. Get the venv binary path:
   ```bash
   poetry env info --path
   # binary: <venv_path>/bin/pycodekg
   ```

3. The `pycodekg` entry to add/update:
   ```json
   "pycodekg": {
     "command": "<venv_path>/bin/pycodekg",
     "args": ["mcp", "--repo", "<REPO_ROOT>"]
   }
   ```

4. Merge into the existing `mcpServers` object — do not overwrite other entries.

### 5d: Install the PyCodeKG Skill (Global)

The PyCodeKG skill provides AI agents with expert knowledge about PyCodeKG installation and usage.

| Agent | Skill directory |
|-------|----------------|
| **Kilo Code** | `~/.kilocode/skills/pycodekg/` |
| **Claude Code** | `~/.claude/skills/pycodekg/` |

Run the install script (from the `pycode_kg` repo root):

```bash
bash scripts/install-skill.sh
```

Or manually copy from `.claude/skills/pycodekg/` to the target directories above.

Reload VS Code (`Cmd+Shift+P` → "Developer: Reload Window") for Kilo Code to pick up the new skill.

---

## Step 6: Final Report

Present a summary of everything that was done:

```
✓ PyCodeKG version:       <version>
✓ Runner used:          poetry run  OR  .venv/bin/pycodekg (fallback)
✓ Repository indexed:   <REPO_ROOT>
✓ SQLite graph:         <REPO_ROOT>/.pycodekg/graph.sqlite  (<N> nodes, <M> edges)
✓ LanceDB index:        <REPO_ROOT>/.pycodekg/lancedb  (<V> vectors)
✓ Smoke test:           passed
✓ Claude Code config:   <REPO_ROOT>/.mcp.json  (pycodekg entry)
✓ Claude Desktop config: <CONFIG_PATH>  (pycodekg entry)
✓ PyCodeKG skill:         ~/.claude/skills/pycodekg/  (installed/updated/skipped)

Restart Claude Code / Claude Desktop to activate the pycodekg MCP server.

Available tools once active:
  • graph_stats()          — codebase size and shape
  • query_codebase(q)      — semantic + structural exploration
  • pack_snippets(q)       — source-grounded code snippets
  • get_node(node_id)      — single node metadata + neighborhood
  • list_nodes(module_path, kind) — enumerate nodes in a module
  • callers(node_id)       — find all callers of a function
  • explain(node_id)       — natural-language node orientation
  • centrality(top)        — SIR PageRank structural ranking
  • analyze_repo()         — full architectural analysis

Suggested first query after restart:
  graph_stats()
```

---

## Important Rules

- **Do NOT modify source files** in the target repository.
- **Do NOT run `git commit`** or any destructive git operations.
- Use **absolute paths** everywhere — relative paths will break MCP clients.
- Prefer `poetry run` for CLI calls; fall back to `.venv/bin/pycodekg` if Poetry reports a Python version conflict.
- `mcp` is a **required main dependency** of PyCodeKG — there is no `[mcp]` extra to add.
- If any step fails, stop and report the error clearly before proceeding.
- If the user's repo is very large (>50k lines of Python), warn that the build and embedding steps may take several minutes.

| Error | Fix |
|-------|-----|
| `Current Python version is not allowed by the project` | Use `.venv/bin/pycodekg` directly instead of `poetry run pycodekg` |
| `pycodekg: command not found` | Run `poetry install`; if venv exists use `.venv/bin/pycodekg` |
| `error: the following arguments are required: --sqlite` | Use `--sqlite`, not `--db`, for `pycodekg build-lancedb` |
| `ModuleNotFoundError: No module named 'mcp'` | Run `poetry install` — `mcp` is a required dep, not an extra |
| `WARNING: SQLite database not found` | Run both build commands first |
| Empty query results | Run `pycodekg build-lancedb --repo "$REPO_ROOT" --wipe` |
| `pycodekg mcp` not appearing in Claude Code | Use absolute venv path in `.mcp.json`; restart Claude Code |

---

## Rebuilding After Code Changes

When the target codebase changes, the graph must be rebuilt:

```bash
# Rebuild both artifacts (idempotent — safe to re-run)
$RUNNER pycodekg build-sqlite  --repo "$REPO_ROOT" --wipe
$RUNNER pycodekg build-lancedb --repo "$REPO_ROOT" --wipe
```

The MCP client configs do not need to change — they point to the same file paths.
