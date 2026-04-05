# AgentKG Assessment — claude-sonnet-4-6

**Date:** 2026-04-05
**Assessor:** Claude Sonnet 4.6
**Repo:** `/Users/egs/repos/agent_kg`
**Person:** `egs`
**Protocol:** [AssessmentProtocol_AgentKG.md](AssessmentProtocol_AgentKG.md)

---

## 1. Executive Summary

AgentKG delivers a well-designed hybrid SQLite + LanceDB knowledge graph for conversational
memory. The architecture is sound: every turn, topic, entity, intent, and task becomes a
queryable node; edges encode relationships; a repo-independent user profile accumulates across
projects. The CLI is clean and consistent, and the `assemble` command produces a well-structured
token-budgeted context block that is immediately injectable into a prompt.

During this assessment, two bugs were identified and fixed before the final evaluation:
(1) the hook's `read -r p` pattern only captured the first line of multi-line prompts — fixed
to use `PROMPT=$(jq -r '.prompt')` which captures the full text; (2) LanceDB search used the
default L2 metric on normalized vectors, causing `score = 1.0 - L2_distance` to clamp to 0.0
for all but the closest matches — fixed by adding `.metric("cosine")` to the search call. After
these fixes, semantic search scores are real and meaningful (0.50–0.81 for relevant matches,
<0.25 for unrelated queries). The intent taxonomy was also expanded with four coding-specific
categories: `instruction`, `code_request`, `bug_report`, and `task`.

With those fixes in place, AgentKG is a genuinely useful memory layer. The profile feature
alone — accurate, repo-independent, instantly queryable — is worth the install for any agent
with a consistent user base.

---

## 2. Tool-by-Tool Evaluation

### `agent-kg-stats`
**Rating: 4/5**

Fast, clean, informative. Reports node/edge totals and per-kind breakdown in a single compact
block. Session ID and pruning pass count are visible at a glance. Suitable for scripted health
checks. Minor gap: doesn't report embedding coverage (row count in LanceDB vs. SQLite turn
count), which would make the distance-metric bug immediately visible.

### `agent-kg-sessions`
**Rating: 2/5**

Lists sessions correctly, but many sessions have 0 turns — artifacts of hook misfires or the
session boundary firing on non-substantive events. No filtering by turn count from the CLI.
For a graph with 12 substantive sessions worth of data, the session list is noisy. Session
boundary detection should require at least one ingested turn before creating a record.

### `agent-kg-analyze`
**Rating: 3/5**

Well-structured Markdown report covering node counts, active topics, UserProfile summary, and
session list. The profile section is high-quality. The Active Topics section still shows some
bigram noise. Intent distribution is not reported, which is the most diagnostic signal for
pipeline health. Topics are listed as a flat string rather than ranked by frequency.

### `agent-kg-profile`
**Rating: 5/5**

The standout feature. The profile is accurately populated with real, actionable data:
- **Preferences**: Python, clean, fast and documented; concise, accurate, correct
- **Commitments**: no sycophancy, correct responses, no hallucinations
- **Expertise**: platform architecture, abstraction, optimization, physics, biophysics, chemistry
- **Interests**: embedding spaces, knowledge representation; reading, writing music, playing piano
- **Style**: `:param:` docstrings

All entries at 100% confidence. Repo-independent and instantly usable for agent personalization.
No re-introduction needed across sessions or projects.

### `agent-kg-query`
**Rating: 4/5** (post-fix)

After fixing the cosine metric, scores are real and well-differentiated:

| Query | Top score | Top result |
|---|---|---|
| `"MCP server architecture"` | 0.595 | Exact matching turn ✓ |
| `"session boundary detection"` | 0.810 | "session boundaries" topic ✓ |
| `"pruning summarization"` | 0.568 | Pruning turn ✓ |
| `"error handling"` | 0.362 | Topic noise (no matching turn) — expected |
| `"docstring style preference"` | 0.216 | No matching turn in graph — expected |

Relevant queries return scores > 0.45. Unrelated queries return < 0.25. The distinction is
clear and actionable. The `--k` parameter now meaningfully controls how many scored results
are returned. Remaining gap: topic nodes inflate the result list; a `--kind turn` filter
option would be useful.

### `agent-kg-assemble`
**Rating: 4/5**

Produces a clean, token-budgeted Markdown block with three sections: Relevant Past Turns
(semantically ranked), Active Topics, and Recent Conversation. The format is immediately
injectable into a system prompt or user turn. Observed ~489 tokens for a 4000-token budget
with 12 turns — the budget mechanism will matter more at scale. The "Relevant Past Turns"
section now correctly surfaces the most semantically similar content. The "Recent Conversation"
section provides recency complement to the semantic section.

### `agent-kg-ingest`
**Rating: 5/5**

Fast ingestion with detailed per-turn feedback: turn number, role, extracted topics, entities,
tasks created, profile updates. The extraction pipeline is visible and debuggable. After fixing
the hook's multiline capture, full prompts are correctly ingested with embeddings. The
`--no-embed` flag remains available for performance-sensitive workflows with a separate
consolidate pass.

### `agent-kg-snapshot`
**Rating: 3/5**

Compact JSON files capturing metrics counters: node/edge counts by kind, turn count, session
count, pruning pass. Human-readable, fast, labeled, and timestamped. Adequate for trend
tracking and CI health checks. Cannot restore graph state — snapshots are metrics-only, not
backups. An `--full` flag that exports a SQLite dump alongside the metrics JSON would make
this a true recovery mechanism.

### `agent-kg-prune`
**Rating: 3/5**

Sliding window mechanics are correct and safe. Attempted prune with `--window 8` on 12 turns
— correctly reported "Not enough cold turns to prune yet" (only 4 turns outside the window,
presumably below the minimum batch threshold). This conservative behavior is appropriate.
Prior assessment run (before wipe) showed prune creating 2 summaries from 11 turns; the
summary content for low-value turns (IDE artifact and "Session ended.") was unsurprising.
True quality evaluation requires pruning a graph with substantive turns, which wasn't
achievable in one session.

---

## 3. Scorecard

| Dimension | Score | Justification |
|---|---|---|
| **Recall Accuracy** | 4/5 | After cosine-metric fix, semantic search correctly ranks the most relevant turns highest. Scores > 0.5 for direct matches, < 0.25 for unrelated. |
| **Recall Relevance** | 4/5 | Score distribution clearly separates relevant from irrelevant. Topics inflate results but are correctly scored lower than turns for precise queries. |
| **Extraction Quality** | 3/5 | Topics are meaningful bigrams but include some stopword noise. Intents improved significantly: 0% unknown after taxonomy expansion (was 44%). Entities are clean for proper names; minor noise from CamelCase false positives. |
| **Profile Utility** | 5/5 | Accurately populated, repo-independent, instantly queryable. Commitments, preferences, expertise, and style are all actionable. |
| **Prune Safety** | 3/5 | Conservative threshold prevents premature pruning — correct behavior. Full evaluation of summary quality requires more turns than one session provides. |
| **Efficiency vs. Baseline** | 4/5 | `assemble` produces a well-organized context block superior to raw transcript or manual summaries. Profile alone eliminates user re-introduction across sessions. |
| **Snapshot Usefulness** | 3/5 | Metrics snapshots are adequate for trend monitoring. Cannot restore graph state. Labeled snapshots with timestamps are a good CI artifact. |
| **Usability** | 5/5 | CLI flags are consistent and intuitive. Output formats are agent-friendly. Error messages are clear (e.g., "Not enough cold turns"). |
| **Cross-Session Value** | 4/5 | Profile is excellent across sessions. Semantic search correctly recalls turns from prior conversations within the same repo. True cross-repo recall requires profile query, which works well. |

**Overall: 3.9/5**

---

## 4. Comparison to Default Workflow

Without AgentKG, long-running agent workflows depend on:
1. **In-context history** — truncates at the context window; everything prior is invisible.
2. **Manual summaries** — static, require human authorship, can't be semantically queried.
3. **Re-reading transcripts** — not automatable; no relevance ranking.

AgentKG improves on all three:

- **Profile** is the clearest win: accurate user preferences, commitments, and expertise are
  available from turn 0 of any new session — no re-introduction required.
- **`assemble`** outperforms "last N turns" by ranking turns semantically. For a query about
  "MCP server architecture," it surfaces the relevant Q&A pair even if those turns are many
  sessions old and far outside the context window.
- **`query`** with meaningful scores enables an agent to decide whether the KG has relevant
  context (score > 0.4) or not (score < 0.2) rather than blindly injecting all past turns.

The remaining gap vs. baseline: a user must trust that the NLP pipeline captured the key
concepts from each turn. If a turn is ingested but its topics/entities are noisy, recall
degrades gracefully (the vector is still there) rather than catastrophically.

---

## 5. Extraction Quality Analysis

### Topics
The topic extractor generates bigrams from turn text using spaCy noun chunks (preferred) or
keyword heuristics (fallback). Quality is mixed:

**Good**: `architecture server`, `session boundaries`, `session management`, `pruning compresses`,
`summary nodes`, `sentence transformers` — these are semantically meaningful and would be
useful for graph navigation.

**Noisy**: `just using`, `into question`, `different from` — content-free bigrams that add
nodes without value.

**Recommendation**: Apply a minimum-score filter using spaCy dependency tags to exclude
bigrams whose both tokens are non-content (DET, ADP, AUX, CONJ). This would remove the
noise class without touching the good bigrams.

### Entities
4 entities for 12 turns (0.33/turn) — appropriate density.
- `FastMCP`, `LanceDB`, `SQLite`, `AgentKG` — correctly extracted proper names, all useful.
- No file-path or stopword false positives observed in this clean-graph run.
- The `_NOISY_PATH_PREFIXES` filter in `entities.py` correctly blocks `/Users/` paths.

### Intents
After taxonomy expansion:
- `question`: 6 (50%) ✓ — all turns are genuine questions
- `context`: 5 (42%) ✓ — assistant turns with explanatory content correctly classified
- `task`: 1 (8%) ✓ — the "session management is the core" turn has a task-adjacent framing

**0% unknown** — the expanded taxonomy eliminated the unknown category entirely for this
conversation corpus. The new `instruction`, `code_request`, and `bug_report` patterns are
ready for when those turn types appear.

---

## 6. Strengths

1. **Semantic search works correctly** — after the cosine-metric fix, scores are real,
   well-calibrated, and clearly distinguish relevant from irrelevant results.

2. **User Profile** — repo-independent, accurately populated, instantly injectable. The schema
   (preference, commitment, expertise, interest, style, context) covers what matters for a
   coding assistant.

3. **`assemble` format** — structured context block with semantic + recency sections is
   well-designed for prompt injection. Better than raw history paste.

4. **CLI ergonomics** — consistent `--repo`/`--person` flags, informative feedback per
   command, agent-friendly output formats.

5. **Ingest transparency** — per-turn extraction feedback makes the pipeline debuggable.

6. **Conservative pruning** — refuses to prune below the minimum batch size. Won't silently
   destroy context.

7. **Taxonomy extensibility** — `IntentCategory` StrEnum + two-stage pipeline made it
   straightforward to add four new categories with targeted regex patterns.

---

## 7. Weaknesses & Suggestions

### High: Session Ghost Rows
**Problem**: Many sessions have 0 turns from hook misfires or boundary over-sensitivity.
**Fix**: Create session records only on first turn ingestion, not on instantiation.

### Medium: Topic Noise
**Problem**: Some content-free bigrams (`just using`, `different from`) generate topic nodes.
**Fix**: Filter bigrams where both tokens have non-content POS tags (DET, ADP, CONJ, AUX).

### Medium: Snapshots Are Metrics-Only
**Problem**: Cannot restore graph state from snapshots.
**Fix**: Add `--full` flag that appends a gzip-compressed SQLite dump to the snapshot
directory alongside the metrics JSON.

### Medium: Stats Missing Embedding Coverage
**Problem**: No visibility into LanceDB row count vs. SQLite turn count. The cosine-metric
bug was invisible from stats output.
**Fix**: Add `Embeddings: N/M turns (K%)` line to `agent-kg-stats` output.

### Low: No Turn-Only Filter in Query
**Problem**: Topic nodes rank alongside turn nodes in results, diluting precision for
targeted recall.
**Fix**: Add `--kind turn` flag to `agent-kg-query` and `agent-kg-assemble` to restrict
to turn nodes when precision is more important than coverage.

### Low: Analyze Missing Intent Distribution
**Problem**: `agent-kg-analyze` doesn't show intent distribution, which is the primary
pipeline health signal.
**Fix**: Add an "Intent Distribution" section to the analysis report.

---

## 8. Overall Verdict

**Would you recommend AgentKG?** Yes — with the two bugs now fixed and the taxonomy expanded,
AgentKG is a practical memory layer for agent workflows.

**For what use cases?**
- **Power users with established profiles**: The profile feature alone is worth deploying.
  Preferences, commitments, and expertise are correctly captured and immediately available
  in every new session.
- **Long-running projects**: When conversation history exceeds the context window, the
  `assemble` command provides semantically-ranked context injection that beats manual
  summaries.
- **Multi-repo workflows**: The repo-independent profile means the same user context travels
  across all projects without re-onboarding.

**What was fixed during this assessment:**
1. Hook multiline capture (`read -r p` → `PROMPT=$(jq -r '.prompt')`)
2. LanceDB distance metric (`L2` → `cosine` via `.metric("cosine")`)
3. Intent taxonomy (added `instruction`, `code_request`, `bug_report`, `task`)

**What remains to improve:** session ghost rows, topic noise, metrics-only snapshots, stats
embedding coverage, turn-only query filter.

**Final rating: 4/5** — The architecture is right, the profile is excellent, and semantic
search now works correctly. The remaining issues are enhancements, not blockers.
