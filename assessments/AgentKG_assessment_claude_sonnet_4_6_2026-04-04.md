# AgentKG Assessment

**Model:** claude-sonnet-4-6
**Date:** 2026-04-04
**Repo:** /Users/egs/repos/agent_kg
**Person:** egs

---

## Executive Summary

AgentKG delivers on its core promise — persistent conversational memory that survives
context resets — but the current build has significant rough edges that limit its
utility for production use. The `assemble` command is genuinely useful and produces
well-formatted, token-budgeted context blocks that beat manual history scrolling. The
global user profile is well-populated and accurate. However, semantic search scores are
weak (max 0.31), topic extraction is polluted by noise from system/IDE context tags
ingested verbatim, entity extraction misclassifies file paths and stopwords, and the
LanceDB index starts empty because hooks use `--no-embed` — making `query` return
nothing until embeddings are explicitly generated.

The session model fragments severely in practice: this repo accumulated 36 sessions with
mostly 1 turn each, because every new hook invocation creates a new session. This
prevents the cross-session memory narrative from being exercised meaningfully. Pruning
couldn't be triggered (no cold turns), so that path remains unverified.

With targeted fixes to topic/entity extraction, embedding coverage, and session
continuity, AgentKG would be a meaningfully useful tool. As of this build it is a
solid prototype.

---

## Tool-by-Tool Evaluation

| Tool | Score | Notes |
|------|-------|-------|
| `agent-kg-stats` | 5/5 | Clean, fast, informative. Good first-look output. |
| `agent-kg-sessions` | 3/5 | Shows sessions correctly but the 1-turn-per-session fragmentation makes the list noisy and hard to read. |
| `agent-kg-analyze` | 4/5 | Full Markdown report is well-structured and LLM-ready. Profile section surfaced correctly. |
| `agent-kg-profile` | 4/5 | Good content, confidence scores, clean format. Two malformed preference entries (raw conversation fragments ingested as preferences). |
| `agent-kg-query` | 2/5 | Starts empty (LanceDB has 0 rows after hook-only ingestion). After manual embedding: precise query scores 0.189 (weak), broad query returns only topic nodes not turns, preference query returns all 0.000. Score range too compressed to discriminate well. |
| `agent-kg-assemble` | 4/5 | Best tool in the suite. Blends semantic relevance + recency into a clean, token-budgeted block. Format is LLM-ready. Reliable even when embeddings are sparse. |
| `agent-kg-ingest` | 4/5 | Works correctly. Ingestion output (topics/entities/tasks found) is informative. |
| `agent-kg-snapshot` | 4/5 | Lightweight JSON, correct metadata, clean output. Only 1 snapshot captured so diff couldn't be tested. |
| `agent-kg-prune` | N/A | Could not trigger — "Not enough cold turns to prune yet" even at `--window 5`. All turns are recent/active. Cannot assess summary quality. |

---

## Scorecard

| Dimension | Score | Justification |
|-----------|-------|---------------|
| **Recall Accuracy** | 3/5 | Precise queries find the right turn at rank #1. Broad and preference queries fail or return only topic nodes. |
| **Recall Relevance** | 2/5 | Score range 0.000–0.189 for turns. Compressed, non-discriminating. Topics swamp results at score=0. |
| **Extraction Quality** | 2/5 | Topics are bigram noise, heavily duplicated (e.g. "file users" ×7, "file" ×7 from IDE context tags). Entities extract file paths and "just". Intent categories too coarse (10/21 classified as "context"). |
| **Profile Utility** | 4/5 | Preferences, expertise, interests, commitments, and style are all present and mostly accurate. Malformed entries are minor. Cross-repo accumulation confirmed. |
| **Prune Safety** | N/A | Could not trigger. No cold turns available in this young graph. |
| **Efficiency vs. Baseline** | 4/5 | `assemble` is genuinely faster and more relevant than scrolling history or relying on system prompts. The format drops directly into a prompt. |
| **Snapshot Usefulness** | 3/5 | Works correctly, clean JSON. Too lightweight — no node payload for recovery. Single snapshot means no diff insight. |
| **Usability** | 4/5 | CLI is clean with sensible defaults (OS username, `--repo .`). Output is readable. The `--no-embed` hook footgun is the main usability hazard. |
| **Cross-Session Value** | 2/5 | Profile is cross-session. Turn memory is technically persistent but session fragmentation (36 sessions, 1 turn each) defeats the purpose — there's nothing coherent to recall across sessions. |

**Overall: 3.1 / 5**

---

## Comparison to Default Workflow

Without AgentKG: rely on in-context history (truncates at ~200k tokens), manually
maintained CLAUDE.md notes (static, not searchable), or re-explaining context each
session.

With AgentKG: `assemble` gives a structured, token-budgeted context block that includes
both semantically relevant past turns and recent conversation. For questions like "what
did we decide about X?" it is materially better than any manual alternative. The profile
is the most immediately useful component — it correctly captures `egs`'s preferences,
expertise, and style without any manual curation.

The gap is that `query` doesn't yet deliver on its promise. If it worked reliably (full
embeddings + better extraction), AgentKG would be a significant force multiplier.

---

## Extraction Quality Analysis

**Topics:** N-gram bigrams dominate. The biggest problem is verbatim ingestion of
`<ide_opened_file>` system tags, which generate topics like "file users", "users repos",
"opened file", "file" (×7) — noise that swamps real signal. No deduplication: identical
bigrams appear 7 times each as separate nodes.

**Entities:** Extracting file paths
(`/Users/egs/repos/agent_kg/assessments/AssessmentProtocol_CodeKG.md`) as entities,
with duplicates. The word "just" extracted as an entity. Real named entities (FastMCP,
LanceDB, SQLite, agent_kg, CodeKG) not extracted at all.

**Intents:** Four categories: `context` (10), `unknown` (7), `question` (3),
`confirmation` (1). "context" is too broad — it catches most assistant turns. "unknown"
at 33% is high. The category set isn't well-matched to a coding assistant context.

---

## Strengths

1. **`assemble` works.** The blended semantic+recency context block is well-designed and immediately useful.
2. **User profile is accurate.** Preferences, commitments, expertise, and style populated correctly without manual intervention.
3. **Clean CLI.** Intuitive flags, good defaults, informative ingestion output.
4. **Snapshot captures meaningful metrics.** Node/edge/turn counts plus kind breakdown give a clear point-in-time picture.
5. **Architecture is sound.** SQLite + LanceDB hybrid is the right foundation. The graph model (turn → topic/entity/intent edges) is well-conceived.

---

## Weaknesses & Suggestions

1. **`--no-embed` hook default leaves semantic search dead.** Hooks use `--no-embed` for speed, so LanceDB starts at 0 rows. Either run a consolidation pass on startup, or embed asynchronously after ingestion. A `agent-kg-consolidate` command run periodically would fix this.

2. **System/IDE context tags pollute extraction.** `<ide_opened_file>` and session-end markers are ingested verbatim and generate dozens of junk topics. Pre-process or strip known system tags before extraction.

3. **Topic deduplication missing.** The same bigram appears 7 times as separate nodes. Topics should be upserted (merge duplicate labels), not inserted fresh each time.

4. **Entity extraction is shallow.** Needs NER that recognizes tools, libraries, commands, and proper nouns. File paths should either be normalized or excluded. Stopwords ("just") should be filtered.

5. **Session fragmentation.** 36 sessions with 1 turn each defeats cross-session memory. The hook should resume the current session (or a configurable recent session) rather than creating a new one on every invocation.

6. **Recall score compression.** Max observed score 0.189 for a directly relevant turn. Either the embedding model is undersized for this domain, or the vector index needs more turns to calibrate. Consider domain-adapted embeddings.

7. **Snapshot too lightweight.** At 372 bytes with no node payloads, it can't be used for actual recovery. A `--full` flag that serializes all nodes would make snapshots genuinely restorable.

---

## Overall Verdict

**3.1 / 5 — Promising prototype, not yet production-ready.**

AgentKG is worth using now for the profile and `assemble` features alone. The
architectural foundation is correct and the vision is compelling. But the three critical
gaps — dead embeddings by default, noisy extraction, and session fragmentation — need to
be fixed before it delivers on the cross-session memory promise.

**Recommended for:** Projects where the user profile and `assemble`-based context
injection are the primary use cases. Particularly valuable for agents that need to
"remember" user preferences and coding style across sessions.

**Not yet reliable for:** Precise semantic recall of specific past decisions, or any
workflow that depends on `query` returning discriminating scores.
