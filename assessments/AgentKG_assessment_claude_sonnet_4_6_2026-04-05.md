# AgentKG Assessment — claude_sonnet_4_6 — 2026-04-05

**Assessor:** claude-sonnet-4-6
**Date:** 2026-04-05
**Repo:** `/Users/egs/repos/agent_kg`
**Person:** `egs`
**Platform:** 2026 M3 Max MacBook Pro, 64 GB RAM, 2 TB SSD

---

## 1. Executive Summary

AgentKG delivers on its core promise: a persistent, cross-session conversational memory that
survives context resets and is semantically queryable. The hybrid SQLite + LanceDB backend is
architecturally sound, and the CLI toolchain is cohesive enough that an agent can plausibly
use it without human guidance. Semantic recall for precise, on-topic queries is genuinely
strong — relevance scores above 0.9 for exact-match queries, and the `assemble` command
produces well-structured, token-budgeted context blocks that are ready for prepending to a
prompt.

However, the system has two significant rough edges. First, topic extraction produces a high
volume of noisy bigrams with minimal deduplication, diluting the semantic index with near-
synonyms and stopword-adjacent fragments. Entity extraction is even sparser: only 5 entities
were captured across 25 turns in a conversation heavily referencing tools, projects, and
people. Second, the pruning subsystem is gated on "cold turns" (turns from prior closed
sessions) in a way that makes it impossible to invoke on any single-session conversation,
including most practical early-lifecycle repos. The documentation and error messages do not
explain this constraint.

The user profile is the most strategically valuable feature: it is repo-independent, persists
commitments and expertise reliably, and provides a meaningful signal for personalizing agent
responses. With targeted improvements to extraction quality and pruning ergonomics, AgentKG
would be a compelling memory layer for multi-session AI assistants.

---

## 2. Tool-by-Tool Evaluation

### `agent-kg-stats`
**Rating: 5/5**
Concise, well-structured output. Node/edge counts broken out by kind. Session ID shown.
Runs in < 100ms. No issues found.

### `agent-kg-sessions`
**Rating: 4/5**
Lists sessions with start time and turn count. Boundary detection is automatic. In testing,
only 1 session was present (all 25 turns in one session) — functionally correct but limits
the ability to test cross-session behavior. Output format is clear.

### `agent-kg-analyze`
**Rating: 4/5**
Produces a useful Markdown report: node/edge counts, open tasks, active topics, profile
summary, session list. The "Active Topics" section surfaces the most recent bigrams rather
than the highest-frequency ones, which can make it feel noisy. Profile embedding in the
analysis output is a nice touch. Would benefit from a topic frequency ranking.

### `agent-kg-profile`
**Rating: 3/5**
Profile content is meaningful (commitments, preferences, expertise, interests, style). However,
several preference entries are malformed — injection of raw conversation fragments:
- `"embedding always! fix the hooks first and then re=run"` stored as a preference
- `"your ideas"` and `"you to exercise agent_kg NOT code_kg"` stored as preferences
  (these are instruction turns, not style preferences)

This suggests the preference extraction classifier does not adequately filter non-preference
content and conflates instructions with standing preferences.

### `agent-kg-ingest`
**Rating: 4/5**
Works reliably. Topics, entities, and intent are classified at ingest time. The `--no-embed`
flag is a sensible optimization for hook-based ingestion. The turn numbering is global (not
per-session), which is correct. Entity extraction is weak (see Phase 3).

### `agent-kg-query`
**Rating: 3/5**
Strong for precise, topic-rich queries. Top result for "MCP server architecture" scored 0.911
and was exactly correct. Weaker for broad or preference queries: "error handling" returned
only topic nodes at scores 0.23–0.45, none of which were turns. "Docstring style preference"
returned scores 0.19–0.23 — essentially random noise, missing the `:param:` entry in the
profile entirely. The query tool searches the conversation graph, not the profile graph; there
is no unified search across both.

### `agent-kg-assemble`
**Rating: 4/5**
Produces well-formatted, token-budgeted context blocks. Token count displayed (~467 tokens).
Sections for open tasks, relevant past turns, active topics, and recent conversation are
clearly structured. For "MCP server architecture", the assembled context was excellent.
For "what did we work on recently", the context included a raw `perform @assessments/...`
turn and a `/changelog-commit` slash command — noise from hook-captured prompts that are not
real conversation content. The assembled block would confuse an agent.

### `agent-kg-snapshot`
**Rating: 3/5**
Snapshot capture works and is fast. 7 snapshots taken during the assessment session; all
timestamped and stored as JSON. **Critical limitation**: snapshots store only aggregate
metrics (counts by kind) — they are not restorable backups. There is no mechanism to diff
two snapshots or to restore a graph from one. The format is useful for monitoring temporal
trends but not for recovery.

### `agent-kg-prune`
**Rating: 2/5**
Prune failed with "Not enough cold turns to prune yet" at all window sizes tested (5, 15, 20).
All 25 turns in the test run belong to the current session. "Cold turns" apparently refers to
turns from prior closed sessions. This design makes pruning impossible for any repo with a
single session — including all new projects and any single-uninterrupted-session scenario.
No documentation explains what "cold" means or how to satisfy the precondition. This is the
most significant usability gap in the system.

### `agent-kg-onboard` / `agent-kg-mcp`
Not exercised in this assessment (onboard requires interactive stdin; MCP server is tested
implicitly via existing hooks).

---

## 3. Scorecard

| Dimension | Score | Justification |
|-----------|-------|---------------|
| **Recall Accuracy** | 4/5 | Precise queries hit correctly (0.911 for "MCP server architecture"). Broad/preference queries miss. |
| **Recall Relevance** | 3/5 | Scores > 0.5 are meaningful; scores < 0.3 are noise. No clear relevance threshold documented. Query returns mixed turn/topic nodes without distinguishing content relevance from structural co-occurrence. |
| **Extraction Quality** | 2/5 | Topic bigrams are numerous but noisy; no deduplication of near-synonyms. Entity extraction very sparse (5/25 turns). Profile extraction conflates instructions with preferences. |
| **Profile Utility** | 3/5 | Profile content is largely correct and genuinely useful. Malformed entries (instruction fragments stored as preferences) reduce trust. Profile is not queryable from `agent-kg-query`. |
| **Prune Safety** | 1/5 | Prune refused to execute in all test conditions. Cannot assess post-prune recall quality. "Cold turns" constraint undocumented. |
| **Efficiency vs. Baseline** | 4/5 | For precise recall of past architectural decisions, clearly superior to scrolling context. Assembled context is prompt-ready with zero friction. |
| **Snapshot Usefulness** | 2/5 | Metrics snapshots are useful for trend tracking only. Not restorable; no diff tool. |
| **Usability** | 4/5 | CLI is consistent, flags are uniform (`--repo`, `--person`), output is human-readable and Markdown-friendly. Error messages occasionally unhelpful ("Not enough cold turns"). |
| **Cross-Session Value** | N/A | Only one session existed in this assessment. Cross-session behavior could not be tested. The profile mechanism (repo-independent) is the strongest indicator this works as designed. |

**Overall mean (scored dimensions): 2.9 / 5**

---

## 4. Comparison to Default Workflow

**Without AgentKG**, an agent working in this repo depends on:
1. In-context history — truncates at context window limits; loses everything on reset
2. Manual summaries in CLAUDE.md — static; requires human maintenance; no semantic search
3. Re-reading files on every session — slow; misses conversation-level context

**With AgentKG**, the agent can:
- Retrieve architecturally relevant turns from past sessions in < 200ms via `assemble`
- Access a persistent user profile with commitments and preferences without re-prompting
- See open tasks without reading todo files

**Net delta for precise recall queries:** High. The MCP server architecture context block would
have taken 3-5 minutes to reconstruct manually; AgentKG returned it in 1 second.

**Net delta for broad/preference queries:** Low to negative. "What did we work on recently"
returned noise-contaminated output. Profile queries require direct `agent-kg-profile` invocation,
not the conversational `query` interface. An agent using only `assemble` for preference recall
would get wrong answers.

**Recommendation for an agent workflow**: Use `agent-kg-assemble` for precise topic retrieval
and `agent-kg-profile` for preference/commitment retrieval — treat them as separate tools
with complementary scopes.

---

## 5. Extraction Quality Analysis

### Topics (Bigrams)

The topic extractor produces contiguous 2-grams from turn text. In 25 turns, 112 topic nodes
were created. Quality assessment:

**Useful topics** (semantically meaningful):
- `architecture server`, `uses fastmcp`, `semantic search`, `session management`,
  `sqlite lancedb`, `sentence transformers`, `pruning compresses`, `design goals`

**Noisy topics** (stopword-dominant or too generic):
- `module`, `query`, `repo`, `fix`, `memory`, `pipeline`, `error` — single words
- `metadata while`, `into batches`, `different from`, `just using` — function words
- `does agentkg`, `agentkg handle`, `agentkg provides`, `available agentkg` — undeduped variants

**Deduplication**: None observed. "AgentKG" appears as the second token in at least 4 distinct
topic nodes that all mean "something about AgentKG". A bigram index with TF-IDF pruning and
lemmatization would reduce noise significantly.

### Entities (Named Entities)

5 entities across 25 turns: `AgentKG`, `AssessmentProtocol_AgentKG`, `FastMCP`, `LanceDB`,
`SQLite`. Notable misses:
- `spaCy`, `sentence-transformers`, `claude-haiku` (all mentioned in turns)
- `graph.py`, `mcp_server.py` (file entities)
- `egs`, `Eric` (person entities)
- `UUID` (technical term repeatedly used)

The entity extractor appears to be limited to proper-noun NER only, missing technical compound
terms, file names, and person names. This gap materially limits the usefulness of the graph
structure for technical conversations.

### Intents

Distribution across 23 turns: question (10), context (8), unknown (2), task (1),
instruction (1), bug_report (1). No `request` or `code_request` classified.

For a Q&A-style conversation about architecture, `question` and `context` are the dominant
correct classifications. The 2 `unknown` classifications deserve investigation but are minor.
Intent quality is acceptable for this conversation type.

---

## 6. Strengths

1. **Precise semantic recall works well.** Top-1 result for an exact-match architectural query
   scored 0.911 with correct content. The hybrid SQL + vector search is the right architecture
   for this problem.

2. **`assemble` output is agent-ready.** Token budget respected, sections clearly delineated,
   open tasks surfaced, relevant + recent turns both included. This is immediately usable as
   a prompt prefix without post-processing.

3. **User profile is repo-independent and persistent.** The global profile at
   `~/.kgrag/profiles/<person_id>/` accumulates commitments and preferences across all
   projects. This is the strongest cross-session signal in the system. 16 profile nodes
   observed, covering commitments, preferences, expertise, interests, and style.

4. **CLI is ergonomic and consistent.** All commands share `--repo` and `--person` flags.
   Auto-detection via `$(git rev-parse --show-toplevel)` works reliably. Output is clean
   Markdown that pipes into reports. Startup latency is low.

5. **Snapshot mechanism provides audit trail.** Even as metrics-only, the JSON timestamps
   give a temporal record of graph growth that is useful for monitoring.

---

## 7. Weaknesses & Suggestions

### W1: Topic extraction is noisy and undeduped
**Problem:** 112 bigrams from 25 turns includes many stopword-adjacent and near-duplicate
entries. No lemmatization or deduplication.
**Suggestion:** Apply TF-IDF filtering to remove low-information bigrams. Normalize to
lowercase + lemmatized form before storing. Use a minimum frequency or entropy threshold
before creating a topic node.

### W2: Entity extraction too narrow
**Problem:** Only capitalized proper nouns are captured. File names, model names, technical
compounds, and person names are missed.
**Suggestion:** Expand the NER pipeline to include: (a) spaCy `ORG`/`PRODUCT`/`PERSON`
labels, (b) regex for `*.py` file references, (c) model/package names matching
`[a-z]+-[a-z]+` pattern (e.g., `sentence-transformers`, `claude-haiku`).

### W3: Prune requires "cold turns" — undocumented and un-triggerable in single sessions
**Problem:** `agent-kg-prune` silently fails when all turns are in the current session, with
an unhelpful message. No documentation defines "cold turns" or explains the precondition.
**Suggestion:** (a) Document the cold-turn requirement clearly in `--help` output and the
README. (b) Add a `--force` flag that allows pruning the current session. (c) Consider
auto-closing the prior session on `agent-kg-stats` first-run in a new session.

### W4: Snapshot is metrics-only — not restorable
**Problem:** Snapshots store count aggregates only. There is no mechanism to restore a graph
from a snapshot.
**Suggestion:** Add an `--full` mode to `agent-kg-snapshot` that serializes all nodes/edges
to JSON (or a compressed SQLite dump). Add `agent-kg-restore --snapshot <file>` as a
companion command.

### W5: Profile extraction conflates instructions with preferences
**Problem:** Turn-level instruction text (e.g., "fix the hooks first") is stored as a
preference node. Slash commands (`/changelog-commit`) are stored as conversation turns.
**Suggestion:** Pre-filter ingested text: skip turns that start with `/` (CLI commands),
`<ide_opened_file>` (IDE context injections), or match known Claude Code hook patterns.
Tighten the preference classifier to require explicit first-person preference markers
("I prefer", "I like", "my style is").

### W6: Query does not search profile nodes
**Problem:** `agent-kg-query "docstring style"` returns nothing about `:param:` style despite
it being in the profile. The query and profile stores are separate.
**Suggestion:** Add a `--include-profile` flag to `agent-kg-query` (and `assemble`) that
also searches profile nodes and merges results, ranked by relevance.

---

## 8. Overall Verdict

**Recommended for:** AI coding assistants working across multiple sessions in a single repo,
especially where the user has established preferences, commitments, and architectural decisions
that are expensive to re-derive from context. The strongest use case is rapid retrieval of
past architectural discussions and standing user preferences (via profile).

**Not yet recommended for:** Agents that rely on broad/preference semantic search, single-
session workflows, or any scenario requiring graph pruning or point-in-time restoration.

**Would I use AgentKG in my own workflow?** Yes, for the `assemble` + `profile` combination.
The 1-second retrieval of a correct architectural context block is a qualitative improvement
over manual context management. The rough edges are addressable with targeted engineering.

**Final rating: 3.0 / 5**

The foundation is solid and the core value proposition is proven for precise recall. Extraction
quality and pruning ergonomics need work before this is production-ready for general-purpose
agent memory.

---

*Assessment conducted by claude-sonnet-4-6 on 2026-04-05 per AgentKG Assessment Protocol v1.*
