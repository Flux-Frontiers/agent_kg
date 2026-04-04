# KGRAG Workflows

Multi-step procedures for common KGRAG use cases.

## Workflow 1: First-Time Setup (Single Project)

Initialize KGRAG for a single project and start querying.

**Steps:**

1. **Initialize the project:**
   ```bash
   cd ~/repos/myproject
   kgrag init
   ```
   This auto-detects applicable layers (code, doc), builds them, and registers in the registry.

2. **Verify registration:**
   ```bash
   kgrag list
   ```
   Should show registered KG instances (e.g., `myproject-code`, `myproject-doc`).

3. **Try a simple query:**
   ```bash
   kgrag query "authentication flow"
   ```
   Results should appear from all registered KGs.

4. **Launch the visualizer:**
   ```bash
   kgrag viz
   ```
   Open browser to `http://localhost:8501` to explore interactively.

**Time:** ~5 minutes (depends on codebase size)

**Output:** Fully initialized KGRAG registry with one project's KGs.

---

## Workflow 2: Multi-Project Setup

Initialize and federate multiple projects under a single registry.

**Setup (first time only):**

```bash
# Initialize project 1
kgrag init ~/repos/backend --name backend

# Initialize project 2
kgrag init ~/repos/frontend --name frontend

# Initialize project 3
kgrag init ~/repos/docs --name docs
```

**Verify all registered:**
```bash
kgrag status
# Output: 3 KGs registered, all built
```

**Query all projects at once:**
```bash
kgrag query "error handling patterns"
# Results from backend code, frontend code, and docs — all ranked globally
```

**Explore in UI:**
```bash
kgrag viz
```

**Key insight:** Once initialized, KGRAG treats all projects as one federated corpus. You never need to specify which project to search — all KGs are queried simultaneously.

---

## Workflow 3: Preparing Context for LLM Analysis

Extract relevant snippets from KGs and prepare markdown for feeding to LLMs.

**Steps:**

1. **Identify the topic you're analyzing:**
   Example: "How does our system handle database transactions?"

2. **Extract snippets:**
   ```bash
   kgrag pack "database transaction patterns" \
     --kind code \
     --out db_context.md \
     -k 8 \
     --context 5
   ```

3. **Verify the output:**
   ```bash
   wc -l db_context.md  # Check file size
   head -50 db_context.md  # Preview
   ```

4. **Use in LLM prompt:**
   ```bash
   # Option A: Copy to clipboard (macOS)
   cat db_context.md | pbcopy

   # Option B: Include in file
   cat db_context.md >> analysis_prompt.txt
   ```

5. **(Optional) Customize context:**
   If snippets are too large, reduce `-k` or `--context`:
   ```bash
   kgrag pack "database transaction patterns" \
     --kind code \
     --out db_context_compact.md \
     -k 5 \
     --context 3
   ```

**Result:** `db_context.md` is ready to paste into Claude, ChatGPT, or other LLM for analysis.

---

## Workflow 4: Running Architectural Analysis

Analyze a single CodeKG instance for complexity, issues, and strengths.

**Steps:**

1. **Check available CodeKGs:**
   ```bash
   kgrag list | grep code
   ```

2. **Get a quick analysis:**
   ```bash
   kgrag analyze
   ```
   Shows overview of all KGs.

3. **Deep dive with visualizer:**
   ```bash
   kgrag viz
   ```
   - Open browser
   - Go to **🧪 Analysis** tab
   - Select a CodeKG
   - Click **Run Analysis**
   - Results show: complexity hotspots, call chains, docstring coverage, orphaned code, etc.

4. **(Optional) Export analysis:**
   In the visualizer, click **⬇ Download Markdown** to save the full report.

**Result:** Detailed architectural report suitable for code review, refactoring planning, or team discussion.

---

## Workflow 5: Setting Up Claude Code Integration

Configure KGRAG to work with Claude Code via MCP.

**Steps:**

1. **Ensure KGRAG is initialized:**
   ```bash
   cd ~/repos/myproject
   kgrag init
   ```

2. **Find your registry path:**
   ```bash
   echo $KGRAG_REGISTRY
   # If not set, default is ~/.kgrag/registry.sqlite
   ```

3. **Create `.mcp.json` in project root:**
   ```json
   {
     "mcpServers": {
       "kgrag": {
         "command": "kgrag",
         "args": ["mcp", "--registry", "/absolute/path/to/registry.sqlite"]
       }
     }
   }
   ```
   ⚠️ Use **absolute paths** (not `~`).

4. **Restart Claude Code** — MCP tools load automatically.

5. **Verify in Claude Code prompt:**
   Type `kgrag_query` or `kgrag_pack` — should show autocomplete.

6. **Use in prompts:**
   ```
   Use kgrag_query("error handling", k=8, kinds=["code"])
   to find error handling patterns, then explain them.
   ```

**Result:** Claude Code now has federated search capabilities. Queries appear inline in the conversation with ranked results.

---

## Workflow 6: Rebuilding After Major Changes

Rebuild KGs when code structure changes significantly.

**When to rebuild:**
- After large refactoring (renames, deletions, restructuring)
- After adding significant new modules
- Monthly health check
- When results seem stale

**Steps:**

1. **Full rebuild (recommended):**
   ```bash
   kgrag init ~/repos/myproject --wipe
   ```
   This deletes and rebuilds all databases from scratch.

2. **Verify the rebuild:**
   ```bash
   kgrag info myproject-code
   ```
   Check that "Updated" timestamp is recent.

3. **Test with a query:**
   ```bash
   kgrag query "new feature" --kind code -k 5
   ```

**Time:** Depends on codebase size (typically 1-5 minutes for Python projects).

**Why `--wipe`?** Without it, renamed nodes remain as phantom entries. `--wipe` clears stale data completely.

---

## Workflow 7: Debugging Missing Results

Troubleshoot when queries return no results.

**Steps:**

1. **Check registry health:**
   ```bash
   kgrag status
   ```
   Look for:
   - Total KGs registered (should be > 0)
   - Built count (should match total)
   - Any "not built" or "missing path" indicators

2. **If KG is "not built":**
   ```bash
   kgrag init ~/repos/myproject --wipe
   ```

3. **Verify KG contains data:**
   ```bash
   kgrag info myproject-code
   ```
   Check `node_count` and `edge_count` (should be > 0).

4. **Try a broader query:**
   ```bash
   # Instead of: "JWT validation"
   # Try: "authentication"
   kgrag query "authentication"
   ```

5. **Check filters:**
   ```bash
   # Instead of: --kind code only
   # Try: query all KGs
   kgrag query "your query"  # no --kind filter
   ```

6. **If still no results, rebuild:**
   ```bash
   kgrag init ~/repos/myproject --wipe
   ```
   Then try query again.

---

## Workflow 8: Cross-Project Pattern Analysis

Search for a pattern across multiple projects and compare implementations.

**Steps:**

1. **Ensure multiple projects are registered:**
   ```bash
   kgrag list
   # Should show multiple projects
   ```

2. **Search for pattern across all projects:**
   ```bash
   kgrag query "caching strategy"
   ```
   Results include implementations from all projects.

3. **Extract snippets for side-by-side comparison:**
   ```bash
   kgrag pack "caching strategy" -k 3 --out caching_patterns.md
   ```

4. **Review in visualizer:**
   ```bash
   kgrag viz
   ```
   - Go to **🔍 Federated Query** tab
   - Query: "caching strategy"
   - Set **Display** to "Grouped by KG"
   - Compare implementations side-by-side

5. **(Optional) Filter by project:**
   In visualizer, use the sidebar KG selector to compare subset of projects.

**Result:** Clear understanding of how different projects solve the same problem.

---

## Workflow 9: Team Collaboration with Visualizer

Share findings with non-technical team members using the KGRAG visualizer.

**Setup:**

1. **Initialize KGRAG (see Workflow 2 for multi-project setup):**
   ```bash
   kgrag init ~/repos/myproject
   ```

2. **Prepare the visualizer:**
   ```bash
   kgrag viz --port 8501
   ```

3. **Make it accessible:**
   - For local network: Use your machine's IP (not `localhost`)
   - For remote: SSH tunnel or use `--host 0.0.0.0` (be careful with security)

4. **Share the URL:**
   - Local: `http://192.168.1.100:8501`
   - Give team members the link

**In the visualizer, teams can:**

- **📋 Registry tab** — See what KGs exist, build status
- **🔍 Federated Query tab** — Run searches, see results ranked or grouped
- **🧪 Analysis tab** — View architectural reports
- **📦 Snippet Pack tab** — Extract code for documentation

**Result:** Non-technical stakeholders can explore the codebase without CLI knowledge.

---

## Workflow 10: Automation with JSON Output

Use KGRAG in scripts and automation pipelines.

**Query and capture results:**
```bash
kgrag query "error handling" --json > results.json
```

**Process results:**
```python
import json

with open("results.json") as f:
    results = json.load(f)

for hit in results["hits"]:
    print(f"{hit['kg_name']}: {hit['name']} (score: {hit['score']})")
```

**Extract snippets to file:**
```bash
kgrag pack "database patterns" --out context.md
# Use context.md in documentation, reports, or further processing
```

**Health monitoring:**
```bash
kgrag analyze --json | jq '.by_kind'
# Extract specific metrics for monitoring dashboards
```

**Result:** KGRAG integrates into CI/CD, monitoring, and automation workflows.

---

## Best Practices Across Workflows

1. **Use meaningful query terms** — "JWT validation" is better than "auth"
2. **Start with small k** — `kgrag query "term" -k 3` for focused results
3. **Filter by kind when appropriate** — `--kind code` for code patterns, `--kind doc` for docs
4. **Rebuild monthly** — Run `kgrag init` periodically to catch stale data
5. **Verify with `kgrag status`** — Before troubleshooting, always check health
6. **Use visualizer for exploration** — CLI for automation, UI for interactive analysis
7. **Export results** — Use `--json` or `--out FILE` for reproducible workflows
