# Sync MCP Documentation

You are updating all AgentKG MCP documentation to reflect the current state of
`src/agent_kg/mcp/server.py`. Execute the following steps in order.

---

## Step 0: Establish the Source of Truth

Read `src/agent_kg/mcp/server.py` and extract the **authoritative tool list**:

1. Find the `_TOOLS` list (returned by the `@app.list_tools()` handler) — these are the
   declared tools, each a `types.Tool` with a `name`, `description`, and `inputSchema`.
2. Cross-check against the `@app.call_tool()` dispatch (`call_tool`) — every `name ==`
   branch is a live tool; the arguments it reads define the real parameters and defaults.
3. For each tool, record:
   - **Name** (e.g. `agent_kg_query`)
   - **Parameters** with defaults (from `arguments.get(...)` and the `inputSchema`)
   - **One-line description** (from the `Tool.description` / first docstring line)
   - **Return shape** (all tools return a `TextContent` block — note JSON-ish vs prose)
4. Print the complete tool inventory before proceeding. This is your ground truth.

**Example format:**
```
TOOL INVENTORY (from src/agent_kg/mcp/server.py):
  1. agent_kg_ingest(turn_text, role="user", repo, person_id, session_id) — ingest a turn
  2. agent_kg_query(query, k=8, repo, person_id)                          — hybrid semantic recall
  3. agent_kg_pack(query, k=6, …)                                         — source-grounded snippet pack
  4. agent_kg_assemble(query, budget=4000, …)                            — assemble context within a token budget
  5. agent_kg_prune(window=20, …)                                        — summarise + prune cold turns
  6. agent_kg_stats(repo, person_id)                                     — node/edge counts by kind
  7. agent_kg_topics(repo, person_id)                                    — list tracked topics
  8. agent_kg_tasks(repo, person_id)                                     — list open tasks
  9. agent_kg_profile(person_id)                                         — render the UserProfile markdown
 10. agent_kg_analyze(repo, person_id)                                   — full conversation analysis
```

> The list above is illustrative — always regenerate it from `_TOOLS`. Never invent tool
> names or parameters.

---

## Step 1: Update the AgentKG Skill (primary)

### `.claude/skills/agent-kg/SKILL.md`

- **Frontmatter `description:`** — ensure the MCP surface is represented. The
  `agent-kg-mcp` entry point must be mentioned; if the description enumerates capabilities,
  keep it consistent with the tool inventory.
- **`### MCP server` section** — maintain an **"MCP Tools"** table immediately under it:

  | Tool | When to use |
  |---|---|
  | `agent_kg_query(query, k)` | Hybrid semantic recall of past context |
  | … | … |

  Add a row for every tool in `_TOOLS`; update signatures in place; remove rows for tools
  that no longer exist. Keep one line per tool.

---

## Step 2: Update User-Facing Docs

Work through each file. Apply only the changes relevant to that file's format — do **not**
homogenize styles.

### 2a. `README.md`

- **Features list** — the `- **MCP server** —` bullet should describe the tool surface
  accurately (the count is optional but, if stated, must match `_TOOLS`).
- **`## MCP Server` section** — if it carries an "Available tools" table, every tool needs a
  row with the correct signature and description. If no table exists and the surface is now
  large enough to warrant one, add a compact table after the `.mcp.json` example.

### 2b. `docs/cheatsheet.md`

- **`## MCP Server` section** — keep a compact tools table (tool | best for) in sync with the
  inventory. Add missing tools; update changed signatures.

---

## Step 3: Update CLAUDE.md (if present)

If a `CLAUDE.md` exists in the repo root and contains an MCP tool table or list, apply the
same updates (signatures, descriptions, count) following that file's existing format.

---

## Step 4: Consistency Check

1. **Coverage** — every tool in `_TOOLS` appears in `SKILL.md` (and any table that lists tools).
2. **No phantom tools** — no doc references a tool name absent from `_TOOLS` / `call_tool`.
3. **Signatures** — parameter names and defaults match `server.py` exactly.
4. **Count** — any stated tool count matches the actual number of tools.

Fix any inconsistency before proceeding.

---

## Step 5: Stage and Prepare Commit

1. Stage the modified files (only those you actually changed):
   ```bash
   git add .claude/skills/agent-kg/SKILL.md README.md docs/cheatsheet.md
   ```
   Add `CLAUDE.md` if it was modified.

2. Write a conventional commit message, e.g.:
   ```
   docs(mcp): sync provider docs to the N-tool MCP surface

   Updated tool inventory: [list added/removed/changed tools]

   Files updated:
   - .claude/skills/agent-kg/SKILL.md: ...
   - README.md: ...
   - docs/cheatsheet.md: ...
   ```

---

## Rules

- **`src/agent_kg/mcp/server.py` is always the source of truth.** Never invent tool names
  or parameters.
- **Preserve each file's style.** Don't homogenize formats across files.
- **Minimal diffs.** Only change what is wrong, missing, or stale.
- **`SKILL.md` is the canonical tool reference** for this repo — keep it complete; other
  files can stay lighter-weight.
