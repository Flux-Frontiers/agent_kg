# Release Notes -- v0.14.0

> Released: 2026-10-26

Step 4 of the fleet's MCP centralization (kgrag_priv
`docs/MCP_CENTRALIZATION_PLAN.md`, sweep item 93). **Needs kgmodule-utils
0.29.0**, which provides `kg_utils.mcp`: the floor is `>=0.29.0`,
whose `[mcp]` extra replaces the direct `mcp` pin.

### Changed

- **`AgentKG.stats()`, and so the `stats` tool, returns the fleet stats
  shape** (kgrag_priv `docs/FLEET_STANDARDS.md`, "KG stats shape"):
  `{"kind": "agent", "nodes": {"total", "by_kind"}, "edges": {"total",
  "by_rel"}}`, built by `kg_utils.stats.kg_stats`, with `session_id`,
  `turn_count`, `session_count` and `person_id` as extras. The bare-int
  `nodes` / `edges` keys, `node_count`, `edge_count` and `kind_counts` are
  gone from it; read `stats["nodes"]["total"]` and friends. The store's own
  `stats()` stays flat for snapshots, drops its unread bare-int `nodes` /
  `edges` and `kind`, and gains `rel_counts`, so snapshots now record
  `edge_counts` too. `agentkg stats` prints the relation breakdown and the
  session count.

- **The MCP server is built on `kg_utils.mcp`**, off the low-level `Server`.
  It serves the fleet's five canonical tools under the same names as every
  other KG server (`stats`, `query`, `pack`, `get_node`, `neighbors`), then
  AgentKG's own, unprefixed: `ingest`, `assemble`, `prune`, `topics`, `tasks`,
  `profile`, `analyze`. The server's instructions are generated from the
  tools' docstrings, and `agentkg mcp --manifest` prints the tool list as JSON
  without opening the graph. A tool that fails is now an MCP error (`isError`)
  instead of an `Error in ...` text result. Under stdio, stray prints go to
  stderr instead of corrupting the protocol stream.
- **One graph per client session.** The server opens the repository's graph
  once per MCP session, instead of reopening it (and its conversation session)
  on every tool call, and prints the store it serves to stderr.
- `agentkg mcp` takes the fleet's standard flags: `--repo`, `--db`,
  `--vectors`, `--model`, `--transport stdio|streamable-http`, `--host`,
  `--port`, `--manifest`. `AGENTKG_REPO` still scopes the server when
  `--repo` is not given, so installed configs keep working; `AGENTKG_PERSON`
  and `AGENTKG_SESSION` are unchanged. `agentkg-mcp` is the same command.
  Registering it does not import `mcp`.
- `AgentKG.query()` and `AgentKG.pack()` take keyword-only `hop`,
  `max_nodes` and `rels`. The default `hop=0` returns exactly the old hits;
  `hop` > 0 appends the graph neighbourhood of those hits, ranked after them.
  Every hit carries `hop` and `via_seed`. The MCP `query` returns
  `{"query", "hits"}` (structured JSON) instead of formatted text.
- `AgentKG(..., *, db_path=None, vectors_path=None)`, with read-only
  `repo_root`, `db_path`, `vectors_path` and `model_name` properties.

### Added

- `AgentKG.node(node_id)`, `AgentKG.neighbors(node_id, *, rels, direction,
  limit)` and `AgentKGStore.edges_touching()`: the edges touching one node and
  the nodes at their other ends, ordered by (relation, source, target). Graph
  only; no model is loaded. Same contract as
  `kg_utils.pipeline.KGModule.neighbors`.

### Removed

- **MCP tool names `agent_kg_*`**, with no aliases: `agent_kg_stats`,
  `agent_kg_query` and `agent_kg_pack` are `stats`, `query` and `pack`; the
  rest drop the prefix. Their per-call `repo`, `person_id` and `session_id`
  arguments are gone: a server serves one repository, and the person and
  session come from the environment. `query`, `pack` and `assemble` take `q`
  instead of `query`. (`profile` still takes an optional `person_id`.)

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
