> **Analysis Report Metadata**
> - **Generated:** 2026-04-05T00:56:30Z
> - **Version:** code-kg 0.11.0
> - **Commit:** 0457090 (main)
> - **Platform:** macOS 26.4 | arm64 (arm) | Turing | Python 3.12.13
> - **Graph:** 3973 nodes · 5044 edges (431 meaningful)
> - **Included directories:** all
> - **Excluded directories:** none
> - **Elapsed time:** 3s

# agent_kg Analysis

**Generated:** 2026-04-05 00:56:30 UTC

---

## Executive Summary

This report provides a comprehensive architectural analysis of the **agent_kg** repository using CodeKG's knowledge graph. The analysis covers complexity hotspots, module coupling, key call chains, and code quality signals to guide refactoring and architecture decisions.

| Overall Quality | Grade | Score |
|----------------|-------|-------|
| [B] **Good** | **B** | 80 / 100 |

---

## Baseline Metrics

| Metric | Value |
|--------|-------|
| **Total Nodes** | 3973 |
| **Total Edges** | 5044 |
| **Modules** | 36 (of 36 total) |
| **Functions** | 90 |
| **Classes** | 49 |
| **Methods** | 256 |

### Edge Distribution

| Relationship Type | Count |
|-------------------|-------|
| CALLS | 1285 |
| CONTAINS | 395 |
| IMPORTS | 221 |
| ATTR_ACCESS | 1218 |
| INHERITS | 4 |

---

## Fan-In Ranking

Most-called functions are potential bottlenecks or core functionality. These functions are heavily depended upon across the codebase.

| # | Function | Module | Callers |
|---|----------|--------|---------|
| 1 | `close()` | src/agent_kg/graph.py | **28** |
| 2 | `_get_db()` | src/agent_kg/store.py | **16** |
| 3 | `upsert_node()` | src/agent_kg/store.py | **15** |
| 4 | `upsert()` | src/agent_kg/profile.py | **15** |
| 5 | `get_nodes_by_kind()` | src/agent_kg/store.py | **11** |
| 6 | `_heuristic_classify()` | src/agent_kg/nlp/intent.py | **11** |
| 7 | `add_edge()` | src/agent_kg/store.py | **11** |
| 8 | `stats()` | src/agent_kg/cli/main.py | **11** |
| 9 | `stats()` | src/agent_kg/graph.py | **11** |
| 10 | `get_by_kind()` | src/agent_kg/profile.py | **10** |
| 11 | `_resolve_kg()` | src/agent_kg/cli/main.py | **10** |
| 12 | `get_node()` | src/agent_kg/store.py | **9** |
| 13 | `search()` | src/agent_kg/index.py | **8** |
| 14 | `add()` | src/agent_kg/index.py | **7** |
| 15 | `should_consolidate()` | src/agent_kg/consolidate.py | **6** |


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
| `tests/test_nlp.py` | 0 | 5 | 0 | 5 | 0.83 |
| `tests/test_schema.py` | 0 | 7 | 0 | 1 | 0.50 |
| `tests/test_ingest.py` | 3 | 7 | 0 | 4 | 0.80 |
| `src/agent_kg/store.py` | 2 | 1 | 8 | 1 | 0.10 |
| `tests/test_store.py` | 1 | 4 | 0 | 2 | 0.67 |
| `tests/test_snapshots.py` | 2 | 3 | 0 | 3 | 0.75 |
| `tests/test_profile.py` | 1 | 4 | 0 | 2 | 0.67 |
| `src/agent_kg/graph.py` | 0 | 1 | 4 | 12 | 0.71 |
| `src/agent_kg/profile.py` | 1 | 1 | 3 | 1 | 0.20 |
| `src/agent_kg/cli/main.py` | 17 | 0 | 0 | 1 | 0.50 |

---

## Key Call Chains

Deepest call chains in the codebase.

**Chain 1** (depth: 3)

```
store → close → close_session
```

---

## Public API Surface

Identified public APIs (module-level functions with high usage).

| Function | Module | Fan-In | Type |
|----------|--------|--------|------|
| `Node()` | src/agent_kg/schema.py | 24 | class |
| `capture()` | src/agent_kg/snapshots.py | 14 | function |
| `Edge()` | src/agent_kg/schema.py | 12 | class |
| `stats()` | src/agent_kg/cli/main.py | 11 | function |
| `extract_preferences()` | src/agent_kg/nlp/preferences.py | 10 | function |
| `extract_entities()` | src/agent_kg/nlp/entities.py | 9 | function |
| `extract_topics()` | src/agent_kg/nlp/topics.py | 8 | function |
| `AgentKGStore()` | src/agent_kg/store.py | 6 | class |
| `should_consolidate()` | src/agent_kg/consolidate.py | 6 | function |
| `classify_intent()` | src/agent_kg/nlp/intent.py | 5 | function |
---

## Docstring Coverage

Docstring coverage directly determines semantic retrieval quality. Nodes without
docstrings embed only structured identifiers (`KIND/NAME/QUALNAME/MODULE`), where
keyword search is as effective as vector embeddings. The semantic model earns its
value only when a docstring is present.

| Kind | Documented | Total | Coverage |
|------|-----------|-------|----------|
| `function` | 68 | 90 | [WARN] 75.6% |
| `method` | 238 | 256 | [OK] 93.0% |
| `class` | 49 | 49 | [OK] 100.0% |
| `module` | 34 | 36 | [OK] 94.4% |
| **total** | **389** | **431** | **[OK] 90.3%** |

---

## Structural Importance Ranking (SIR)

Weighted PageRank aggregated by module — reveals architectural spine. Cross-module edges boosted 1.5×; private symbols penalized 0.85×. Node-level detail: `codekg centrality --top 25`

| Rank | Score | Members | Module |
|------|-------|---------|--------|
| 1 | 0.206026 | 31 | `src/agent_kg/store.py` |
| 2 | 0.128132 | 14 | `src/agent_kg/schema.py` |
| 3 | 0.090179 | 19 | `src/agent_kg/profile.py` |
| 4 | 0.047691 | 33 | `tests/test_ingest.py` |
| 5 | 0.042838 | 44 | `tests/test_nlp.py` |
| 6 | 0.041601 | 20 | `src/agent_kg/graph.py` |
| 7 | 0.040368 | 39 | `tests/test_schema.py` |
| 8 | 0.038801 | 9 | `src/agent_kg/index.py` |
| 9 | 0.037453 | 10 | `src/agent_kg/session.py` |
| 10 | 0.036152 | 6 | `src/agent_kg/nlp/intent.py` |
| 11 | 0.030660 | 31 | `tests/test_store.py` |
| 12 | 0.027661 | 8 | `src/agent_kg/ingest.py` |
| 13 | 0.024515 | 25 | `tests/test_snapshots.py` |
| 14 | 0.023894 | 23 | `tests/test_profile.py` |
| 15 | 0.020802 | 18 | `src/agent_kg/cli/main.py` |



---

## Code Quality Issues

- [WARN] 5 orphaned functions found (`test_delete_nonexistent_is_safe`, `wipe`, `_parse_args`, `TestNodeCRUD`, `TestSessionPersistence`) -- consider archiving or documenting

---

## Architectural Strengths

- Well-structured with 15 core functions identified
- No god objects or god functions detected
- Good docstring coverage: 90.3% of functions/methods/classes/modules documented

---

## Recommendations

### Immediate Actions
1. **Remove or archive orphaned functions** — `test_delete_nonexistent_is_safe`, `wipe`, `_parse_args`, `TestNodeCRUD`, `TestSessionPersistence` have zero callers and add maintenance burden

### Medium-term Refactoring
1. **Harden high fan-in functions** — `close`, `_get_db`, `upsert_node` are widely depended upon; review for thread safety, clear contracts, and stable interfaces
2. **Reduce module coupling** — consider splitting tightly coupled modules or introducing interface boundaries
3. **Add tests for key call chains** — the identified call chains represent well-traveled execution paths that benefit most from regression coverage

### Long-term Architecture
1. **Version and stabilize the public API** — document breaking-change policies for `Node`, `capture`, `Edge`
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
| 1 | 2026-04-04 22:00:05 | main | 0.11.0 | 3460 | 4587 | 91.3% | +0 | +0 | +0.0% |
| 2 | 2026-04-04 21:59:23 | main | 0.11.0 | 3460 | 4587 | 91.3% | +1 | +1 | +0.0% |
| 3 | 2026-04-04 20:53:31 | main | 0.11.0 | 3459 | 4586 | 91.3% | -1 | -5 | +0.0% |
| 4 | 2026-04-04 20:52:12 | main | 0.11.0 | 3460 | 4591 | 91.3% | — | — | — |


---

## Appendix: Orphaned Code

Functions with zero callers (potential dead code):

| Function | Module | Lines |
|----------|--------|-------|
| `TestNodeCRUD()` | tests/test_store.py | 91 |
| `TestSessionPersistence()` | tests/test_session.py | 30 |
| `wipe()` | src/agent_kg/index.py | 10 |
| `_parse_args()` | src/agent_kg/app.py | 5 |
| `test_delete_nonexistent_is_safe()` | tests/test_store.py | 2 |
---

## CodeRank -- Global Structural Importance

Weighted PageRank over CALLS + IMPORTS + INHERITS edges (test paths excluded). Scores are normalized to sum to 1.0. This ranking seeds Phase 2 fan-in discovery and Phase 15 concern queries.

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.002168 | method | `UserProfileStore.get_by_kind` | src/agent_kg/profile.py |
| 2 | 0.001922 | method | `AgentKGStore._get_db` | src/agent_kg/store.py |
| 3 | 0.001062 | method | `UserProfileStore._get_db` | src/agent_kg/profile.py |
| 4 | 0.001039 | function | `_resolve_kg` | src/agent_kg/cli/main.py |
| 5 | 0.000921 | method | `UserProfileStore._row_to_node` | src/agent_kg/profile.py |
| 6 | 0.000655 | method | `AgentKGStore.get_nodes_by_kind` | src/agent_kg/store.py |
| 7 | 0.000628 | function | `_get_spacy_model` | src/agent_kg/nlp/intent.py |
| 8 | 0.000614 | method | `SummarizerConfig.from_env` | src/agent_kg/summarize.py |
| 9 | 0.000606 | method | `AgentKGStore._get_table` | src/agent_kg/store.py |
| 10 | 0.000563 | method | `AgentKGStore._get_embedder` | src/agent_kg/store.py |
| 11 | 0.000543 | method | `AgentKGStore.embed` | src/agent_kg/store.py |
| 12 | 0.000520 | function | `_serve` | src/agent_kg/mcp/server.py |
| 13 | 0.000516 | method | `ConversationIndex._get_db` | src/agent_kg/index.py |
| 14 | 0.000473 | method | `AgentKGStore.upsert_node` | src/agent_kg/store.py |
| 15 | 0.000473 | method | `AgentKGStore.embed_node` | src/agent_kg/store.py |
| 16 | 0.000473 | method | `AgentKG.close_session` | src/agent_kg/graph.py |
| 17 | 0.000445 | method | `UserProfileStore.upsert` | src/agent_kg/profile.py |
| 18 | 0.000445 | function | `_try_spacy` | src/agent_kg/nlp/intent.py |
| 19 | 0.000445 | function | `_heuristic_classify` | src/agent_kg/nlp/intent.py |
| 20 | 0.000445 | function | `_spacy_topics` | src/agent_kg/nlp/topics.py |

---

## Concern-Based Hybrid Ranking

Top structurally-dominant nodes per architectural concern (0.60 × semantic + 0.25 × CodeRank + 0.15 × graph proximity).

### Configuration Loading Initialization Setup

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.786 | method | `SummarizerConfig.from_env` | src/agent_kg/summarize.py |
| 2 | 0.7493 | method | `UserProfileStore.__init__` | src/agent_kg/profile.py |
| 3 | 0.7429 | function | `init` | src/agent_kg/cli/main.py |
| 4 | 0.7388 | function | `_load_profile` | src/agent_kg/app.py |
| 5 | 0.7319 | method | `AgentKGStore.__init__` | src/agent_kg/store.py |

### Data Persistence Storage Database

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.7246 | function | `consolidate` | src/agent_kg/consolidate.py |
| 2 | 0.7186 | function | `capture` | src/agent_kg/snapshots.py |
| 3 | 0.7181 | function | `prune` | src/agent_kg/prune.py |
| 4 | 0.69 | class | `AgentKGStore` | src/agent_kg/store.py |
| 5 | 0.6677 | class | `Session` | src/agent_kg/session.py |

### Query Search Retrieval Semantic

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.75 | function | `query` | src/agent_kg/cli/main.py |
| 2 | 0.7442 | method | `AgentKG.index` | src/agent_kg/graph.py |
| 3 | 0.7331 | method | `ConversationIndex.search` | src/agent_kg/index.py |
| 4 | 0.733 | method | `AgentKGStore.search` | src/agent_kg/store.py |
| 5 | 0.7231 | function | `query` | src/agent_kg/query.py |

### Graph Traversal Node Edge

| Rank | Score | Kind | Name | Module |
|------|-------|------|------|--------|
| 1 | 0.7528 | function | `_get_topic_nodes_for_turns` | src/agent_kg/prune.py |
| 2 | 0.7489 | method | `AgentKG.stats` | src/agent_kg/graph.py |
| 3 | 0.7396 | method | `AgentKGStore.refresh_related_to_edges` | src/agent_kg/store.py |
| 4 | 0.7355 | method | `AgentKGStore.get_edges` | src/agent_kg/store.py |
| 5 | 0.2401 | method | `AgentKGStore._get_db` | src/agent_kg/store.py |



---

*Report generated by CodeKG Thorough Analysis Tool — analysis completed in 3.2s*
