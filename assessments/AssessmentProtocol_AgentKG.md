# AgentKG Assessment Protocol

**Author:** Eric G. Suchanek, PhD <suchanek@mac.com>
**Repository:** https://github.com/Flux-Frontiers/agent_kg.git
**Testing Platform:** 2026 M% Max, MacBook Pro, 64GB RAM, 2TB SSD

---

## Background

AgentKG stores conversational memory in a hybrid SQLite + LanceDB knowledge graph that
persists across sessions. Every user turn, assistant turn, topic, entity, intent, task,
and user preference becomes a node; edges encode their relationships. The result is a
queryable, prunable, semantically-searchable memory that survives context resets.

Unlike CodeKG (which indexes *source code*), AgentKG indexes *conversations* — making it
a fundamentally different beast to evaluate. The key question is not "does it find the
right function?" but "does it recall the right context at the right time?"

You have access to AgentKG's CLI tools and MCP server in this session. Your task is to
**evaluate the tool itself** — not the repo it stores memory for.

---

## Pre-Assessment Setup

Before starting, verify the graph has data to work with:

```bash
agent-kg-stats --repo "$(git rev-parse --show-toplevel)"
```

If turn count is low (< 20), ingest a few representative turns first:

```bash
agent-kg-ingest "What is the architecture of the MCP server?" --role user \
  --repo "$(git rev-parse --show-toplevel)"
agent-kg-ingest "The MCP server uses FastMCP with tool handlers in mcp_server.py." \
  --role assistant --repo "$(git rev-parse --show-toplevel)"
```

---

## Phase 1: Orientation & Health Check

1. Run `agent-kg-stats --repo .` — review node/edge counts by kind.
   Are the proportions sensible? (turns >> topics > entities > tasks)
2. Run `agent-kg-sessions --repo .` — how many sessions exist? Are
   session boundaries correctly detected?
3. Run `agent-kg-analyze --repo .` — read the full Markdown analysis.
   - Is the breakdown useful for understanding conversation history?
   - Are topics, intents, and entities accurately extracted?
4. Run `agent-kg-profile --repo . --person egs` — is the user profile populated?
   (`--person` required here — profile is user-scoped, not repo-scoped.)
   - If empty, note it as a setup issue, not a tool failure.

## Phase 2: Semantic Recall

Test the hybrid search and assembly capabilities with varied queries:

1. **Precise recall** — Ask for something specific that was discussed (e.g.,
   `"MCP server architecture"`, `"CLI entry point"`, `"database schema"`).
2. **Broad recall** — Ask for a high-level concern (e.g., `"error handling"`,
   `"design decisions"`, `"what did we work on recently"`).
3. **Preference recall** — Ask for a user preference (e.g.,
   `"docstring style preference"`, `"testing approach"`).

For each query, run **both**:
```bash
agent-kg-query "<query>" --k 8 --repo .
agent-kg-assemble "<query>" --budget 4000 --repo .
```

For preference recall specifically, also run:
```bash
agent-kg-query "<query>" --k 8 --repo . --include-profile
```

Compare:
- Do `query` results rank the most relevant turns highest?
- Does `assemble` produce a well-formatted, token-budgeted context block?
- Are scores meaningful (> 0.4 for relevant hits, near 0 for unrelated)?
- How does this compare to manually scrolling conversation history?

## Phase 3: Entity & Topic Extraction Quality

1. Examine the entity nodes from `agent-kg-stats` output or direct SQLite query:
   ```bash
   sqlite3 .agentkg/graph.sqlite \
     "SELECT label, kind FROM nodes WHERE kind IN ('entity','topic') LIMIT 30;"
   ```
2. Assess extraction quality:
   - Are entities meaningful (tools, projects, people) or noisy?
   - Are topics representative N-grams, or mostly stopwords?
   - Is there deduplication? (e.g., "codekg" and "CodeKG" shouldn't be separate nodes)
3. Check intent classification:
   ```bash
   sqlite3 .agentkg/graph.sqlite \
     "SELECT label, COUNT(*) as n FROM nodes WHERE kind='intent' GROUP BY label ORDER BY n DESC;"
   ```
   Are the intent categories reasonable for a coding assistant conversation?

## Phase 4: Profile & Cross-Session Memory

1. Run `agent-kg-profile --repo . --person egs` — read the global profile.
2. Verify profile nodes exist:
   ```bash
   sqlite3 ~/.kgrag/profiles/egs/userprofile.sqlite \
     "SELECT kind, COUNT(*) FROM profile_nodes GROUP BY kind;"
   ```
3. Assess: Does the profile capture meaningful preferences, expertise areas, and
   commitments that would actually help an agent personalize future responses?
4. Is the profile repo-independent? Verify it accumulates across projects.

## Phase 5: Snapshot & Temporal Analysis

1. Capture a snapshot:
   ```bash
   agent-kg-snapshot --repo . --label "assessment baseline"
   ```
2. List snapshots:
   ```bash
   ls -la .agentkg/snapshots/
   ```
3. Ingest 2-3 new turns, then take a second snapshot.
4. Assess: Are snapshots useful for point-in-time recovery? Is the format
   human-readable? Could you restore from one?

## Phase 6: Pruning

1. Check current turn count from stats.
2. Run a dry-run prune (if supported) or run with a conservative window:
   ```bash
   agent-kg-prune --window 20 --repo .
   # If all turns are in the current session, add --force
   agent-kg-prune --window 20 --repo . --force
   ```
3. Re-run stats and compare node counts.
4. Run a recall query from Phase 2 again — does quality degrade after pruning?
5. Assess: Does the summary node replacement preserve enough context for later recall?

---

## Evaluation Criteria

Score each dimension 1 (poor) to 5 (excellent) with brief justification:

| Dimension | What to Assess |
|-----------|----------------|
| **Recall Accuracy** | Does semantic search surface the genuinely relevant past turns? |
| **Recall Relevance** | Do scores distinguish relevant vs. irrelevant results? |
| **Extraction Quality** | Are topics, entities, and intents accurately and usefully extracted? |
| **Profile Utility** | Does the user profile capture actionable preferences and expertise? |
| **Prune Safety** | Does pruning preserve recall quality? Are summaries faithful? |
| **Efficiency vs. Baseline** | Is this better than re-reading transcripts or relying on system prompts? |
| **Snapshot Usefulness** | Are snapshots practical for recovery and diffing? |
| **Usability** | Are CLI interfaces intuitive? Is output well-structured for agent ingestion? |
| **Cross-Session Value** | Does memory genuinely improve responses across session boundaries? |

---

## Output Requirements

Save your assessment as:

```
./assessments/AgentKG_assessment_<model_name>_<datestamp>.md
```

Where `<model_name>` is your model identifier (e.g., `claude_sonnet_4_6`) and
`<datestamp>` is `YYYY-MM-DD`.

### Required Sections

1. **Executive Summary** — 2-3 paragraph overall assessment
2. **Tool-by-Tool Evaluation** — Rate and discuss each CLI command and MCP tool exercised
3. **Scorecard** — The evaluation criteria table with scores and justifications
4. **Comparison to Default Workflow** — How does AgentKG change your approach vs.
   relying on in-context history or manual summaries?
5. **Extraction Quality Analysis** — Deep dive on topic/entity/intent extraction
6. **Strengths** — What AgentKG does well
7. **Weaknesses & Suggestions** — What could be improved, with specific recommendations
8. **Overall Verdict** — Would you recommend AgentKG? For what use cases? Final rating out of 5.

---

## Important Notes

- **Assess the tool, not the project.** Focus on how well the *memory system* helps you
  recall and contextualize past conversations — not on agent_kg's codebase quality.
- **Be honest about recall failures.** If a query returns irrelevant turns or misses
  obvious ones, document the specific case. That's the most valuable signal.
- **Compare to your baseline.** Without AgentKG, you depend on in-context history
  (which truncates) or manual summaries (which are static). Explicitly compare.
- **Test across the session boundary.** The whole value proposition is cross-session
  memory — if you can only test within a single session, note that limitation.
- **Score embeddings separately from extraction.** A weak topic extractor can coexist
  with strong semantic search — and vice versa. Keep them distinct.
