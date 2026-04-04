---
name: kgrag
description: "Expert knowledge for KGRAG — the unified cross-KG registry and federated query layer for CodeKG, DocKG, and MetaKG. Use this skill when: (1) Setting up or configuring KGRAG in projects, (2) Querying across multiple knowledge graphs simultaneously, (3) Extracting code/doc snippets for LLM context, (4) Integrating with Claude Code or Claude Desktop, (5) Running architectural analyses, (6) Managing the KG registry, or (7) Troubleshooting KG-related issues."
---

# KGRAG Skill

KGRAG is the **unified abstraction over CodeKG, DocKG, and MetaKG**. It provides a single registry and federated query interface to search across multiple knowledge graphs simultaneously.

## What is KGRAG?

KGRAG (Knowledge Graph Registry and Query) orchestrates multiple KG backends:

- **CodeKG** — Semantic + structural analysis of Python code
- **DocKG** — Semantic + structural analysis of markdown documentation
- **MetaKG** — Domain-specific knowledge graphs
- **KGRAG** — The unifying registry, CLI, and federated query layer

One registry manages all KG instances. One CLI queries all of them. One philosophy: **"One registry. Many KGs. Infinite queries."**

## Core Concepts

### Registry
The KGRAG registry (`~/.kgrag/registry.sqlite` by default) is the source of truth:
- Tracks all KG instances across your projects
- Stores metadata: names, kinds, paths, build status
- Enables federated queries and analysis

### KG Layers
A **KG layer** is a single knowledge graph for a repository:
- **Code layer** (CodeKG) — Python codebase semantic indexing
- **Doc layer** (DocKG) — Markdown documentation semantic indexing
- Multiple layers can coexist in the registry

One project can have both code and doc layers registered simultaneously.

### Federated Queries
Query all KGs in one command:
```bash
kgrag query "database connection"
# Results ranked globally, sourced from all registered KGs
```

## Quick Start

### Initialize a project
```bash
cd ~/repos/myproject
kgrag init
# Auto-detects applicable layers, builds them, registers in registry
```

### Query all KGs
```bash
kgrag query "error handling patterns"
kgrag query "REST API" --kind code -k 5
```

### Extract snippets for LLM
```bash
kgrag pack "authentication flow" --out context.md
```

### Visualize interactively
```bash
kgrag viz
# Launches Streamlit UI: Registry, Federated Query, Analysis, Snippets
```

### Check registry health
```bash
kgrag status
kgrag list
```

## CLI Commands

See [cli-reference.md](references/cli-reference.md) for detailed documentation on all commands:

| Command | Purpose |
|---------|---------|
| `kgrag init` | Initialize and register KG layers for a project |
| `kgrag query` | Federated semantic search across all KGs |
| `kgrag pack` | Extract source snippets for LLM context |
| `kgrag analyze` | Show cross-KG statistics and health metrics |
| `kgrag viz` | Launch Streamlit visualizer (interactive UI) |
| `kgrag list` | Show all registered KG instances |
| `kgrag status` | Quick registry health check |
| `kgrag info` | Detailed metadata for a specific KG |
| `kgrag register` | Manual KG registration (rarely needed) |
| `kgrag unregister` | Remove KG from registry |
| `kgrag scan` | Auto-discover existing KG databases |
| `kgrag mcp` | Launch MCP server for Claude Code/Desktop integration |

**Quick reference:** `kgrag <command> --help` for any command.

## Workflows

See [workflows.md](references/workflows.md) for detailed multi-step workflows:

- **First-time setup** — Initialize KGRAG for one or more projects
- **Preparing LLM context** — Extract snippets for code review or AI analysis
- **Cross-project analysis** — Query patterns across multiple repositories
- **Team collaboration** — Share visualizer with non-technical stakeholders
- **Claude Code integration** — Set up MCP for interactive exploration

### Setup MCP for Claude Code (5 min)

1. Create `.mcp.json` in your project root:
```json
{
  "mcpServers": {
    "kgrag": {
      "command": "kgrag",
      "args": ["mcp", "--registry", "/path/to/registry.sqlite"]
    }
  }
}
```

2. Restart Claude Code — MCP tools appear automatically

3. Now available in prompts:
   - `kgrag_query(q, k, kinds)` — Semantic search
   - `kgrag_pack(q, k, context, kinds)` — Snippet extraction
   - `kgrag_list()` — List registered KGs
   - `kgrag_info(name)` — KG metadata
   - `kgrag_stats()` — Registry health

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `KGRAG_REGISTRY` | Path to registry SQLite file | `~/.kgrag/registry.sqlite` |
| `CODEKG_MODEL_DIR` | Cache embedding model (CodeKG) | `.codekg/models` |
| `DOCKG_MODEL_DIR` | Cache embedding model (DocKG) | `.dockg/models` |

Set these once in your shell profile for permanent configuration.

## Troubleshooting

See [troubleshooting.md](references/troubleshooting.md) for detailed solutions.

**Common issues:**
- **Query returns no results** — Check if KG is built: `kgrag status`
- **KG marked "not built"** — Rebuild: `kgrag init <repo-path> --wipe`
- **MCP tools not appearing** — Verify `.mcp.json` paths are absolute; restart Claude Code
- **Stale results in visualizer** — Click "🔄 Refresh Registry" or rebuild

## Best Practices

**Registry management:**
- Keep a single registry (`~/.kgrag/registry.sqlite`) for your workspace
- Use meaningful names: `project-name-code`, `project-name-doc`
- Run `kgrag status` monthly to catch unbuilt KGs

**Querying:**
- Use specific queries ("JWT validation" > "authentication")
- Filter by kind: `--kind code` or `--kind doc`
- Adjust `-k`: Start with 5 for focused results, 12 for broad surveys

**Rebuilding:**
- After major refactoring: `kgrag init --wipe` (full rebuild)
- After renames: `kgrag init` (incremental, no `--wipe`)
- Monthly health check: Re-run `kgrag init` to catch stale data

## Philosophy

> **One registry. Many KGs. Infinite queries.**

KGRAG unifies CodeKG, DocKG, and MetaKG under a single contract:
- Apps register what they know (a KG instance)
- Users query what they want (federated search)
- Agents orchestrate across domains (MCP tools)

This enables:
- **Cross-domain searches** — Find code and matching documentation in one query
- **Unified CLI** — Same commands work across all KG types
- **Extensibility** — New KG types integrate seamlessly
- **Composability** — Agents layer KGRAG with other tools

## Learn More

- **CodeKG skill** — Semantic + structural indexing of Python code
- **DocKG skill** — Semantic + structural indexing of markdown docs
- **CLI reference** — See [cli-reference.md](references/cli-reference.md)
- **Workflows** — See [workflows.md](references/workflows.md)
- **Troubleshooting** — See [troubleshooting.md](references/troubleshooting.md)
