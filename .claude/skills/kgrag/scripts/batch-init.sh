#!/bin/bash
# batch-init.sh — Initialize multiple projects at once

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Usage
if [ $# -lt 1 ]; then
    echo "Usage: $0 <project1> [project2] [project3] ... [--wipe]"
    echo ""
    echo "Examples:"
    echo "  $0 ~/repos/backend ~/repos/frontend"
    echo "  $0 ~/repos/backend ~/repos/frontend --wipe"
    exit 1
fi

# Parse arguments
PROJECTS=()
WIPE_FLAG=""

for arg in "$@"; do
    if [ "$arg" = "--wipe" ]; then
        WIPE_FLAG="--wipe"
    else
        PROJECTS+=("$arg")
    fi
done

echo -e "${BLUE}Initializing ${#PROJECTS[@]} project(s)...${NC}"
echo ""

# Initialize each project
SUCCESS=0
FAILED=0

for project in "${PROJECTS[@]}"; do
    if [ ! -d "$project" ]; then
        echo -e "${RED}✗ Project not found: $project${NC}"
        ((FAILED++))
        continue
    fi

    project_name=$(basename "$project")
    echo -e "${BLUE}Initializing: $project_name${NC}"

    if kgrag init "$project" $WIPE_FLAG > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Success: $project_name${NC}"
        ((SUCCESS++))
    else
        echo -e "${RED}✗ Failed: $project_name${NC}"
        ((FAILED++))
    fi
    echo ""
done

# Summary
echo -e "${BLUE}Summary:${NC}"
echo -e "${GREEN}✓ Initialized: $SUCCESS${NC}"
if [ $FAILED -gt 0 ]; then
    echo -e "${RED}✗ Failed: $FAILED${NC}"
fi

# Show registry status
echo ""
echo -e "${BLUE}Registry status:${NC}"
kgrag status

exit $FAILED
