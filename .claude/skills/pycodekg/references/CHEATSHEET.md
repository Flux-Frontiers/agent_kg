# PyCodeKG Query Cheatsheet

A practical reference for the seventeen MCP tools, with examples drawn from this codebase.
All queries below work against the live `pycode_kg` knowledge graph.

---

## The Seventeen Tools at a Glance

### Core Tools

| Tool | Best for | Returns |
|---|---|---|
| `graph_stats()` | Orientation — size and shape of the graph | Markdown: node/edge counts by kind |
| `query_codebase(q)` | Structural exploration — *what exists, how things relate* | JSON: ranked nodes + edges |
| `pack_snippets(q)` | Implementation detail — *actual source code* | Markdown: snippets with line numbers |
| `get_node(node_id, include_edges)` | Pinpoint lookup — one node by its stable ID + optional neighborhood | Markdown: full node metadata |
| `list_nodes(module_path, kind)` | Enumerate all nodes in a module filtered by kind | JSON: array of matching nodes |
| `callers(node_id, rel)` | Fan-in lookup — *who calls this function?* | JSON: all caller nodes, resolved through stubs |
| `explain(node_id)` | Natural language understanding — *what does this do?* | Markdown: role, callers, callees, docstring |
| `centrality(top, kinds, group_by)` | SIR PageRank — rank nodes or modules by structural importance | Markdown: ranking table |
| `bridge_centrality(top, include_imports)` | Hub modules by connectivity — orchestrators and entry points | Markdown: ranking table |
| `framework_nodes(top)` | Framework-like hubs: high SIR + high connectivity | Markdown: ranking table |
| `analyze_repo()` | Full architectural health check — complexity, coupling, orphans | Markdown: nine-phase analysis |
| `snapshot_list(limit, branch)` | Temporal tracking — *how has the codebase grown?* | JSON: snapshots with deltas, newest first |
| `snapshot_show(key)` | Snapshot detail — full metrics at a specific snapshot or `"latest"` | JSON: full metrics + hotspots + deltas |
| `snapshot_diff(key_a, key_b)` | Before/after comparison — *what changed between two snapshots?* | JSON: metrics for both + computed delta |

### CodeRank Tools

| Tool | Best for | Returns |
|---|---|---|
| `rank_nodes(top, rels, persist_metric, exclude_tests)` | Global weighted PageRank — most structurally important nodes | JSON: ranked nodes with scores |
| `query_ranked(q, k, mode, top, rels, radius, exclude_tests)` | Structure-aware query blending semantic + centrality + proximity | JSON: nodes with score components |
| `explain_rank(node_id, q)` | Why did this node rank here? — inbound counts, global rank, query scores | Markdown: rank explanation |

---

## 1. Orient First with `graph_stats`

Always start here when approaching an unfamiliar codebase or after a rebuild.

```python
graph_stats()
```

Returns counts broken down by node kind and edge relation.
For this repo you'll see:

```json
{
  "total_nodes": 3818,
  "total_edges": 3717,
  "node_counts": { "class": 27, "function": 80, "method": 132, "module": 32, "symbol": 3547 },
  "edge_counts": { "ATTR_ACCESS": 1274, "CALLS": 1310, "CONTAINS": 239, "IMPORTS": 210, "INHERITS": 8, "RESOLVES_TO": 676 }
}
```

High symbol counts mean data-flow edges are active (ATTR_ACCESS, RESOLVES_TO). High CALLS counts mean the call graph is rich.

---

## 2. Semantic Exploration with `query_codebase`

Returns a ranked set of nodes and the edges between them. Good for mapping unknown territory.

### Find classes and their methods

```python
query_codebase("knowledge graph storage persistence")
```

Returns `GraphStore`, `PyCodeKG`, and the edges connecting them — no need to know filenames.

### Trace a call chain

```python
query_codebase("query pipeline semantic search expansion", rels="CALLS")
```

`rels=` restricts graph expansion to a single edge type. Set it to `"CALLS"` to follow execution flow only.

### Explore the module import graph

```python
query_codebase("module imports dependencies", rels="IMPORTS")
```

### Find inheritance hierarchies

```python
query_codebase("NodeVisitor AST visitor base class", rels="INHERITS")
```

`PyCodeKGVisitor` inherits from `ast.NodeVisitor` — this surfaces that relationship.

### Combine edge types

```python
query_codebase("build index embedding", rels="CALLS,IMPORTS")
```

Comma-separated `rels` expand through multiple relation types simultaneously.

### Increase graph depth

```python
query_codebase("error handling exception", hop=2)
```

`hop=2` follows edges two levels out from each seed. Useful when the entry point is one hop away from the interesting logic.

### Filter weak semantic seeds

```python
query_codebase("error handling exception", min_score=0.25)
```

`min_score` filters low-similarity seeds (`score = 1 - distance`, clamped to `[0,1]`) before structural expansion.

### Keep module diversity

```python
query_codebase("storage layer", max_per_module=2)
```

`max_per_module` caps returned nodes per module so one file does not dominate results.

### Include symbol-level nodes

```python
query_codebase("self.edges attribute access", include_symbols=True)
```

With `include_symbols=True` the result includes `symbol` nodes — per-scope variable and attribute references created by `PyCodeKGVisitor`.

---

## 3. Source Retrieval with `pack_snippets`

Returns Markdown with actual source snippets, ranked and deduplicated. Use this when you need to *read* the code, not just locate it.

### Understand an implementation

```python
pack_snippets("visitor scope tracking variable assignment")
```

Returns `PyCodeKGVisitor`, `visit_FunctionDef`, `visit_Assign` with surrounding source lines.

### Get context for a specific concept

```python
pack_snippets("graph expansion hop traversal", max_nodes=5)
```

`max_nodes` limits the number of snippets returned — useful when you only need the top results.

### Widen the snippet window

```python
pack_snippets("schema SQL CREATE TABLE", context=15)
```

`context=` controls how many lines of context appear above and below each definition. Default is 5; raise it for dense logic.

### Cap snippet length

```python
pack_snippets("to_markdown render output", max_lines=40)
```

`max_lines=` prevents very long functions from dominating the output.

### Increase semantic seeds

```python
pack_snippets("embedding model LanceDB index build", k=12)
```

`k=` is the number of semantic seed nodes before graph expansion. Raise it when the first results feel off-target.

### Tighten snippet packs

```python
pack_snippets("query expansion ranking", min_score=0.2, max_per_module=1)
```

Use `min_score` and `max_per_module` together to reduce noisy packs and improve cross-module coverage.

---

## 4. Pinpoint Lookup with `get_node`

Fetch a single node by its stable ID. Node IDs appear in `query_codebase` and `pack_snippets` results.
Pass `include_edges=True` to retrieve outgoing edges and incoming callers in the same call.

### Node ID format

```
<kind>:<module_path>:<qualname>

fn:src/pycode_kg/mcp_server.py:pack_snippets
m:src/pycode_kg/visitor.py:PyCodeKGVisitor.visit_Attribute
cls:src/pycode_kg/store.py:GraphStore
mod:src/pycode_kg/kg.py
```

### Fetch a function

```python
get_node("fn:src/pycode_kg/mcp_server.py:query_codebase")
```

Returns `lineno`, `end_lineno`, `docstring`, `module_path`, `qualname`.

### Fetch with immediate neighborhood

```python
get_node("fn:src/pycode_kg/mcp_server.py:query_codebase", include_edges=True)
```

Also returns `outgoing_edges` (grouped by CALLS, CONTAINS, IMPORTS, INHERITS) and `incoming_calls`
(list of caller node dicts). Eliminates the need for a separate `callers()` call for routine inspection.

### Fetch a method

```python
get_node("m:src/pycode_kg/visitor.py:PyCodeKGVisitor.finalize")
```

### Fetch a module

```python
get_node("mod:src/pycode_kg/__init__.py")
```

---

## 5. Fan-In Lookup with `callers`

Find all nodes that call a given function, including cross-module callers resolved through symbol stubs.

When same-name definitions exist in multiple modules, caller resolution uses import-aware filtering to avoid false-positive fan-in links.

### Find direct and indirect callers

```python
callers("fn:src/pycode_kg/store.py:GraphStore.expand")
```

Returns all functions that call `expand()`, with full node metadata (location, docstring, etc.).

### Restrict by relation type

```python
callers("fn:src/pycode_kg/store.py:GraphStore.expand", rel="CALLS")
```

The `rel` parameter (default `"CALLS"`) lets you find other relation types — e.g., `rel="INHERITS"` to find all subclasses.

---

## 6. Natural-Language Explanation with `explain`

Get a structured understanding of what a code node does, who calls it, and what it calls.

### Explain a function

```python
explain("fn:src/pycode_kg/store.py:GraphStore.expand")
```

Returns:
- **Role** — Kind, module, source location
- **Documentation** — Full docstring
- **Called By** — List of callers (top 10, with module paths)
- **Calls** — List of callees (what this function calls)

### Explain a method

```python
explain("m:src/pycode_kg/visitor.py:PyCodeKGVisitor.visit_FunctionDef")
```

### Explain a class

```python
explain("cls:src/pycode_kg/store.py:GraphStore")
```

Returns class-level metadata including methods and key callers.

---

## 7. Structural Importance with Centrality & CodeRank

### `centrality` — SIR PageRank

Rank nodes or modules by structural importance (weighted PageRank over the call graph).

```python
centrality(top=20)                      # top 20 nodes by importance
centrality(top=10, group_by="module")   # roll up by module
centrality(top=10, kinds="class")       # filter to classes only
```

### `bridge_centrality` — hub module connectivity

Find modules that act as orchestrators or bridges — high connectivity across the graph.

```python
bridge_centrality(top=10)
bridge_centrality(top=10, include_imports=True)  # include import edges
```

### `framework_nodes` — most critical hubs

Composite score: `0.6×SIR + 0.4×connectivity`. Identifies the most load-bearing modules.

```python
framework_nodes(top=10)
```

### CodeRank tools — structure-aware search

| Tool | Purpose |
|---|---|
| `rank_nodes(top=25)` | Global weighted PageRank over the full repo |
| `query_ranked(q, mode="hybrid")` | 0.60×semantic + 0.25×centrality + 0.15×proximity |
| `query_ranked(q, mode="ppr")` | 0.70×personalized PageRank + 0.30×semantic |
| `explain_rank(node_id, q)` | Why did this node rank where it did? |

```python
# Find most important nodes globally
rank_nodes(top=25)

# Save scores for later use at query time
rank_nodes(persist_metric='coderank_global')

# Structure-aware search
query_ranked("database connection", mode="hybrid")
query_ranked("query pipeline", mode="ppr")

# Explain ranking
explain_rank("fn:src/pycode_kg/store.py:GraphStore.expand")
explain_rank("fn:src/pycode_kg/store.py:GraphStore.expand", q="database connection")
```

**Typical structural importance workflow:**

```python
# Before refactoring: identify hotspots
centrality(top=20)                    → SIR ranking
bridge_centrality(top=10)             → hub modules
framework_nodes(top=10)               → most critical modules

# Impact-aware query
rank_nodes(top=25)                    → global PageRank
query_ranked("auth", mode="hybrid")   → structure-aware result
```

---

## 8. Temporal Tracking with Snapshot Tools

Track how the codebase evolves across commits — node/edge growth, coverage trends, complexity changes.

### List all snapshots

```python
snapshot_list()
```

Returns the 10 most recent snapshots (newest first), each with tree hash key, branch, timestamp, version,
key metrics, and deltas vs. the previous snapshot.

```python
snapshot_list(limit=0)              # return all snapshots
snapshot_list(branch="main")        # filter to a specific branch
```

### Show a specific snapshot

```python
snapshot_show()                    # most recent (default: "latest")
snapshot_show("abc1234")           # specific key: tree hash
```

Returns full `SnapshotMetrics` (nodes, edges, coverage, critical issues, complexity median),
top hotspots, and deltas vs. both the previous and baseline snapshots.

### Compare two snapshots

```python
snapshot_diff("abc1234", "def5678")   # tree hashes from snapshot_list()
```

Returns metrics for both snapshots and a computed delta (b − a) covering: total nodes, total edges,
docstring coverage change, and critical-issues change.

### Typical snapshot workflow

```python
# 1. Discover available snapshot keys
snapshot_list()

# 2. Compare before/after a refactor
snapshot_diff("abc1234", "def5678")

# 3. Check the current state
snapshot_show("latest")
```

> Snapshots are captured automatically by the pre-commit hook (`pycodekg install-hooks`).
> They are stored in `.pycodekg/snapshots/` and are tracked in git — staged atomically with each commit.

---

## 9. Data-Flow Queries (from `PyCodeKGVisitor`)

The `PyCodeKGVisitor` class enriches the graph with **data-flow** edges.
These enable a new category of query that structural tools (CALLS, CONTAINS) cannot answer.

### ATTR_ACCESS — attribute access patterns

`ATTR_ACCESS` edges connect a variable node to the attribute being accessed on it.
Pattern: `scope.obj` →[ATTR_ACCESS]→ `scope.attr`

```python
# Find all attribute accesses in the codebase
query_codebase("attribute access self method property", rels="ATTR_ACCESS")

# Find what attributes are accessed on 'con' (database connection)
query_codebase("con execute commit database connection attribute", rels="ATTR_ACCESS", include_symbols=True)

# Explore data flow around the store
pack_snippets("GraphStore edges within attribute access", include_symbols=True)
```

**Current graph:** 2,179 `ATTR_ACCESS` edges, mostly on `self`, local variables, and module-level objects. Also 1,229 `RESOLVES_TO` edges mapping symbols to their definitions.

### Scope awareness — what lives in each function

`PyCodeKGVisitor` tracks `vars_in_scope` per function, seeding all parameter names at function entry. This means semantic queries about parameter patterns are grounded in the correct scope.

```python
# Find functions with specific parameter shapes
pack_snippets("function parameter args kwargs positional keyword-only")

# Find async functions and their argument patterns
pack_snippets("async def fetch url timeout parameter scope")
```

### Default expression scope (a subtle detail)

Default argument values are evaluated in the *enclosing* scope, not the function scope. `PyCodeKGVisitor` handles this correctly, so queries about default expressions land on the right scope.

```python
# Find module-level constants used as default values
pack_snippets("default value parameter enclosing scope constant")
```

---

## 10. Edge Type Reference

| Edge | Direction | Meaning | Source |
|---|---|---|---|
| `CONTAINS` | module → class, class → method, module → fn | Lexical containment | AST structure |
| `CALLS` | fn/method → fn/method | Direct function call | AST `Call` node |
| `IMPORTS` | module → module | `import` statement | AST `Import`/`ImportFrom` |
| `INHERITS` | class → class | `class Foo(Bar)` | AST `ClassDef.bases` |
| `ATTR_ACCESS` | symbol → symbol | `obj.attr` access | `PyCodeKGVisitor.visit_Attribute` |
| `RESOLVES_TO` | symbol → node | Symbol resolves to definition | `SymbolResolver` name binding |
| `READS` *(tracked)* | symbol → — | Variable read | `PyCodeKGVisitor._extract_reads` |
| `WRITES` *(tracked)* | symbol → — | Variable write | `PyCodeKGVisitor.visit_Assign` |

> **READS / WRITES** are tracked in `vars_in_scope` per scope but are not yet stored as graph edges (no `target` node is wired). They will become queryable once hooked into edge storage.

---

## 11. Parameter Quick Reference

### `query_codebase` and `pack_snippets` shared params

| Parameter | Default | Effect |
|---|---|---|
| `q` | *(required)* | Natural-language query |
| `k` | `8` | Semantic seed nodes before expansion |
| `hop` | `1` | Graph expansion hops from each seed |
| `rels` | `"CONTAINS,CALLS,IMPORTS,INHERITS"` | Edge types to traverse |
| `include_symbols` | `False` | Include `symbol`-kind nodes (variables, attrs) |
| `max_nodes` | `25` / `15` | Cap returned nodes |

### `pack_snippets` only

| Parameter | Default | Effect |
|---|---|---|
| `context` | `5` | Lines above/below each definition |
| `max_lines` | `60` | Max lines per snippet block |

---

## 12. Common Query Patterns

### "How does X work?"

```python
pack_snippets("X concept or class name")
```

### "What calls Y?"

```python
query_codebase("Y function name", rels="CALLS")
# Then look for edges where dst == Y's node ID
```

### "What does module Z import?"

```python
query_codebase("module Z name", rels="IMPORTS")
```

### "Find all subclasses of Base"

```python
query_codebase("Base class inheritance", rels="INHERITS")
```

### "What attributes does this object touch?"

```python
query_codebase("object variable name attribute", rels="ATTR_ACCESS", include_symbols=True)
```

### "Show me the full structure of this module"

```python
query_codebase("module name", rels="CONTAINS", hop=2)
```

### "Get me the source for function F"

```python
# Step 1: find the node ID
query_codebase("F function description")
# Step 2: fetch it directly
get_node("fn:src/module/path.py:F")
```

---

## 13. Excluding Directories from Indexing

By default, PyCodeKG indexes all Python files under the repo root. Excluding directories keeps metrics clean and queries accurate.

**Why exclude `tests/`?** Test directories pollute architectural analysis in three ways:
- Pytest entry points have no callers → they show up as **orphaned code**
- Test helpers become the top **fan-in** functions, hiding real hotspots
- Undocumented test functions drag **docstring coverage** well below production reality

**Configuration (`pyproject.toml`, persistent — recommended):**

```toml
[tool.pycodekg]
exclude = ["tests"]          # exclude test suite from all builds and analysis
```

**CLI flags (per-command override):**

```bash
pycodekg build  --repo . --exclude-dir tests
pycodekg analyze . --exclude-dir tests
```

Both options are additive — CLI flags extend `pyproject.toml` excludes.

---

## 14. This Codebase Live Stats

```
Nodes: 6,741   (class: 42 · function: 146 · method: 184 · module: 51 · symbol: 6,318)
Edges: 6,535   (CALLS: 2,403 · ATTR_ACCESS: 2,179 · RESOLVES_TO: 1,229 · IMPORTS: 344 · CONTAINS: 372 · INHERITS: 8)
DB:    .pycodekg/graph.sqlite
Model: all-MiniLM-L6-v2
```

*Rebuild after significant code changes: `pycodekg build --repo . --wipe`*
