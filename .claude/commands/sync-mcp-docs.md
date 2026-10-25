# Sync MCP Documentation

You are updating all AgentKG MCP documentation to reflect the current state of
`src/agent_kg/mcp/server.py`. Execute the following steps in order.

---

## Step 0: Establish the Source of Truth

Run `agentkg mcp --manifest` and take the **authoritative tool list** from its JSON. The
server is built on `kg_utils.mcp`: each tool's docstring is its description and its
signature is its input schema, so the manifest is generated, never hand-kept.

1. For each tool, record:
   - **Name** (e.g. `query`)
   - **Parameters** with defaults (from `input_schema`)
   - **One-line description** (the first line of `description`)
   - **Return shape** (structured JSON or text)
2. Print the complete tool inventory before proceeding. This is your ground truth.

**Example format:**
```
TOOL INVENTORY (from src/agent_kg/mcp/server.py):
  1. stats()                                  — node/edge counts by kind
  2. query(q, k=8, hop=0, max_nodes=25, rels)  — semantic recall
  3. pack(q, k=6, hop=0, max_nodes=15, rels)   — prompt-ready snippets
  4. get_node(node_id)                        — one node
  5. neighbors(node_id, rels, direction, limit) — a node's edges
  6. ingest(turn_text, role="user")           — ingest a turn
  …
```

> The list above is illustrative — always regenerate it from the manifest. Never invent tool
> names or parameters.

---

## Step 1: Update the AgentKG Skill (primary)

### `.claude/skills/agent-kg/SKILL.md`

- **Frontmatter `description:`** — ensure the MCP surface is represented. The
  `agentkg mcp` command must be mentioned; if the description enumerates capabilities,
  keep it consistent with the tool inventory.
- **`### MCP server` section** — maintain an **"MCP Tools"** table immediately under it:

  | Tool | When to use |
  |---|---|
  | `query(q, k)` | Semantic recall of past context |
  | … | … |

  Add a row for every tool in the manifest; update signatures in place; remove rows for tools
  that no longer exist. Keep one line per tool.

---

## Step 2: Update User-Facing Docs

Work through each file. Apply only the changes relevant to that file's format — do **not**
homogenize styles.

### 2a. `README.md`

- **Features list** — the `- **MCP server** —` bullet should describe the tool surface
  accurately (the count is optional but, if stated, must match the manifest).
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

1. **Coverage** — every tool in the manifest appears in `SKILL.md` (and any table that lists tools).
2. **No phantom tools** — no doc references a tool name absent from the manifest.
3. **Signatures** — parameter names and defaults match the manifest exactly.
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
