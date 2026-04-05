> **Analysis Report Metadata**
> - **Generated:** 2026-04-05T04:45:49Z
> - **Version:** code-kg 0.11.0
> - **Commit:** 9a20d63 (main)
> - **Platform:** macOS 26.4 | arm64 (arm) | Turing | Python 3.12.13
> - **Graph:** 3135 nodes · 3211 edges (221 meaningful)
> - **Included directories:** src
> - **Excluded directories:** none
> - **Elapsed time:** 3s

# agent_kg Analysis

**Generated:** 2026-04-05 04:45:49 UTC

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
| **Total Nodes** | 3135 |
| **Total Edges** | 3211 |
| **Modules** | 27 (of 27 total) |
| **Functions** | 86 |
| **Classes** | 15 |
| **Methods** | 93 |

### Edge Distribution

| Relationship Type | Count |
|-------------------|-------|
| CALLS | 1018 |
| CONTAINS | 194 |
| IMPORTS | 174 |
| ATTR_ACCESS | 998 |
| INHERITS | 4 |

---

## Fan-In Ranking

Most-called functions are potential bottlenecks or core functionality. These functions are heavily depended upon across the codebase.

| # | Function | Module | Callers |
|---|----------|--------|---------|
| 1 | `close()` | src/agent_kg/graph.py | **23** |
| 2 | `_get_db()` | src/agent_kg/store.py | **16** |
| 3 | `_resolve_kg()` | src/agent_kg/cli/main.py | **12** |
| 4 | `_get_db()` | src/agent_kg/user_profile.py | **8** |
| 5 | `add_edge()` | src/agent_kg/store.py | **7** |
| 6 | `stats()` | src/agent_kg/cli/main.py | **7** |
| 7 | `get_by_kind()` | src/agent_kg/user_profile.py | **6** |
| 8 | `get_nodes_by_kind()` | src/agent_kg/store.py | **6** |
| 9 | `_get_table()` | src/agent_kg/store.py | **5** |
| 10 | `embed()` | src/agent_kg/store.py | **5** |
| 11 | `get_node()` | src/agent_kg/store.py | **5** |
| 12 | `embed_node()` | src/agent_kg/store.py | **4** |
| 13 | `_node_tooltip()` | src/agent_kg/viz.py | **4** |
| 14 | `_require_pyvis()` | src/agent_kg/viz.py | **4** |
| 15 | `assemble_context()` | src/agent_kg/assemble.py | **4** |


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
| `src/agent_kg/store.py` | 2 | 1 | 3 | 1 | 0.20 |
| `src/agent_kg/user_profile.py` | 1 | 1 | 2 | 1 | 0.25 |
| `src/agent_kg/cli/main.py` | 19 | 0 | 0 | 1 | 0.50 |
| `src/agent_kg/graph.py` | 0 | 1 | 4 | 12 | 0.71 |
| `src/agent_kg/schema.py` | 3 | 7 | 11 | 0 | 0.00 |
| `src/agent_kg/app.py` | 9 | 0 | 0 | 0 | 0.00 |
| `src/agent_kg/session.py` | 0 | 1 | 2 | 0 | 0.00 |
| `src/agent_kg/index.py` | 0 | 1 | 1 | 1 | 0.33 |
| `src/agent_kg/ingest.py` | 5 | 1 | 1 | 5 | 0.71 |
| `src/agent_kg/summarize.py` | 0 | 2 | 2 | 0 | 0.00 |

---

## Key Call Chains

Deepest call chains in the codebase.

**Chain 1** (depth: 3)

```
close → close → close_session
```

**Chain 2** (depth: 3)

```
ingest → _resolve_kg → AgentKG
```

---

## Public API Surface

Identified public APIs (module-level functions with high usage).

| Function | Module | Fan-In | Type |
|----------|--------|--------|------|
| `stats()` | src/agent_kg/cli/main.py | 7 | function |
| `Edge()` | src/agent_kg/schema.py | 4 | class |
| `Node()` | src/agent_kg/schema.py | 4 | class |
| `assemble_context()` | src/agent_kg/assemble.py | 4 | function |
| `UserProfileStore()` | src/agent_kg/user_profile.py | 3 | class |
| `query()` | src/agent_kg/query.py | 3 | function |
| `pack()` | src/agent_kg/query.py | 2 | function |
| `AgentKG()` | src/agent_kg/graph.py | 2 | class |
| `prune()` | src/agent_kg/prune.py | 2 | function |
| `AgentKGStore()` | src/agent_kg/store.py | 2 | class |
---

## Docstring Coverage

Docstring coverage directly determines semantic retrieval quality. Nodes without
docstrings embed only structured identifiers (`KIND/NAME/QUALNAME/MODULE`), where
keyword search is as effective as vector embeddings. The semantic model earns its
value only when a docstring is present.

| Kind | Documented | Total | Coverage |
|------|-----------|-------|----------|
| `function` | 61 | 86 | [WARN] 70.9% |
| `method` | 75 | 93 | [OK] 80.6% |
| `class` | 15 | 15 | [OK] 100.0% |
| `module` | 25 | 27 | [OK] 92.6% |
| **total** | **176** | **221** | **[WARN] 79.6%** |

> **Recommendation:** 45 nodes lack docstrings. Prioritize documenting high-fan-in functions and public API surface first — these have the highest impact on query accuracy.

---

## Structural Importance Ranking (SIR)

Weighted PageRank aggregated by module — reveals architectural spine. Cross-module edges boosted 1.5×; private symbols penalized 0.85×. Node-level detail: `codekg centrality --top 25`

| Rank | Score | Members | Module |
|------|-------|---------|--------|
| 1 | 0.227669 | 31 | `src/agent_kg/store.py` |
| 2 | 0.166700 | 25 | `src/agent_kg/user_profile.py` |
| 3 | 0.127228 | 14 | `src/agent_kg/schema.py` |
| 4 | 0.081345 | 20 | `src/agent_kg/graph.py` |
| 5 | 0.049429 | 10 | `src/agent_kg/session.py` |
| 6 | 0.045867 | 20 | `src/agent_kg/cli/main.py` |
| 7 | 0.043480 | 9 | `src/agent_kg/index.py` |
| 8 | 0.030765 | 9 | `src/agent_kg/summarize.py` |
| 9 | 0.028486 | 6 | `src/agent_kg/nlp/intent.py` |
| 10 | 0.026929 | 5 | `src/agent_kg/mcp/server.py` |
| 11 | 0.021159 | 8 | `src/agent_kg/viz.py` |
| 12 | 0.020178 | 9 | `src/agent_kg/ingest.py` |
| 13 | 0.019832 | 10 | `src/agent_kg/app.py` |
| 14 | 0.019208 | 7 | `src/agent_kg/prune.py` |
| 15 | 0.015221 | 5 | `src/agent_kg/nlp/entities.py` |



---

## Code Quality Issues

- [WARN] Moderate docstring coverage (79.6%) — semantic retrieval quality is degraded for undocumented nodes; BM25 is as effective as embeddings without docstrings
- [WARN] 3 orphaned functions found (`wipe`, `_init_state`, `_parse_args`) -- consider archiving or documenting

---

## Architectural Strengths

- Well-structured with 15 core functions identified
- No god objects or god functions detected

---

## Recommendations

### Immediate Actions
1. **Improve docstring coverage** — 45 nodes lack docstrings; prioritize high-fan-in functions and public APIs first for maximum semantic retrieval gain
2. **Remove or archive orphaned functions** — `wipe`, `_init_state`, `_parse_args` have zero callers and add maintenance burden

### Medium-term Refactoring
1. **Harden high fan-in functions** — `close`, `_get_db`, `_resolve_kg` are widely depended upon; review for thread safety, clear contracts, and stable interfaces
2. **Reduce module coupling** — consider splitting tightly coupled modules or introducing interface boundaries
3. **Add tests for key call chains** — the identified call chains represent well-traveled execution paths that benefit most from regression coverage

### Long-term Architecture
1. **Version and stabilize the public API** — document breaking-change policies for `stats`, `Edge`, `Node`
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

Recent snapshots in reverse chronological order. Δ columns show change vs. the immediately preceding snapshot.

| # | Timestamp | Branch | Version | Nodes | Edges | Coverage | Δ Nodes | Δ Edges | Δ Coverage |
|---|-----------|--------|---------|-------|-------|----------|---------|---------|------------|
| 1 | 2026-04-05 04:43:36 | main | 0.11.0 | 3135 | 3211 | 79.6% | +0 | +0 | +0.0% |
| 2 | 2026-04-05 04:42:52 | main | 0.11.0 | 3135 | 3211 | 79.6% | +0 | +0 | +0.0% |
| 3 | 2026-04-05 04:40:54 | main | 0.11.0 | 3135 | 3211 | 79.6% | +0 | +0 | +0.0% |
| 4 | 2026-04-05 04:39:26 | main | 0.11.0 | 3135 | 3211 | 79.6% | +267 | +233 | -0.4% |
| 5 | 2026-04-05 03:01:00 | main | 0.11.0 | 2868 | 2978 | 80.0% | +4 | -3 | +0.0% |
| 6 | 2026-04-05 01:37:14 | main | 0.11.0 | 2864 | 2981 | 80.0% | +0 | +0 | +0.0% |
| 7 | 2026-04-05 01:36:32 | main | 0.11.0 | 2864 | 2981 | 80.0% | +68 | +73 | +0.2% |
| 8 | 2026-04-05 01:15:09 | main | 0.11.0 | 2796 | 2908 | 79.8% | +0 | +1 | +0.0% |
| 9 | 2026-04-05 01:14:25 | main | 0.11.0 | 2796 | 2907 | 79.8% | +0 | +1 | +0.0% |
| 10 | 2026-04-05 01:13:43 | main | 0.11.0 | 2796 | 2906 | 79.8% | +0 | +0 | +0.0% |


---

## Appendix: Orphaned Code

Functions with zero callers (potential dead code):

| Function | Module | Lines |
|----------|--------|-------|
| `wipe()` | src/agent_kg/index.py | 10 |
| `_init_state()` | src/agent_kg/app.py | 8 |
| `_parse_args()` | src/agent_kg/app.py | 5 |
---

## CodeRank -- Global Structural Importance

Weighted PageRank over CALLS + IMPORTS + INHERITS edges (test paths excluded). Scores are normalized to sum to 1.0. This ranking seeds Phase 2 fan-in discovery and Phase 15 concern queries.

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.002155 | method | `UserProfileStore.get_by_kind` | src/agent_kg/user_profile.py |
| 2 | 0.001738 | method | `AgentKGStore._get_db` | src/agent_kg/store.py |
| 3 | 0.001427 | method | `UserProfileStore._get_db` | src/agent_kg/user_profile.py |
| 4 | 0.001023 | function | `_resolve_kg` | src/agent_kg/cli/main.py |
| 5 | 0.000884 | method | `UserProfileStore._row_to_node` | src/agent_kg/user_profile.py |
| 6 | 0.000592 | method | `AgentKGStore.get_nodes_by_kind` | src/agent_kg/store.py |
| 7 | 0.000568 | function | `_get_spacy_model` | src/agent_kg/nlp/intent.py |
| 8 | 0.000556 | method | `SummarizerConfig.from_env` | src/agent_kg/summarize.py |
| 9 | 0.000548 | method | `AgentKGStore._get_table` | src/agent_kg/store.py |
| 10 | 0.000509 | method | `AgentKGStore._get_embedder` | src/agent_kg/store.py |
| 11 | 0.000491 | method | `AgentKGStore.embed` | src/agent_kg/store.py |
| 12 | 0.000471 | function | `_serve` | src/agent_kg/mcp/server.py |
| 13 | 0.000467 | method | `ConversationIndex._get_db` | src/agent_kg/index.py |
| 14 | 0.000428 | method | `AgentKGStore.upsert_node` | src/agent_kg/store.py |
| 15 | 0.000428 | method | `AgentKGStore.embed_node` | src/agent_kg/store.py |
| 16 | 0.000428 | method | `AgentKG.close_session` | src/agent_kg/graph.py |
| 17 | 0.000403 | method | `UserProfileStore.get_identity` | src/agent_kg/user_profile.py |
| 18 | 0.000402 | method | `UserProfileStore.upsert` | src/agent_kg/user_profile.py |
| 19 | 0.000402 | function | `_try_spacy` | src/agent_kg/nlp/intent.py |
| 20 | 0.000402 | function | `_heuristic_classify` | src/agent_kg/nlp/intent.py |

---

## Concern-Based Hybrid Ranking

Top structurally-dominant nodes per architectural concern (0.60 × semantic + 0.25 × CodeRank + 0.15 × graph proximity).

### Configuration Loading Initialization Setup

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.7817 | method | `SummarizerConfig.from_env` | src/agent_kg/summarize.py |
| 2 | 0.7441 | method | `UserProfileStore.__init__` | src/agent_kg/user_profile.py |
| 3 | 0.7435 | function | `init` | src/agent_kg/cli/main.py |
| 4 | 0.7381 | function | `_load_profile` | src/agent_kg/app.py |
| 5 | 0.7332 | function | `_init_state` | src/agent_kg/app.py |

### Data Persistence Storage Database

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.7308 | method | `AgentKGStore.embed_node` | src/agent_kg/store.py |
| 2 | 0.7251 | function | `consolidate` | src/agent_kg/consolidate.py |
| 3 | 0.7192 | function | `capture` | src/agent_kg/snapshots.py |
| 4 | 0.7187 | function | `prune` | src/agent_kg/prune.py |
| 5 | 0.69 | class | `AgentKGStore` | src/agent_kg/store.py |

### Query Search Retrieval Semantic

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.75 | method | `AgentKG.index` | src/agent_kg/graph.py |
| 2 | 0.7498 | method | `UserProfileStore.search` | src/agent_kg/user_profile.py |
| 3 | 0.7389 | method | `ConversationIndex.search` | src/agent_kg/index.py |
| 4 | 0.7371 | method | `AgentKGStore.search` | src/agent_kg/store.py |
| 5 | 0.7288 | function | `query` | src/agent_kg/query.py |

### Graph Traversal Node Edge

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.7524 | function | `_get_topic_nodes_for_turns` | src/agent_kg/prune.py |
| 2 | 0.7489 | method | `AgentKG.stats` | src/agent_kg/graph.py |
| 3 | 0.7388 | method | `AgentKGStore.refresh_related_to_edges` | src/agent_kg/store.py |
| 4 | 0.736 | method | `AgentKGStore.get_edges` | src/agent_kg/store.py |
| 5 | 0.7279 | function | `_get_entity_nodes_for_turns` | src/agent_kg/prune.py |



---

*Report generated by CodeKG Thorough Analysis Tool — analysis completed in 3.0s*
