#!/bin/bash
# setup-kgrag-mcp.sh — Configure KGRAG MCP for Claude Code

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}KGRAG MCP Setup${NC}"
echo "Configures .mcp.json for KGRAG integration with Claude Code"
echo ""

# Check if we're in a project directory
if [ ! -f "pyproject.toml" ] && [ ! -f "package.json" ] && [ ! -d ".git" ]; then
    echo -e "${YELLOW}Warning: Not in a project root. Proceeding anyway.${NC}"
fi

# Get registry path
REGISTRY_PATH="${KGRAG_REGISTRY:-$HOME/.kgrag/registry.sqlite}"

# Resolve to absolute path
REGISTRY_PATH=$(cd "$(dirname "$REGISTRY_PATH")" && pwd)/$(basename "$REGISTRY_PATH")

echo "Registry path: $REGISTRY_PATH"
echo ""

# Create .mcp.json
MCP_CONFIG='{
  "mcpServers": {
    "kgrag": {
      "command": "kgrag",
      "args": ["mcp", "--registry", "'$REGISTRY_PATH'"]
    }
  }
}'

# Check if .mcp.json already exists
if [ -f ".mcp.json" ]; then
    echo -e "${YELLOW}Warning: .mcp.json already exists${NC}"
    echo "Backing up to .mcp.json.bak"
    cp .mcp.json .mcp.json.bak
fi

# Write .mcp.json
echo "$MCP_CONFIG" > .mcp.json
echo -e "${GREEN}✓ Created .mcp.json${NC}"

# Verify
echo ""
echo -e "${BLUE}Configuration:${NC}"
cat .mcp.json | head -10
echo ""

# Test MCP server
echo -e "${BLUE}Testing MCP server...${NC}"
if kgrag mcp --help > /dev/null 2>&1; then
    echo -e "${GREEN}✓ MCP server available${NC}"
else
    echo -e "${YELLOW}Warning: kgrag mcp command not found${NC}"
    echo "Make sure KGRAG is installed: pip install kgrag"
fi

echo ""
echo -e "${GREEN}Setup complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Restart Claude Code (fully quit and reopen)"
echo "2. MCP tools will be available in prompts:"
echo "   - kgrag_query(q, k, kinds)"
echo "   - kgrag_pack(q, k, context, kinds)"
echo "   - kgrag_list()"
echo "   - kgrag_info(name)"
echo "   - kgrag_stats()"
