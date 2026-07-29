# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""Import-level regression tests for agent_kg.mcp.server.

The MCP server registers its handlers with module-level decorators, so an
incompatible ``mcp`` release breaks it at *import* time, not at call time.
Nothing else in the suite imports this module, which is how mcp 2.0 —
where the low-level ``Server`` decorator API was removed — shipped past CI
in 0.8.0 and left ``agentkg-mcp`` crashing for every PyPI installer.
"""

import importlib


def test_server_module_imports():
    """The module must import cleanly against the installed mcp release."""
    importlib.import_module("agent_kg.mcp.server")


def test_entry_point_target_exists():
    """``agentkg-mcp`` resolves to agent_kg.mcp.server:main."""
    server = importlib.import_module("agent_kg.mcp.server")
    assert callable(server.main)


def test_tools_are_registered():
    """The tool list survives registration and is non-empty."""
    server = importlib.import_module("agent_kg.mcp.server")
    names = [t.name for t in server._TOOLS]
    assert names, "no tools registered"
    assert "agent_kg_query" in names
