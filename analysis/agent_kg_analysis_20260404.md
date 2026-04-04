> **Analysis Report Metadata**
> - **Generated:** 2026-04-04T19:38:15Z
> - **Version:** code-kg 0.9.2
> - **Commit:** 10ce0dd (main)
> - **Platform:** macOS 26.4 | arm64 (arm) | Turing | Python 3.12.13
> - **Graph:** 3192 nodes · 3617 edges (277 meaningful)
> - **Included directories:** all
> - **Excluded directories:** none
> - **Elapsed time:** 3s

# agent_kg Analysis

**Generated:** 2026-04-04 19:38:15 UTC

---

## Executive Summary

This report provides a comprehensive architectural analysis of the **agent_kg** repository using CodeKG's knowledge graph. The analysis covers complexity hotspots, module coupling, key call chains, and code quality signals to guide refactoring and architecture decisions.

| Overall Quality | Grade | Score |
|----------------|-------|-------|
| [C] **Fair** | **C** | 60 / 100 |

---

## Baseline Metrics

| Metric | Value |
|--------|-------|
| **Total Nodes** | 3192 |
| **Total Edges** | 3617 |
| **Modules** | 26 (of 26 total) |
| **Functions** | 71 |
| **Classes** | 33 |
| **Methods** | 147 |

### Edge Distribution

| Relationship Type | Count |
|-------------------|-------|
| CALLS | 966 |
| CONTAINS | 251 |
| IMPORTS | 273 |
| ATTR_ACCESS | 970 |
| INHERITS | 4 |

---

## Fan-In Ranking

Most-called functions are potential bottlenecks or core functionality. These functions are heavily depended upon across the codebase.

| # | Function | Module | Callers |
|---|----------|--------|---------|
| 1 | `close()` | src/agent_kg/graph.py | **20** |
| 2 | `close()` | src/agent_kg/kg.py | **20** |
| 3 | `close()` | src/agent_kg/profile.py | **20** |
| 4 | `close()` | src/agent_kg/graph.py | **19** |
| 5 | `_get_db()` | src/agent_kg/store.py | **14** |
| 6 | `_resolve_kg()` | src/agent_kg/cli/main.py | **10** |
| 7 | `stats()` | src/agent_kg/cli/main.py | **10** |
| 8 | `_kg()` | src/agent_kg/mcp/server.py | **7** |
| 9 | `get_nodes_by_kind()` | src/agent_kg/store.py | **6** |
| 10 | `get_node()` | src/agent_kg/store.py | **6** |
| 11 | `get_by_kind()` | src/agent_kg/profile.py | **5** |
| 12 | `_get_table()` | src/agent_kg/store.py | **5** |
| 13 | `embed()` | src/agent_kg/store.py | **5** |
| 14 | `add_edge()` | src/agent_kg/store.py | **5** |
| 15 | `_get_db()` | src/agent_kg/profile.py | **4** |


**Insight:** Functions with high fan-in are either core APIs or bottlenecks. Review these for:
- Thread safety and performance
- Clear documentation and contracts
- Potential for breaking changes

---

## High Fan-Out Functions (Orchestrators)

Functions that call many others may indicate complex orchestration logic or poor separation of concerns.

No extreme high fan-out functions detected. Well-balanced architecture.

---

## Module Architecture

Top modules by dependency coupling and cohesion (showing up to 10 with activity).
Cohesion = incoming / (incoming + outgoing + 1); higher = more internally focused.

| Module | Functions | Classes | Incoming | Outgoing | Cohesion |
|--------|-----------|---------|----------|----------|----------|
| `src/agent_kg/graph.py` | 1 | 2 | 10 | 12 | 0.52 |
| `src/agent_kg/profile.py` | 1 | 2 | 5 | 1 | 0.14 |
| `src/agent_kg/store.py` | 1 | 1 | 2 | 1 | 0.25 |
| `src/agent_kg/session.py` | 0 | 3 | 3 | 1 | 0.20 |
| `src/agent_kg/cli/main.py` | 14 | 0 | 0 | 2 | 0.67 |
| `src/agent_kg/kg.py` | 0 | 1 | 3 | 9 | 0.69 |
| `src/agent_kg/schema.py` | 3 | 7 | 11 | 0 | 0.00 |
| `src/agent_kg/summarize.py` | 0 | 3 | 4 | 0 | 0.00 |
| `src/agent_kg/mcp/server.py` | 12 | 0 | 0 | 2 | 0.67 |
| `src/agent_kg/ingest.py` | 3 | 2 | 3 | 8 | 0.67 |

---

## Key Call Chains

Deepest call chains in the codebase.

**Chain 1** (depth: 4)

```
__exit__ → close → close → close_session
```

**Chain 2** (depth: 4)

```
__exit__ → close → close → close_session
```

**Chain 3** (depth: 4)

```
__exit__ → close → close → close_session
```

**Chain 4** (depth: 3)

```
close → close → close_session
```

---

## Public API Surface

Identified public APIs (module-level functions with high usage).

| Function | Module | Fan-In | Type |
|----------|--------|--------|------|
| `stats()` | src/agent_kg/cli/main.py | 10 | function |
| `Node()` | src/agent_kg/schema.py | 4 | class |
| `Edge()` | src/agent_kg/schema.py | 4 | class |
| `AgentKG()` | src/agent_kg/kg.py | 3 | class |
| `prune()` | src/agent_kg/prune.py | 3 | function |
| `pack()` | src/agent_kg/query.py | 2 | function |
| `assemble()` | src/agent_kg/cli/main.py | 2 | function |
| `AgentKG()` | src/agent_kg/graph.py | 2 | class |
| `NodeKind()` | src/agent_kg/schema.py | 2 | class |
| `query()` | src/agent_kg/query.py | 2 | function |
---

## Docstring Coverage

Docstring coverage directly determines semantic retrieval quality. Nodes without
docstrings embed only structured identifiers (`KIND/NAME/QUALNAME/MODULE`), where
keyword search is as effective as vector embeddings. The semantic model earns its
value only when a docstring is present.

| Kind | Documented | Total | Coverage |
|------|-----------|-------|----------|
| `function` | 50 | 71 | [WARN] 70.4% |
| `method` | 71 | 147 | [LOW] 48.3% |
| `class` | 23 | 33 | [WARN] 69.7% |
| `module` | 24 | 26 | [OK] 92.3% |
| **total** | **168** | **277** | **[WARN] 60.6%** |

> **Recommendation:** 109 nodes lack docstrings. Prioritize documenting high-fan-in functions and public API surface first — these have the highest impact on query accuracy.

---

## Structural Importance Ranking (SIR)

Weighted PageRank aggregated by module — reveals architectural spine. Cross-module edges boosted 1.5×; private symbols penalized 0.85×. Node-level detail: `codekg centrality --top 25`

| Rank | Score | Members | Module |
|------|-------|---------|--------|
| 1 | 0.169034 | 31 | `src/agent_kg/profile.py` |
| 2 | 0.166494 | 29 | `src/agent_kg/store.py` |
| 3 | 0.136768 | 40 | `src/agent_kg/graph.py` |
| 4 | 0.087079 | 14 | `src/agent_kg/schema.py` |
| 5 | 0.063111 | 14 | `src/agent_kg/kg.py` |
| 6 | 0.057704 | 17 | `src/agent_kg/session.py` |
| 7 | 0.040588 | 14 | `src/agent_kg/summarize.py` |
| 8 | 0.038713 | 9 | `src/agent_kg/index.py` |
| 9 | 0.034483 | 13 | `src/agent_kg/mcp/server.py` |
| 10 | 0.029853 | 15 | `src/agent_kg/cli/main.py` |
| 11 | 0.027650 | 11 | `src/agent_kg/ingest.py` |
| 12 | 0.024959 | 9 | `src/agent_kg/snapshots.py` |
| 13 | 0.021780 | 9 | `src/agent_kg/prune.py` |
| 14 | 0.021413 | 9 | `src/agent_kg/onboard.py` |
| 15 | 0.018750 | 6 | `src/agent_kg/assemble.py` |



---

## Code Quality Issues

- [WARN] Moderate docstring coverage (60.6%) — semantic retrieval quality is degraded for undocumented nodes; BM25 is as effective as embeddings without docstrings
- [WARN] 4 orphaned functions found (`wipe`, `current`, `wipe`, `wipe`) -- consider archiving or documenting

---

## Architectural Strengths

- Well-structured with 15 core functions identified
- No god objects or god functions detected

---

## Recommendations

### Immediate Actions
1. **Improve docstring coverage** — 109 nodes lack docstrings; prioritize high-fan-in functions and public APIs first for maximum semantic retrieval gain
2. **Remove or archive orphaned functions** — `wipe`, `current`, `wipe`, `wipe` have zero callers and add maintenance burden

### Medium-term Refactoring
1. **Harden high fan-in functions** — `close`, `close`, `close` are widely depended upon; review for thread safety, clear contracts, and stable interfaces
2. **Reduce module coupling** — consider splitting tightly coupled modules or introducing interface boundaries
3. **Add tests for key call chains** — the identified call chains represent well-traveled execution paths that benefit most from regression coverage

### Long-term Architecture
1. **Version and stabilize the public API** — document breaking-change policies for `stats`, `Node`, `Edge`
2. **Enforce layer boundaries** — add linting or CI checks to prevent unexpected cross-module dependencies as the codebase grows
3. **Monitor hot paths** — instrument the high fan-in functions identified here to catch performance regressions early

---

## Inheritance Hierarchy

**4** INHERITS edges across **4** classes. Max depth: **0**.

| Class | Module | Depth | Parents | Children |
|-------|--------|-------|---------|----------|
| `EdgeRelation` | src/agent_kg/schema.py | 0 | 1 | 0 |
| `IntentCategory` | src/agent_kg/schema.py | 0 | 1 | 0 |
| `NodeKind` | src/agent_kg/schema.py | 0 | 1 | 0 |
| `TaskStatus` | src/agent_kg/schema.py | 0 | 1 | 0 |


---

## Snapshot History

No snapshots found. Run `codekg snapshot save <version>` to capture one.


---

## Appendix: Orphaned Code

Functions with zero callers (potential dead code):

| Function | Module | Lines |
|----------|--------|-------|
| `wipe()` | src/agent_kg/index.py | 5 |
| `wipe()` | src/agent_kg/profile.py | 3 |
| `wipe()` | src/agent_kg/graph.py | 3 |
| `current()` | src/agent_kg/session.py | 1 |
---

## CodeRank -- Global Structural Importance

Weighted PageRank over CALLS + IMPORTS + INHERITS edges (test paths excluded). Scores are normalized to sum to 1.0. This ranking seeds Phase 2 fan-in discovery and Phase 15 concern queries.

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.001914 | method | `UserProfileStore.get_by_kind` | src/agent_kg/profile.py |
| 2 | 0.001614 | method | `AgentKGStore._get_db` | src/agent_kg/store.py |
| 3 | 0.001091 | function | `_kg` | src/agent_kg/mcp/server.py |
| 4 | 0.000937 | method | `UserProfileStore._get_db` | src/agent_kg/profile.py |
| 5 | 0.000883 | function | `_resolve_kg` | src/agent_kg/cli/main.py |
| 6 | 0.000813 | method | `UserProfileStore._row_to_node` | src/agent_kg/profile.py |
| 7 | 0.000578 | method | `AgentKGStore.get_nodes_by_kind` | src/agent_kg/store.py |
| 8 | 0.000557 | method | `AgentKGStore._get_table` | src/agent_kg/store.py |
| 9 | 0.000542 | method | `UserProfileGraph.close` | src/agent_kg/profile.py |
| 10 | 0.000542 | method | `ConversationGraph.close` | src/agent_kg/graph.py |
| 11 | 0.000542 | class | `SummarizerConfig` | src/agent_kg/summarize.py |
| 12 | 0.000542 | method | `AgentKG.close` | src/agent_kg/kg.py |
| 13 | 0.000542 | method | `SummarizerConfig.from_env` | src/agent_kg/summarize.py |
| 14 | 0.000506 | method | `AgentKGStore._get_embedder` | src/agent_kg/store.py |
| 15 | 0.000501 | method | `AgentKGStore.embed` | src/agent_kg/store.py |
| 16 | 0.000481 | method | `ConversationIndex._get_db` | src/agent_kg/index.py |
| 17 | 0.000469 | method | `Onboarder._store` | src/agent_kg/onboard.py |
| 18 | 0.000459 | method | `AgentKG.start_session` | src/agent_kg/kg.py |
| 19 | 0.000455 | class | `OnboardResult` | src/agent_kg/onboard.py |
| 20 | 0.000418 | method | `AgentKGStore.upsert_node` | src/agent_kg/store.py |

---

## Concern-Based Hybrid Ranking

Top structurally-dominant nodes per architectural concern (0.60 × semantic + 0.25 × CodeRank + 0.15 × graph proximity).

### Configuration Loading Initialization Setup

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.7947 | method | `SummarizerConfig.from_env` | src/agent_kg/summarize.py |
| 2 | 0.7476 | method | `UserProfileStore.__init__` | src/agent_kg/profile.py |
| 3 | 0.735 | function | `init_server` | src/agent_kg/mcp/server.py |
| 4 | 0.7327 | method | `AgentKGStore.__init__` | src/agent_kg/store.py |
| 5 | 0.7318 | method | `UserProfileGraph.__init__` | src/agent_kg/profile.py |

### Data Persistence Storage Database

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.7309 | method | `AgentKGStore.embed_node` | src/agent_kg/store.py |
| 2 | 0.7247 | function | `consolidate` | src/agent_kg/consolidate.py |
| 3 | 0.7186 | function | `prune` | src/agent_kg/prune.py |
| 4 | 0.7186 | function | `capture` | src/agent_kg/snapshots.py |
| 5 | 0.69 | class | `AgentKGStore` | src/agent_kg/store.py |

### Query Search Retrieval Semantic

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.75 | function | `query` | src/agent_kg/cli/main.py |
| 2 | 0.7429 | method | `AgentKG.index` | src/agent_kg/graph.py |
| 3 | 0.7312 | method | `ConversationIndex.search` | src/agent_kg/index.py |
| 4 | 0.7298 | method | `AgentKGStore.search` | src/agent_kg/store.py |
| 5 | 0.7211 | function | `query` | src/agent_kg/query.py |

### Graph Traversal Node Edge

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.75 | method | `AgentKG.stats` | src/agent_kg/graph.py |
| 2 | 0.7497 | function | `_get_topic_nodes_for_turns` | src/agent_kg/prune.py |
| 3 | 0.7466 | method | `ConversationGraph.edges_to` | src/agent_kg/graph.py |
| 4 | 0.7465 | method | `ConversationGraph.edges_from` | src/agent_kg/graph.py |
| 5 | 0.7396 | method | `AgentKGStore.refresh_related_to_edges` | src/agent_kg/store.py |



---

*Report generated by CodeKG Thorough Analysis Tool — analysis completed in 3.4s*

---

*Copyright © 2026 Eric G. Suchanek, PhD. All rights reserved. [Elastic License 2.0](https://www.elastic.co/licensing/elastic-license)*
