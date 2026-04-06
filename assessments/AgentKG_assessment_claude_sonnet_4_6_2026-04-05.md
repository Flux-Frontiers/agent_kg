# AgentKG Assessment — claude_sonnet_4_6 — 2026-04-05

**Assessor:** claude-sonnet-4-6
**Date:** 2026-04-05
**Repo:** `/Users/egs/repos/agent_kg` (self-assessment — tool evaluating memory of its own build session)
**Person:** `egs`
**Graph state at assessment:** 360 nodes, 499 edges, 59 turns, 1 session

---

## 1. Executive Summary

AgentKG's core value proposition — persisting conversational memory as a queryable knowledge graph across sessions — is architecturally sound and the hook-based ingestion pipeline works reliably. The `UserPromptSubmit` and `Stop` hooks fire correctly per-interaction, turns accumulate, and the repo-independent user profile persists commitments, expertise, and style across projects. For its target use case, the infrastructure is operational.

However, several subsystems have meaningful deficiencies that limit practical utility. The `agent-kg analyze` command crashes with an unhandled slice error. Entity extraction is noisy (capturing `pre`, `both`, `all`, `~0.5s` as entities) and lacks deduplication (`.claude/settings.json` and `UserProfileStore` each appear twice). Topic extraction produces sequential bigram windows rather than semantic topics — 224 topic nodes for 59 turns, nearly all of the form `"clean nodes"`, `"nodes turns"`, `"turns fresh"`. Pruning with `--force` on a 59-turn graph produces zero results. The `assemble` output duplicates every entry. Most critically, semantic recall scores for precise queries are very low (max 0.162 for "MCP server architecture") — meaning a new agent session would get poor retrieval quality on the most important use case.

The snapshot system stores lightweight metrics-only JSON, not restorable content — the name is misleading. The profile is the strongest feature and accumulates correctly across projects. AgentKG is a promising v0.4 with the right architecture and several fixable implementation gaps.

---

## 2. Tool-by-Tool Evaluation

### `agent-kg stats`
**Rating: 4/5**
Fast, clean, correctly reports node/edge counts by kind. One discrepancy: `sessions` reported 62 turns while `stats` reported 59 (unexplained 3-turn gap).

### `agent-kg sessions`
**Rating: 3/5**
Correctly identifies 1 session with start time and prune count. Turn count mismatch with `stats` (62 vs 59) is unexplained. No session-level summaries or topic breakdowns.

### `agent-kg analyze`
**Rating: 1/5**
**Crashed.** Full output:
```
Analysis failed: slice(None, 5, None)
```
Unhandled exception — likely `pandas` or `numpy` slice on an empty or misshapen dataframe in the topic analysis path. This is the highest-value diagnostic command in the protocol and it fails completely. No graceful degradation.

### `agent-kg profile`
**Rating: 3/5**
Profile is populated and repo-independent (stored at `~/.kgrag/profiles/egs/`). The `--person egs` flag works. Profile DB contains: commitment(4), context(4), expertise(1), interest(2), style(1). The `:param:` style entry is correct.

Problems:
- Commitment nodes contain truncated mid-sentence text: `"always use embeddings! fix that! i did run prune. finally, we need you to accumu"` — the extractor cuts at an arbitrary character limit rather than at a sentence boundary.
- No identity name/email stored despite the schema supporting them.
- No `preference` nodes exist despite the kind being defined.

### `agent-kg query`
**Rating: 2/5**
Precise queries ("MCP server architecture") returned max score 0.162 with no turns in top 8 — only topic nodes. This is the core recall function and it is not working for the primary use case. Broad queries ("error handling") performed better (score 0.572) but still returned topic nodes, not the actual turns. The `--include-profile` flag correctly surfaces `:param:` at rank 1 for preference queries — this is the strongest single feature of `query`. Fundamental issue: assistant turns are ingested with `--no-embed`, leaving half the corpus without embeddings.

### `agent-kg assemble`
**Rating: 2/5**
Produces a token-budgeted Markdown block (~1054 tokens) with Compressed/Relevant Turns/Active Topics/Recent Conversation sections. Structure is correct. Two problems: (1) every turn appears **twice** in the output — a join or grouping bug; (2) the Compressed section contains raw mypy error dump text from hook-captured CLI output rather than semantic summaries of work done.

### `agent-kg snapshot`
**Rating: 2/5**
Snapshots trigger reliably (Stop hook auto-fires one per interaction — 20 snapshots in one session). Format is metrics-only JSON:
```json
{
  "node_count": 360, "edge_count": 499, "turn_count": 59, ...
}
```
No content. Not restorable. Cannot diff two snapshots. The per-response trigger cadence creates clutter — 20 snapshots in one session is excessive. Name implies recovery capability that doesn't exist.

### `agent-kg prune`
**Rating: 1/5**
Running `agent-kg prune --window 20 --repo . --force` on a 59-turn graph produced:
```
Summaries created: 0 | Turns pruned: 0 | Nodes removed: 0 | Token savings ~0
```
With `--force` and window=20 on 59 turns, 39 turns should have been candidates. Prune appears to require turns from prior closed sessions even with `--force`. This is the most critical usability gap: pruning is non-functional for any single-session scenario, which includes the common case of a long uninterrupted work session.

### `agent-kg ingest` (via hooks)
**Rating: 4/5**
Hook-based auto-ingestion works well. Both `UserPromptSubmit` and `Stop` hooks fire reliably per-interaction. The `--no-embed` optimization on assistant turns is sensible for throughput but leaves assistant content unsearchable via vector similarity.

---

## 3. Scorecard

| Dimension | Score | Justification |
|---|---|---|
| **Recall Accuracy** | 2/5 | Precise queries score ≤ 0.162; topic nodes returned instead of relevant turns; assistant turns have no embeddings |
| **Recall Relevance** | 3/5 | Score spread exists (0.162–0.572); `--include-profile` correctly surfaces profile nodes; broad queries work better than precise ones |
| **Extraction Quality** | 2/5 | Bigram topics (224 for 59 turns); noisy entities (`pre`, `both`, `~0.5s`); deduplication broken; commitment text truncated |
| **Profile Utility** | 3/5 | Repo-independent, persists across sessions, captures style/expertise correctly; commitments truncated; no preferences; no identity fields populated |
| **Prune Safety** | 1/5 | Zero turns pruned with `--force` on 59-turn graph; completely non-functional for single-session repos |
| **Efficiency vs. Baseline** | 3/5 | Profile retrieval is genuinely faster than re-stating preferences; conversation recall below threshold for practical use |
| **Snapshot Usefulness** | 2/5 | Metrics log only; not restorable; triggered too frequently; name misleads on capability |
| **Usability** | 3/5 | CLI flags consistent; `analyze` crash; duplicate entries in `assemble`; turn count inconsistency; unhelpful prune error |
| **Cross-Session Value** | 3/5 | Profile accumulation is the strongest cross-session feature; turn recall across sessions untestable in this single-session run |

**Aggregate: 22/45 (49%)**

---

## 4. Comparison to Default Workflow

Without AgentKG, an agent has: in-context history (truncates at window limit), no cross-session memory, and only what the user re-states.

AgentKG adds:
- **Profile persistence** (clearest win): `:param:` style, expertise, commitments survive context resets and are repo-independent. This works.
- **Turn history beyond context window**: theoretically. In practice, recall scores of 0.162 for precise queries mean the retrieval is not reliably surfacing the most relevant past turns.
- **Session continuity metadata**: knowing turn count, session ID, and graph size is useful for agent self-orientation.

Honest comparison: **profile recall adds clear, immediate value**; **turn recall at current quality is not trustworthy enough to rely on over in-context history**. AgentKG currently functions better as a profile manager than as a full conversation memory system.

---

## 5. Extraction Quality Analysis

### Topics
224 topic nodes for 59 turns (~3.8/turn). These are **sequential bigram windows** across raw text, not semantic topics. Examples from live extraction:
```
"clean nodes" | "nodes turns" | "turns fresh" | "fresh session" | "session profile"
```
These come from sliding a 2-gram window over `"clean nodes turns fresh session profile untouched"`. The approach generates high-volume, low-quality noise. A topic extractor should use TF-IDF, RAKE, or YAKE to surface key phrases, or at minimum filter against a stoplist.

### Entities
17 entities for 59 turns. Mixed quality:
- Useful: `LanceDB`, `UserProfileStore`, `UserPromptSubmit`, `AssessmentProtocol_AgentKG`
- Noisy: `pre`, `both`, `all`, `~0.5s` — stopwords and measurement strings
- Broken deduplication: `.claude/settings.json` appears twice, `UserProfileStore` appears twice with identical labels

### Intents
Distribution: `context(17)`, `unknown(14)`, `confirmation(11)`, `correction(10)`, `question(7)`. Categories are reasonable for a coding assistant. `unknown` at 24% is high. `correction` at 17% correctly reflects this debugging session. Intent classification is the most reliable extraction subsystem.

---

## 6. Strengths

1. **Hook architecture is clean and zero-friction.** `UserPromptSubmit` + `Stop` auto-ingestion works reliably per-interaction with no manual overhead.
2. **Repo-independent profile is the strongest feature.** `~/.kgrag/profiles/egs/` accumulates across all projects. Style, expertise, and interests are correctly captured.
3. **`--include-profile` integration.** Blending profile nodes into query results is well-designed; `:param:` style surfaced at rank 1.
4. **Token-budgeted `assemble` pattern** is the right interface for LLM context injection — the structure (compressed + recent + topics) is correct even if content quality needs work.
5. **Intent classification** is the most reliable extraction subsystem; categories are sensible.
6. **Per-interaction metrics snapshots** provide a temporal audit trail useful for monitoring graph growth.

---

## 7. Weaknesses & Suggestions

**W1: `agent-kg analyze` crashes**
`slice(None, 5, None)` — likely `.head(5)` or `.iloc[:5]` on an empty dataframe in topic analysis. Fix: guard before the slice, return graceful empty section if no data.

**W2: Duplicate entity nodes**
`.claude/settings.json` and `UserProfileStore` appear twice each. Fix: upsert on `(label, kind)` instead of blind insert.

**W3: Topic extraction is sequential bigrams**
Replace with a proper keyphrase extractor: RAKE, YAKE, or TF-IDF. Minimum: filter against a stopword list. 224 bigram noise nodes drown out 59 meaningful turn nodes.

**W4: Commitment text truncation**
Commitments cut mid-sentence. Fix: apply sentence boundary detection (`spaCy` `sentencizer`) before extracting; truncate at the first sentence end.

**W5: Prune is non-functional for single sessions**
`--force` on 59 turns produces 0 results. Either the window calculation is buggy or `--force` doesn't override the cross-session requirement. Fix: (a) document the cold-turn constraint in `--help` output; (b) make `--force` genuinely bypass the constraint; (c) add `--dry-run` to show what would be pruned.

**W6: Assistant turns have no embeddings**
The Stop hook ingests with `--no-embed`, meaning assistant turn content is not searchable via vector similarity. This explains low recall scores for queries about what the assistant said/did. Fix: embed assistant turns on a background thread or batch-embed during idle periods.

**W7: `assemble` duplicates every entry**
Each turn appears twice in output. Fix: deduplicate by node ID before formatting.

**W8: Snapshot is a metrics log, not a backup**
Rename to `agent-kg metrics-log` or update docs to say explicitly "records metrics only, not restorable." If actual restoration is desired, add `agent-kg export` that dumps full node+edge JSON, and `agent-kg restore --from <file>`.

**W9: Stop hook triggers too frequently**
20 snapshots in one session (one per response) creates clutter and I/O. Throttle: snapshot only when turn count crosses a threshold (every 10 turns) or after a 30-minute idle.

---

## 8. Overall Verdict

**Rating: 3/5**

AgentKG has a sound architecture and the right instincts: hook-based ingestion, hybrid SQLite + vector storage, repo-independent profiles, token-budgeted context assembly. The profile persistence feature alone justifies installation in any multi-session project.

**Ready for use:** Profile persistence (style, expertise, commitments) and session metadata.

**Not yet ready:** Reliable semantic recall of past turns, entity/topic extraction as a meaningful retrieval signal, pruning large single-session graphs.

**Recommended for:** Projects where cross-session profile continuity is the primary need and the user can tolerate rough edges in recall quality.

**Not recommended for:** High-precision recall of specific past technical discussions, or any workflow where `analyze` output is relied upon.

**Path to 4/5:** Fix the analyze crash, deduplicate entities, replace bigram topics with a real keyphrase extractor, fix prune, embed assistant turns, and resolve the duplicate-entry bug in assemble. None of these are architectural changes — they're implementation fixes.

---

*Assessment conducted by claude-sonnet-4-6 on 2026-04-05 per AgentKG Assessment Protocol v1.*
*Graph state: 360 nodes, 499 edges, 59 turns, 1 session, 20 snapshots.*
