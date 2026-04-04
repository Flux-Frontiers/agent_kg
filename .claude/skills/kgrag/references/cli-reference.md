# KGRAG CLI Reference

Complete documentation for all KGRAG commands.

## kgrag init — Initialize and register KG layers

**Usage:**
```bash
kgrag init [REPO_PATH] [OPTIONS]
```

**Purpose:** Auto-detect applicable KG layers, build them, and register in the registry.

**Options:**
- `--wipe` — Rebuild from scratch (deletes existing databases)
- `--layer [code|doc]` — Explicitly specify layers (repeatable). Default: auto-detect
- `--name TEXT` — Custom name prefix for registered KGs (default: repo directory name)
- `--registry PATH` — Override registry path (default: `KGRAG_REGISTRY` env var or `~/.kgrag/registry.sqlite`)

**Examples:**
```bash
# Auto-detect and build all applicable layers in current repo
kgrag init

# Initialize specific repo
kgrag init ~/repos/myproject

# Build only code layer with custom name
kgrag init . --layer code --name myproject-code

# Rebuild from scratch (wipe existing DBs)
kgrag init --wipe

# Build both code and doc layers explicitly
kgrag init --layer code --layer doc
```

**Output:** Creates and registers KG instances. Check with `kgrag status` or `kgrag list`.

---

## kgrag query — Federated semantic search

**Usage:**
```bash
kgrag query QUERY_TEXT [OPTIONS]
```

**Purpose:** Search all registered KGs with natural language.

**Arguments:**
- `QUERY_TEXT` — Natural-language query string (required)

**Options:**
- `-k INTEGER` — Results per KG (default: 8)
- `--kind [code|doc|meta]` — Filter by KG kind
- `--json` — Output as JSON for automation
- `--registry PATH` — Override registry path

**Examples:**
```bash
# Query all KGs
kgrag query "database connection setup"

# Code KGs only, 5 results per KG
kgrag query "error handling" --kind code -k 5

# DocKGs only
kgrag query "REST API endpoints" --kind doc

# JSON output for scripting
kgrag query "metabolic pathways" --kind meta --json
```

**Output format:**
```
KG: myproject-code
  1. fn:src/db/connection.py:connect_db (0.85)
     Database connection factory
  2. ...

KG: docs-api
  1. chunk:docs/api.md#connection (0.79)
     Connection pooling reference
  2. ...

Global ranking: [sorted by relevance across all KGs]
```

---

## kgrag pack — Extract source snippets

**Usage:**
```bash
kgrag pack QUERY_TEXT [OPTIONS]
```

**Purpose:** Build markdown-formatted snippet pack for LLM context windows.

**Arguments:**
- `QUERY_TEXT` — Natural-language query (required)

**Options:**
- `-k INTEGER` — Snippets per KG (default: 8)
- `--context INTEGER` — Lines of context around code (default: 5)
- `--kind [code|doc|meta]` — Filter by KG kind
- `--out FILE` — Write to file instead of stdout
- `--registry PATH` — Override registry path

**Examples:**
```bash
# Extract snippets across all KGs
kgrag pack "database transaction patterns"

# Code KGs only, 3 lines of context
kgrag pack "error handling" --kind code --context 3 -k 5

# Save to file
kgrag pack "API design patterns" --out snippets.md

# High volume for comprehensive context
kgrag pack "authentication flow" -k 12 --context 10
```

**Output format:**
Markdown with KG source, file path, line numbers, code block, and relevance score.

---

## kgrag analyze — Cross-KG analysis

**Usage:**
```bash
kgrag analyze [OPTIONS]
```

**Purpose:** Show statistics and health metrics across all registered KGs.

**Options:**
- `--json` — Output as JSON
- `--registry PATH` — Override registry path

**Output includes:**
- Total node and edge counts by KG kind
- Docstring coverage percentage
- Critical issues (circular dependencies, orphaned code, etc.)
- Per-KG breakdown

---

## kgrag viz — Launch Streamlit visualizer

**Usage:**
```bash
kgrag viz [OPTIONS]
```

**Purpose:** Interactive web UI for exploring registered KGs.

**Options:**
- `--port INTEGER` — Server port (default: 8501)
- `--registry PATH` — Override registry path

**Tabs:**
- **📋 Registry** — Browse KGs, view stats, check build status
- **🔍 Federated Query** — Search across KGs, display ranked or grouped
- **🧪 Analysis** — Run architectural analysis on CodeKGs
- **📦 Snippet Pack** — Extract snippets with configurable context

**Launch:**
```bash
kgrag viz
# Open browser to http://localhost:8501
```

---

## kgrag list — Show registered KGs

**Usage:**
```bash
kgrag list [OPTIONS]
```

**Purpose:** List all KG instances in the registry.

**Options:**
- `--registry PATH` — Override registry path
- `--json` — Output as JSON

**Output columns:**
- Name
- Kind (code/doc/meta)
- Status (built/not built)
- Version
- Path

---

## kgrag status — Registry health check

**Usage:**
```bash
kgrag status [OPTIONS]
```

**Purpose:** Quick health summary of the registry.

**Options:**
- `--registry PATH` — Override registry path

**Output includes:**
- Total KGs registered
- Built / not built count
- Missing or invalid paths
- Registry location and size

---

## kgrag info — Detailed KG metadata

**Usage:**
```bash
kgrag info KG_NAME [OPTIONS]
```

**Purpose:** Show full details for a specific registered KG.

**Arguments:**
- `KG_NAME` — Name of registered KG

**Options:**
- `--registry PATH` — Override registry path
- `--json` — Output as JSON

**Output includes:**
- Build date and version
- Repo path and venv path
- SQLite and LanceDB paths
- Statistics (node count, edge count, etc.)
- Tags and metadata

---

## kgrag register — Manual KG registration

**Usage:**
```bash
kgrag register [OPTIONS]
```

**Purpose:** Register an existing KG database (usually not needed — `init` handles this).

**Options:**
- `--name TEXT` — KG name (required)
- `--kind [code|doc|meta]` — KG kind (required)
- `--repo PATH` — Repository path (required)
- `--sqlite PATH` — Path to SQLite graph DB
- `--lancedb PATH` — Path to LanceDB vector index
- `--registry PATH` — Override registry path

**Example:**
```bash
kgrag register --name mykg \
  --kind code \
  --repo ~/repos/myproject \
  --sqlite ~/.codekg/graph.sqlite \
  --lancedb ~/.codekg/lancedb
```

---

## kgrag unregister — Remove KG from registry

**Usage:**
```bash
kgrag unregister KG_NAME [OPTIONS]
```

**Purpose:** Remove a KG entry from the registry.

**Arguments:**
- `KG_NAME` — Name of registered KG

**Options:**
- `--registry PATH` — Override registry path
- `--force` — Skip confirmation

**Warning:** Only removes the registry entry, not the actual database files. To fully clean up, manually delete the `.codekg/`, `.dockg/`, or `.metakg/` directories.

---

## kgrag scan — Auto-discover KGs

**Usage:**
```bash
kgrag scan [DIRECTORY] [OPTIONS]
```

**Purpose:** Scan directory tree for existing CodeKG/DocKG databases and suggest registration.

**Arguments:**
- `DIRECTORY` — Directory to scan (default: current directory)

**Options:**
- `--registry PATH` — Override registry path
- `--auto-register` — Automatically register discovered KGs

**Example:**
```bash
# Scan for KGs and show suggestions
kgrag scan ~/repos

# Auto-register discovered KGs
kgrag scan ~/repos --auto-register
```

---

## kgrag mcp — Launch MCP server

**Usage:**
```bash
kgrag mcp [OPTIONS]
```

**Purpose:** Expose KGRAG as MCP tools for Claude Code, Claude Desktop, or other MCP clients.

**Options:**
- `--registry PATH` — Override registry path
- `--host HOST` — Server host (default: localhost)
- `--port PORT` — Server port (default: 3000)

**Exposed tools:**
- `kgrag_query(q, k, kinds)` — Semantic search
- `kgrag_pack(q, k, context, kinds)` — Snippet extraction
- `kgrag_list()` — List registered KGs
- `kgrag_info(name)` — Get KG metadata
- `kgrag_stats()` — Registry health metrics

**Configuration for Claude Code (.mcp.json):**
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

Always use **absolute paths** in .mcp.json.

---

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `KGRAG_REGISTRY` | Path to registry SQLite file | `~/.kgrag/registry.sqlite` |
| `CODEKG_MODEL_DIR` | Cache embedding model (CodeKG) | `.codekg/models` |
| `DOCKG_MODEL_DIR` | Cache embedding model (DocKG) | `.dockg/models` |

**Set in shell profile:**
```bash
export KGRAG_REGISTRY=$HOME/.kgrag/registry.sqlite
export CODEKG_MODEL_DIR=$HOME/.models/codekg
export DOCKG_MODEL_DIR=$HOME/.models/dockg
```

---

## Global Options

All commands support:
- `--help` — Show command help
- `--version` — Show KGRAG version
- `--registry PATH` — Override registry path for any command

Example:
```bash
kgrag --version
kgrag query --help
kgrag init --registry /custom/path/registry.sqlite
```
