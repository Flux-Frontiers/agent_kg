---
name: pycodekg
description: Expert knowledge for installing, configuring, and using the PyCodeKG MCP server — a hybrid semantic + structural knowledge graph for Python codebases. Use this skill when the user asks about: setting up PyCodeKG in a project, adding pycode-kg as a Poetry dependency, building the SQLite or LanceDB knowledge graph, configuring .mcp.json for Claude Code or Kilo Code, configuring .vscode/mcp.json for GitHub Copilot, configuring claude_desktop_config.json for Claude Desktop, configuring Cline MCP settings, using the pycodekg CLI (pycodekg build, pycodekg build-sqlite, pycodekg build-lancedb, pycodekg mcp, pycodekg query, pycodekg pack, pycodekg analyze, pycodekg centrality, pycodekg viz, pycodekg viz3d, pycodekg viz-timeline, pycodekg explain, pycodekg snapshot, pycodekg architecture, pycodekg download-model, pycodekg install-hooks), using the graph_stats / query_codebase / pack_snippets / get_node / list_nodes / callers / explain / centrality / bridge_centrality / framework_nodes / analyze_repo / rank_nodes / query_ranked / explain_rank / snapshot_list / snapshot_show / snapshot_diff MCP tools, or troubleshooting PyCodeKG errors.
---

# PyCodeKG Skill

> **Use PyCodeKG first — before grep, Glob, or file reads.**
>
> Grep and file search find text. PyCodeKG understands code. It knows what calls what, what inherits from what, which modules are imported where, and surfaces the most semantically relevant source snippets in a single query. One `pack_snippets` call replaces five rounds of grep-and-read and gives the agent real structural insight into the codebase — not just line matches.

PyCodeKG indexes Python repos into a hybrid knowledge graph (SQLite + LanceDB) and exposes it as MCP tools for AI agents.

## Installation (Poetry)

```bash
# With MCP server support
poetry add "pycode-kg[mcp] @ git+https://github.com/Flux-Frontiers/pycode_kg.git"
```

Adds to `pyproject.toml`:
```toml
pycode-kg = { git = "https://github.com/Flux-Frontiers/pycode_kg.git", extras = ["mcp"] }
```

## Build the Knowledge Graph

```bash
# Step 1 — SQLite graph
pycodekg build-sqlite --repo .

# Step 2 — LanceDB vector index
pycodekg build-lancedb --repo .
```

> **Common mistake:** `pycodekg build-lancedb` uses `--sqlite`, not `--db`, when specifying a non-default path.

Add `--wipe` to either command to rebuild from scratch.

## Rebuilding After Code Changes

The knowledge graph is a snapshot of the codebase at build time. It does **not** update automatically. Stale data causes misleading query results — especially after renames, deletions, or large refactors.

### When to rebuild

| Change | Command |
|---|---|
| Added / renamed / deleted functions, classes, or modules | `pycodekg build` (full wipe) |
| Large refactor touching many files | `pycodekg build` (full wipe) |
| Minor edits within existing functions | `pycodekg update` (incremental upsert) |
| New file added to the repo | `pycodekg update` (incremental upsert) |

> **Why `pycodekg build` always wipes:** Deleted or renamed nodes would otherwise remain as phantom entries. LanceDB upserts by node ID, so renamed nodes leave behind orphans. `pycodekg build` clears both stores unconditionally; use `pycodekg update` only when you're sure no nodes were deleted or renamed.

### Full rebuild

```bash
pycodekg build --repo .
```

### Incremental upsert (minor additions only)

```bash
pycodekg update --repo .
```

### Using the installer script

```bash
# Re-run the installer with --wipe from your target repo
bash scripts/install-skill.sh --wipe

# Or via curl if not running from a local clone
curl -fsSL https://raw.githubusercontent.com/Flux-Frontiers/pycode_kg/main/scripts/install-skill.sh \
  | bash -s -- --wipe
```

---

## Additional CLI Commands

Beyond build/query/viz, the full command set:

| Command | Purpose |
|---|---|
| `pycodekg build` | Full pipeline: SQLite + LanceDB in one step |
| `pycodekg centrality` | Compute Structural Importance Ranking (SIR) over the graph |
| `pycodekg explain <NODE_ID>` | Natural-language explanation of a code node by ID |
| `pycodekg snapshot save <version>` | Capture metrics snapshot (commit, branch, version) |
| `pycodekg snapshot list` | List all snapshots in reverse chronological order |
| `pycodekg snapshot show <commit>` | Full details for a single snapshot |
| `pycodekg snapshot diff <a> <b>` | Compare two snapshots side-by-side |
| `pycodekg viz-timeline` | Temporal metrics evolution chart (2d or 3d) |
| `pycodekg architecture [<repo>]` | Generate Markdown/JSON architecture description |
| `pycodekg download-model` | Pre-download embedding model for offline use |
| `pycodekg install-hooks` | Install post-commit git hook for automatic snapshots |

## Offline Setup

If you need to use PyCodeKG without network access (e.g., in CI, air-gapped nets, or to avoid HuggingFace rate limits):

```bash
# Download the embedding model locally
pycodekg download-model
```

This saves the model to `.pycodekg/models/<model-name>/`. Subsequent runs of `build-lancedb` and `pycodekg query` will use the cached local copy without any network access.

Alternatively, set `PYCODEKG_MODEL_DIR` to cache elsewhere:
```bash
export PYCODEKG_MODEL_DIR=/path/to/shared/models
pycodekg download-model
```

## Configure Claude Code / Kilo Code (.mcp.json)

Both Claude Code and Kilo Code read per-repo config from `.mcp.json` in the project root.

```json
{
  "mcpServers": {
    "pycodekg": {
      "command": "pycodekg",
      "args": [
        "mcp",
        "--repo", "/absolute/path/to/repo",
        "--db",   "/absolute/path/to/repo/.pycodekg/graph.sqlite"
      ]
    }
  }
}
```

Always use **absolute paths**. Merge into existing `mcpServers` — don't overwrite other entries.

> ⚠️ Do NOT add `pycodekg` to any global settings file — use per-repo `.mcp.json` only.

## Configure GitHub Copilot (.vscode/mcp.json)

GitHub Copilot uses a different schema — `"servers"` key and `"type": "stdio"` required:

```json
{
  "servers": {
    "pycodekg": {
      "type": "stdio",
      "command": "pycodekg",
      "args": [
        "mcp",
        "--repo", "/absolute/path/to/repo",
        "--db",   "/absolute/path/to/repo/.pycodekg/graph.sqlite"
      ]
    }
  }
}
```

VS Code will prompt you to **Trust** the server on first use.

## Configure Claude Desktop (claude_desktop_config.json)

Claude Desktop has no Poetry on PATH — use the absolute venv binary:

```bash
poetry env info --path
# → /path/to/venv
# binary: /path/to/venv/bin/pycodekg
```

Config path: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)

```json
{
  "mcpServers": {
    "pycodekg": {
      "command": "/path/to/venv/bin/pycodekg",
      "args": ["mcp", "--repo", "/abs/path", "--db", "/abs/path/.pycodekg/graph.sqlite"]
    }
  }
}
```

## Automated Setup

If the project has Claude Copilot installed:
```
/setup-pycodekg-mcp /path/to/repo
```
This installs, builds, smoke-tests, and writes both config files automatically.

## MCP Tools

| Tool | When to use |
|---|---|
| `graph_stats()` | First call — understand codebase size/shape |
| `query_codebase(q)` | Explore graph structure, find relevant nodes; tune precision with `min_score` and result diversity with `max_per_module` |
| `pack_snippets(q)` | Read actual source code (prefer over query_codebase); supports `min_score` and `max_per_module` |
| `get_node(node_id, include_edges)` | Fetch node metadata; `include_edges=True` also returns outgoing edges + incoming callers |
| `list_nodes(module_path, kind)` | List nodes filtered by module path prefix and/or kind |
| `callers(node_id)` | Find all callers of a node — fan-in lookup resolving cross-module sym: stubs with import-aware filtering for ambiguous names |
| `explain(node_id)` | Natural-language explanation of a node: role, docstring, callers, callees |
| `centrality(top, kinds, group_by)` | SIR PageRank — rank nodes or modules by structural importance; use before refactoring or to prioritize test coverage |
| `bridge_centrality(top, include_imports)` | Module connectivity ranking — identifies orchestrator/hub modules by how many other modules they interact with |
| `framework_nodes(top)` | Identify framework-like hub modules: high SIR + high connectivity (0.6×SIR + 0.4×connectivity) |
| `analyze_repo()` | Full architectural analysis — complexity, coupling, coverage, orphans |
| `snapshot_list(limit)` | List saved metric snapshots newest-first (use `limit=0` for all) |
| `snapshot_show(key)` | Full metrics for a snapshot key (tree hash) or `"latest"`; legacy snapshots backfill missing deltas |
| `snapshot_diff(key_a, key_b)` | Compare two snapshots by key — node/edge/coverage/issues delta |

## CodeRank Tools

Structure-aware ranking that blends PageRank with semantic search.

| Tool | When to use |
|---|---|
| `rank_nodes(top, rels, persist_metric, exclude_tests)` | Global weighted CodeRank (PageRank) — find the most structurally important nodes across the whole repo |
| `query_ranked(q, k, mode, top, rels, radius, exclude_tests)` | CodeRank-enhanced query: `hybrid` mode (0.60×semantic + 0.25×centrality + 0.15×proximity) or `ppr` (0.70×personalized PageRank + 0.30×semantic) |
| `explain_rank(node_id, q)` | Explain why a node ranked where it did — shows inbound counts, global rank, and query-conditioned scores |

**CodeRank workflows:**
- Find most important nodes globally: `rank_nodes(top=25)` → `explain_rank`
- Persist global rank for later queries: `rank_nodes(persist_metric='coderank_global')`
- Structure-aware query: `query_ranked(q='database connection', mode='hybrid')`

## Query Strategy Guide

### Choosing `k` and `hop`

| Goal | Settings |
|---|---|
| Narrow, precise lookup | `k=4, hop=0` |
| Standard exploration | `k=8, hop=1` (default) |
| Broad context sweep | `k=12, hop=2` |
| Deep dependency trace | `k=8, hop=2, rels="CALLS,IMPORTS"` |

### Choosing `rels`

| Relation | When to include |
|---|---|
| `CONTAINS` | Almost always — structural context |
| `CALLS` | Tracing execution flow |
| `IMPORTS` | Dependency analysis |
| `INHERITS` | OOP hierarchy |
| `RESOLVES_TO` | Connecting `sym:` stubs to definitions | Used internally by `callers()` — include in `query_codebase` rels for graph traversal through import aliases |

### Typical session workflow

```
1. graph_stats()                                         → orientation
2. query_codebase("auth flow", k=8, hop=1)               → find nodes
3. explain("cls:src/auth/jwt.py:JWTValidator")           → understand before reading
4. pack_snippets("JWT validation", k=6, hop=1)           → read source
5. get_node("fn:src/auth/jwt.py:JWTValidator.validate", include_edges=True)
                                                         → node detail + neighborhood in one call
6. pack_snippets("error handling", k=4, hop=2, rels="CALLS")  → deeper
7. snapshot_list() / snapshot_diff("a", "b")             → track codebase evolution
```

### Structural importance workflows

```
# Identify hotspots before refactoring
centrality(top=20)                                       → SIR ranking by node
centrality(top=10, group_by="module")                    → SIR ranking by module
bridge_centrality(top=10)                                → hub modules by connectivity
framework_nodes(top=10)                                  → most critical hub modules

# CodeRank-enhanced search
rank_nodes(top=25)                                       → global PageRank ranking
query_ranked("database connection", mode="hybrid")       → structure-aware query
explain_rank("fn:src/db/store.py:connect")               → why did this rank here?
```

## .gitignore Setup

The `.pycodekg/` directory holds the SQLite graph, LanceDB vector index, and snapshots. All are local artifacts — the graph and index are reproducible, snapshots are captured by the post-commit hook.

```gitignore
.pycodekg/
```

Add this to `.gitignore` when installing PyCodeKG in a new repo. Commit snapshots manually at milestones if you want git history.

## Key Defaults

- `k=8, hop=1, rels="CONTAINS,CALLS,IMPORTS,INHERITS"`
- Node ID format: `<kind>:<module_path>:<qualname>` (e.g. `fn:src/auth/jwt.py:JWTValidator.validate`)
- Node ID prefixes: `mod:` module, `cls:` class, `fn:` function/method, `sym:` external symbol
- Transport: `stdio` (Claude Code/Desktop), `sse` (HTTP clients)

## Troubleshooting

| Error | Fix |
|---|---|
| `error: the following arguments are required: --sqlite` | Use `--sqlite`, not `--db`, for `pycodekg build-lancedb` |
| `ERROR: 'mcp' package not found` | `poetry add mcp` |
| `WARNING: SQLite database not found` | Run both build commands first |
| MCP server not appearing | Use absolute paths; restart Claude Code |
| Empty query results | Run `pycodekg build-lancedb --wipe` |

## Full Reference

See `references/installation.md` for complete CLI flags, `.mcp.json` templates with full Copilot stack, gitignore recommendations, and query strategy guide.
