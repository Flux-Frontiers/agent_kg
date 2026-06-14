# PyCodeKG — Cline Rules Template

Copy this file to `.clinerules` in the root of any repo that has PyCodeKG configured.
It gives Cline automatic context about the available MCP tools and how to use them.

---

## How to use this file

```bash
cp /path/to/pycode_kg/.claude/skills/pycodekg/clinerules.md /path/to/myrepo/.clinerules
```

Or add the content below to an existing `.clinerules` file in your repo.

---

## Content to put in `.clinerules`

```
## PyCodeKG MCP Tools

This project has a PyCodeKG MCP server configured (`pycodekg`). Use these tools to
explore the codebase structure before writing or modifying code.

### Available tools

- **graph_stats()** — Get codebase size and shape (node/edge counts by type).
  Use this first to orient yourself in a new session.

- **query_codebase(q)** — Hybrid semantic + structural search. Returns nodes
  (modules, classes, functions, methods) and their relationships. Use for:
  - Finding where something is implemented
  - Understanding call graphs and dependencies
  - Exploring module structure
  Supports precision/diversity controls: `min_score` and `max_per_module`.

- **pack_snippets(q)** — Like query_codebase but returns actual source code
  snippets. Use when you need to read the implementation, not just the structure.
  Supports `min_score` and `max_per_module` for tighter packs.

- **explain(node_id)** — Natural-language explanation of a node: kind, location,
  docstring, top callers, callees, and role assessment. Use before pack_snippets
  to orient yourself on a specific function or class.

- **analyze_repo()** — Full architectural analysis: complexity hotspots, high
  fan-out functions, module coupling, circular dependencies, docstring coverage,
  orphaned code, and recommendations. Use for health checks.

- **get_node(node_id, include_edges)** — Look up a single node by its ID (e.g.
  `fn:src/mymodule.py:my_function`). Pass `include_edges=True` to get outgoing
  edges and incoming callers in one call — avoiding a separate `callers()` call.

- **callers(node_id)** — Find all callers of a function, including cross-module
  callers resolved through import stubs. Use for impact analysis before changing
  a function. Import-aware filtering reduces same-name false positives.

- **snapshot_list(limit)** — List saved codebase metric snapshots newest-first.
  Returns snapshot key (tree hash), branch, timestamp, node/edge counts, and deltas.

- **snapshot_show(key)** — Full metrics for a specific snapshot key (tree hash), or
  `"latest"` for the most recent snapshot.

- **snapshot_diff(key_a, key_b)** — Compare two snapshots side-by-side.
  Returns delta for nodes, edges, docstring coverage, and critical issues.

### When to use PyCodeKG

- **Start of session:** Call `graph_stats()` to understand the codebase size.
- **Before editing:** Call `query_codebase("relevant topic")` to find related code.
- **Before implementing:** Call `pack_snippets("feature area")` to read existing patterns.
- **Tracing calls:** Use `query_codebase` with function/class names to find callers/callees.

### Rebuilding the index

**Full rebuild** (always wipes — use after renames, deletions, or large refactors):

```bash
pycodekg build --repo .
```

**Incremental upsert** (no wipe — safe for minor edits and new files only):

```bash
pycodekg update --repo .
```

Or step by step (with explicit wipe control):

```bash
pycodekg build-sqlite  --repo . --wipe
pycodekg build-lancedb --repo . --wipe
```

### Cline MCP config

Cline uses a global config file (not per-repo `.mcp.json`):
`~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

Add a named entry for each repo:
```json
{
  "mcpServers": {
    "pycodekg-REPONAME": {
      "command": "/absolute/path/to/venv/bin/pycodekg",
      "args": [
        "mcp",
        "--repo",    "/absolute/path/to/repo",
        "--db",      "/absolute/path/to/repo/.pycodekg/graph.sqlite"
      ]
    }
  }
}
```

Use a unique name per repo (e.g. `pycodekg-myproject`) to avoid conflicts.
Enable/disable servers via the Cline MCP panel as you switch projects.
```
