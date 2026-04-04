# KGRAG Troubleshooting Guide

Common issues and solutions.

## Registry & Initialization

### "No KGs registered" or empty registry

**Symptoms:**
- `kgrag list` shows no entries
- `kgrag status` says "0 KGs registered"

**Solutions:**

1. **Check if you've run `kgrag init`:**
   ```bash
   kgrag init ~/repos/myproject
   ```

2. **Verify registry path:**
   ```bash
   echo $KGRAG_REGISTRY
   # If empty, default is ~/.kgrag/registry.sqlite
   ```

3. **Check if registry file exists:**
   ```bash
   ls -la ~/.kgrag/registry.sqlite
   # If file doesn't exist, it will be created on first init
   ```

4. **Initialize multiple projects:**
   ```bash
   kgrag init ~/repos/project1
   kgrag init ~/repos/project2
   ```
   Then verify: `kgrag list`

---

### "KG not built" or marked as invalid

**Symptoms:**
- `kgrag status` shows "not built"
- `kgrag list` shows a KG with status "⚠️ Not built"

**Solutions:**

1. **Rebuild the KG:**
   ```bash
   kgrag init ~/repos/myproject --wipe
   ```

2. **Check if repo path still exists:**
   ```bash
   ls ~/repos/myproject
   # If path is gone, the KG entry is orphaned
   ```

3. **If path is gone, unregister:**
   ```bash
   kgrag unregister myproject-code
   ```
   Then re-register from new path:
   ```bash
   kgrag init ~/repos/myproject-new --name myproject-code
   ```

---

### "Registry file corrupted" or database errors

**Symptoms:**
- Error like: "database disk image is malformed"
- `kgrag list` fails with SQL errors

**Solutions:**

1. **Backup the registry:**
   ```bash
   cp ~/.kgrag/registry.sqlite ~/.kgrag/registry.sqlite.backup
   ```

2. **Delete and recreate:**
   ```bash
   rm ~/.kgrag/registry.sqlite
   kgrag init ~/repos/project1
   ```
   This creates a fresh registry and re-registers.

3. **Re-register all projects:**
   List your projects and re-initialize:
   ```bash
   kgrag init ~/repos/project1
   kgrag init ~/repos/project2
   kgrag init ~/repos/project3
   ```

---

## Querying & Results

### "No results found" for a query

**Symptoms:**
- `kgrag query "my search term"` returns empty
- Visualizer shows "No results found"

**Troubleshooting steps:**

1. **Check registry health:**
   ```bash
   kgrag status
   ```
   Ensure:
   - KGs are registered
   - KGs are marked as "built"
   - No "missing path" warnings

2. **If KG is not built, rebuild:**
   ```bash
   kgrag init ~/repos/myproject --wipe
   ```

3. **Verify KG contains data:**
   ```bash
   kgrag info myproject-code
   ```
   Check that `node_count` > 0 (not "n/a" or 0).

4. **Try a broader query:**
   Instead of: `"JWT token validation"`
   Try: `"authentication"` or `"token"`

5. **Remove filters to broaden search:**
   ```bash
   # Instead of:
   kgrag query "error handling" --kind code

   # Try:
   kgrag query "error handling"  # search all KGs
   ```

6. **Increase result count:**
   ```bash
   kgrag query "error handling" -k 12
   # Default is -k 8, try higher to see if more results exist
   ```

7. **Check if KG library is installed:**
   For CodeKGs:
   ```bash
   python -c "import code_kg; print('CodeKG installed')"
   ```
   For DocKGs:
   ```bash
   python -c "import doc_kg; print('DocKG installed')"
   ```

---

### Results seem outdated or stale

**Symptoms:**
- Query results mention code that's been deleted
- New code patterns don't show up in results

**Solutions:**

1. **Rebuild the KG:**
   ```bash
   kgrag init ~/repos/myproject --wipe
   ```
   The `--wipe` flag deletes old data before rebuilding.

2. **Rebuild just the indices:**
   ```bash
   kgrag init ~/repos/myproject
   # Without --wipe, does incremental update
   ```

3. **Schedule monthly rebuilds:**
   Add to your shell profile:
   ```bash
   alias kgrag-refresh='kgrag init ~/repos/myproject && kgrag init ~/repos/project2 && ...'
   ```

---

### Query results are too broad or irrelevant

**Symptoms:**
- Results don't match the query closely
- Getting unrelated code

**Solutions:**

1. **Use more specific terms:**
   - ❌ "database" (too broad)
   - ✅ "transaction handling" (specific)

2. **Filter by KG kind:**
   ```bash
   # Code patterns only
   kgrag query "error handling" --kind code

   # Documentation only
   kgrag query "setup instructions" --kind doc
   ```

3. **Reduce result count:**
   ```bash
   kgrag query "your term" -k 3
   # Lower k = higher relevance threshold
   ```

---

## Snippet Pack Issues

### "Pack is too large" for LLM context

**Symptoms:**
- Output markdown is thousands of lines
- Won't fit in LLM context window

**Solutions:**

1. **Reduce results per KG:**
   ```bash
   kgrag pack "term" -k 3  # instead of default 8
   ```

2. **Reduce context lines:**
   ```bash
   kgrag pack "term" --context 2  # instead of default 5
   ```

3. **Filter to specific KG kind:**
   ```bash
   kgrag pack "term" --kind code  # exclude docs if they're large
   ```

4. **Combine all three:**
   ```bash
   kgrag pack "database patterns" --kind code -k 3 --context 2
   ```

---

### "Pack includes wrong snippets"

**Symptoms:**
- Code snippets are unrelated to query
- Missing relevant code

**Solutions:**

1. **Try different query terms:**
   - Original: `"database patterns"`
   - Alternative: `"transaction handling"` or `"SQL queries"`

2. **Check if KG is up-to-date:**
   ```bash
   kgrag info myproject-code | grep Updated
   ```
   If old, rebuild:
   ```bash
   kgrag init ~/repos/myproject --wipe
   ```

3. **Increase k to see more options:**
   ```bash
   kgrag pack "term" -k 12  # see more results, then filter manually
   ```

---

## Visualizer Issues

### "Registry not loading" in visualizer

**Symptoms:**
- Visualizer shows "⚠️ No KGs registered"
- Even though `kgrag list` shows KGs

**Solutions:**

1. **Check registry path in visualizer:**
   In sidebar, check "Registry path" input field.
   Should match: `echo $KGRAG_REGISTRY`

2. **Click "🔄 Refresh Registry":**
   Button in sidebar refreshes the loaded registry.

3. **If path is wrong, correct it:**
   Type correct path in "Registry path" field and click outside to reload.

4. **Restart visualizer:**
   ```bash
   # Kill current instance (Ctrl+C)
   # Restart:
   kgrag viz
   ```

---

### "Stats unavailable" for a KG in registry tab

**Symptoms:**
- KG card shows "Stats unavailable: [error message]"

**Solutions:**

1. **Check if KG library is installed:**
   ```bash
   python -c "import code_kg"  # for CodeKGs
   python -c "import doc_kg"   # for DocKGs
   ```
   If import fails, install: `pip install code-kg` or `pip install doc-kg`

2. **Check if databases exist:**
   For CodeKGs:
   ```bash
   ls ~/.codekg/graph.sqlite
   ls ~/.codekg/lancedb
   ```

3. **Rebuild the KG:**
   ```bash
   kgrag init ~/repos/myproject --wipe
   ```

---

### Visualizer is slow or unresponsive

**Symptoms:**
- Visualizer takes long time to load results
- UI feels sluggish

**Solutions:**

1. **Reduce query scope:**
   - In "KG Selection", unselect large projects
   - Filter by kind (code/doc)

2. **Reduce result count:**
   - Set "Top-K results per KG" to smaller number (3-5)

3. **Clear browser cache:**
   - Hard refresh: Cmd+Shift+R (macOS) or Ctrl+Shift+R (Linux/Windows)

4. **Restart visualizer:**
   ```bash
   # Kill (Ctrl+C)
   kgrag viz --port 8502  # use different port if 8501 is busy
   ```

---

## MCP Integration Issues

### "MCP tools not appearing" in Claude Code

**Symptoms:**
- `kgrag_query`, `kgrag_pack`, etc. don't autocomplete
- Tools don't show in tool menu

**Solutions:**

1. **Verify `.mcp.json` exists:**
   ```bash
   ls -la .mcp.json
   # Should be in project root
   ```

2. **Check `.mcp.json` format:**
   Must have:
   ```json
   {
     "mcpServers": {
       "kgrag": {
         "command": "kgrag",
         "args": ["mcp", "--registry", "/ABSOLUTE/PATH/to/registry.sqlite"]
       }
     }
   }
   ```
   ⚠️ **Paths must be absolute (not `~`)**

3. **Restart Claude Code:**
   - Fully quit Claude Code (not just close tab)
   - Reopen project
   - Tools should now appear

4. **Check MCP server is running:**
   ```bash
   # In project directory
   kgrag mcp
   # Should show "MCP server starting..."
   # If errors appear, check registry path
   ```

---

### "MCP tools fail" or return errors

**Symptoms:**
- Tool call returns error in Claude Code
- Error like: "Registry not found"

**Solutions:**

1. **Check registry path in `.mcp.json`:**
   Must be absolute path:
   ```bash
   # Wrong:
   "/home/user/~/.kgrag/registry.sqlite"

   # Right:
   "/home/user/.kgrag/registry.sqlite"
   ```

2. **Verify registry file exists:**
   ```bash
   ls -la /absolute/path/to/registry.sqlite
   ```

3. **If registry path is wrong, update `.mcp.json`:**
   ```bash
   echo $KGRAG_REGISTRY
   # Copy this path to .mcp.json
   ```

4. **Restart Claude Code after editing `.mcp.json`.**

---

## Performance Issues

### "Build takes too long" or hangs

**Symptoms:**
- `kgrag init` runs for 10+ minutes
- Appears to be stuck

**Solutions:**

1. **Let it finish (be patient):**
   Large codebases (10k+ files) can take 5-15 minutes.

2. **Check if process is alive:**
   ```bash
   # In another terminal:
   ps aux | grep codekg
   # Should show active process
   ```

3. **If truly stuck (no activity for 30 min):**
   ```bash
   # Kill process
   pkill -f "codekg build"

   # Retry with smaller scope
   kgrag init ~/repos/myproject --layer code  # skip doc layer if huge
   ```

4. **Reduce vector embedding load:**
   Set batch size:
   ```bash
   CODEKG_BATCH_SIZE=50 kgrag init ~/repos/myproject
   ```

---

### "Large memory usage" during build

**Symptoms:**
- System runs out of memory during `kgrag init`
- Process killed or system freezes

**Solutions:**

1. **Close other applications** to free RAM.

2. **Build in separate terminal/screen** to avoid blocking:
   ```bash
   nohup kgrag init ~/repos/myproject > build.log 2>&1 &
   tail -f build.log  # monitor progress
   ```

3. **Try building layers separately:**
   ```bash
   kgrag init --layer code
   # Wait for completion, then:
   kgrag init --layer doc
   ```

---

## Environment & Configuration Issues

### "Command not found: kgrag"

**Symptoms:**
- `kgrag` command not recognized
- Error: "command not found"

**Solutions:**

1. **Install KGRAG:**
   ```bash
   pip install kgrag
   # or via Poetry:
   poetry add kgrag
   ```

2. **If installed via Poetry, use:**
   ```bash
   poetry run kgrag list
   # instead of just:
   kgrag list
   ```

3. **Add to PATH (if using local venv):**
   ```bash
   export PATH="$HOME/.venv/bin:$PATH"
   # Add to ~/.bashrc or ~/.zshrc for persistence
   ```

---

### "Wrong Python environment"

**Symptoms:**
- `kgrag` works in one terminal but not another
- Different results depending on terminal

**Solutions:**

1. **Check which `kgrag` is running:**
   ```bash
   which kgrag
   ```

2. **Check Python version:**
   ```bash
   kgrag --version
   python --version
   ```

3. **Activate correct venv:**
   ```bash
   source ~/.venv/bin/activate
   # or for Poetry projects:
   poetry shell
   ```

4. **Ensure consistent environment variables:**
   ```bash
   export KGRAG_REGISTRY=$HOME/.kgrag/registry.sqlite
   export CODEKG_MODEL_DIR=$HOME/.models/codekg
   # Add to ~/.bashrc or ~/.zshrc
   ```

---

## Getting Help

If you've tried the above solutions:

1. **Check KGRAG logs:**
   ```bash
   # Most commands output detailed error messages
   kgrag init --wipe 2>&1 | tail -50
   ```

2. **Run with verbose output:**
   ```bash
   python -m kgrag query "term" -v
   ```

3. **Check registry integrity:**
   ```bash
   sqlite3 ~/.kgrag/registry.sqlite ".tables"
   # Should show: entries, kgs
   ```

4. **Open an issue:**
   Include:
   - `kgrag --version`
   - `kgrag status` output
   - Steps to reproduce
   - Error messages (full output)
