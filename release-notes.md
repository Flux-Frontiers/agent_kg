# Release Notes — v0.8.0

> Released: 2026-07-29

AgentKG's vector store moves off LanceDB and onto sqlite-vec. Embeddings now live in a single `.agentkg/vectors.sqlite` file rather than a `.agentkg/lancedb/` directory, which makes a conversation graph two files instead of a file plus a directory tree — easier to back up, copy between machines, and reason about. This is a breaking change and existing installs need one migration step, described under Upgrading.

## What changed

**A single-file vector store.** The `AgentKGStore` and `ConversationIndex` constructors now take a `vectors_path` naming a file, replacing the `lancedb_dir` directory parameter, and `ConversationGraph` derives the path internally. Search results are unaffected: the old store already queried with an explicit cosine metric and sqlite-vec reports cosine distance, so the similarity conversion carries over untouched — verified against a same-day LanceDB control across all 620 live nodes, with identical ranking *and* identical scores on four real queries. The one deliberate difference is that `ConversationIndex.search()` returns a raw distance that is now cosine rather than L2, since that path previously ran without an explicit metric.

**Embedding is no longer deferred.** Two bugs meant parts of the graph were silently unsearchable. Intent nodes were written to SQLite with no embedding call at all, so semantic search could never surface them. Separately, the `Stop` hook skipped embedding for speed and leaned on a consolidation pass to catch up — but that pass covered only four node kinds, was scoped to the current session, and re-embedded everything each run instead of just what was missing, so any node from an earlier session or of an uncovered kind stayed unembedded forever. Measured across the fleet before the fix, every `.agentkg` index had drifted from its SQLite source — between 15% and 100% of nodes missing. Ingestion now embeds inline, and the new `agentkg reindex` command backfills anything that drifts, with a `--check` mode that reports drift and exits non-zero without writing.

**Leaner dependency resolution.** The `kgdeps` extra is gone and `doc-kg` / `pycode-kg` are no longer declared as dependencies. AgentKG never imported either package, so the extra bought nothing at runtime — but declaring them forced Poetry to reconcile the `transformers` pin of every published sibling against this project's own, a deadlock given that doc-kg and pycode-kg depend on each other. Removing them drops 259 lines from the lock file and lets the `transformers` constraint sit where `kgmodule-utils` actually wants it. This mirrors a change already made in doc_kg and pycode_kg.

## Upgrading

Delete the old `.agentkg/lancedb/` directory and re-embed. SQLite remains the source of truth for conversation data, so nodes are rebuilt from it and nothing is lost — run `agentkg reindex` to repopulate the vector index, or `agentkg reindex --check` first if you want to see the drift before writing. Because earlier versions could leave intents and older-session nodes unembedded, a reindex on an existing corpus will likely find more missing entries than the migration alone accounts for; that is expected, and is the bug being fixed.

If you use the cross-KG integrations, install them directly — `pip install doc-kg pycode-kg` — as `pip install "agent-kg[kgdeps]"` no longer exists. Note that `lancedb` may still arrive transitively through `kgmodule-utils[semantic]` until that package splits its extras; AgentKG itself no longer uses it.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
