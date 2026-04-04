# Structural Importance Ranking (SIR) for CodeKG

Author: Eric G. Suchanek, PhD  
Project: CodeKG  
Repository: https://github.com/flux-frontiers/code_kg

## Overview

This document describes a deterministic algorithm for computing **structural importance scores** for nodes in a CodeKG knowledge graph.

The algorithm is called **Structural Importance Ranking (SIR)**.

Its purpose is to identify the architectural core of a codebase:

- most important functions
- most important classes
- most important modules
- framework-like abstractions
- widely reused utilities

Unlike embedding-based approaches, SIR relies entirely on the structural dependency graph produced by CodeKG. This makes the result deterministic, explainable, reproducible, and independent of LLM heuristics.

## Why this fits CodeKG

CodeKG already builds a deterministic static graph in SQLite, stores typed structural edges, and adds post-build `RESOLVES_TO` edges for symbol resolution. The repository README describes CodeKG as a deterministic, explainable knowledge graph built from AST structure in SQLite, with post-build symbol resolution and a Click-based CLI. citeturn438305view0turn820418view3turn591393view1

SIR therefore belongs **after** symbol resolution and **before or alongside** downstream retrieval/indexing.

## Conceptual Model

CodeKG builds a directed multigraph:

```text
G = (V, E)
```

Where:

- `V` = nodes (`module`, `class`, `function`, `method`)
- `E` = typed edges representing relationships

Relevant edge types include:

- `CALLS`
- `IMPORTS`
- `INHERITS`
- `CONTAINS`
- `RESOLVES_TO`

Each structural edge indicates that the **source node depends on the target node**.

Example:

```text
function_a CALLS function_b
```

Meaning:

```text
function_a -> function_b
```

Thus importance flows from dependent nodes to dependencies.

## Effective Graph Construction

Before computing importance, normalize the graph.

### Step 1: Resolve symbol stubs

CodeKG can emit edges like:

```text
f -> sym:Foo
sym:Foo -> g  (RESOLVES_TO)
```

Rewrite these as:

```text
f -> g
```

Symbol nodes should not appear in the final scoring graph.

### Step 2: Filter node kinds

Only structural entities should receive scores:

- `module`
- `class`
- `function`
- `method`

### Step 3: Select relations

Version 1 of SIR uses:

- `CALLS`
- `INHERITS`
- `IMPORTS`
- `CONTAINS`

## Edge weighting

Default weights:

```text
CALLS    = 1.00
INHERITS = 0.80
IMPORTS  = 0.45
CONTAINS = 0.15
```

Rationale:

- `CALLS`: direct runtime dependency
- `INHERITS`: strong architectural dependence
- `IMPORTS`: weaker than actual invocation
- `CONTAINS`: light propagation between module/class and member nodes

## Cross-module boost

Dependencies across modules usually signal more reusable architecture than local helper chatter.

Define:

```text
m(u,v) = 1.0  if module(u) == module(v)
m(u,v) = 1.5  if module(u) != module(v)
```

Then:

```text
w'(u,v) = w(u,v) * m(u,v)
```

## Weighted PageRank

Let:

```text
Z_u = sum of outgoing weights from node u
```

Compute weighted PageRank:

```text
PR(v) = (1 - d)/|V| + d * Σ [ PR(u) * w(u,v) / Z_u ]
```

where `d = 0.85`.

Interpretation: a node becomes important if many nodes depend on it, especially if those nodes are themselves important.

## Private-symbol penalty

Private helpers often rank too highly in local clusters. Apply a mild penalty after convergence:

```text
score(v) = 0.85 * PR(v)   if name starts with _ or __
```

## Module-level aggregation

Module importance can be derived from member importance:

```text
M(m) = Σ α(kind(v)) * score(v)
```

Suggested weights:

```text
α(function) = 1.0
α(method)   = 1.0
α(class)    = 1.2
```

## Explanation mechanism

To keep results auditable, decompose inbound contributions:

```text
contrib(u -> v) = PR(u) * w(u,v) / Z_u
```

For each node you can report:

- strongest inbound contributors
- number of callers/importers/inheritors
- cross-module vs same-module support
- relation-type breakdown

## Recommended CLI

```bash
codekg centrality --repo .
codekg centrality --repo . --kind function
codekg centrality --repo . --kind module
codekg centrality --repo . --top 50
codekg centrality --repo . --json
codekg centrality --repo . --write-db
```

## Suggested persistence table

```sql
CREATE TABLE IF NOT EXISTS centrality_scores (
    node_id TEXT NOT NULL,
    metric TEXT NOT NULL,
    score REAL NOT NULL,
    rank INTEGER,
    computed_at TEXT NOT NULL,
    params_json TEXT NOT NULL,
    PRIMARY KEY (node_id, metric)
);
```

## Integration point

Recommended pipeline:

```text
AST parse
  -> SQLite graph
  -> symbol resolution
  -> SIR centrality
  -> semantic indexing / query-time usage
```

The post-build `RESOLVES_TO` phase already exists in `GraphStore.resolve_symbols()`, so SIR should operate on the resolved store rather than the raw AST output. citeturn591393view1

## Summary

Structural Importance Ranking (SIR) gives CodeKG a deterministic and explainable centrality layer over the existing structural graph. It identifies components that matter because **many important parts of the system rely on them**.
