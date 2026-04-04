"""kg.py — Re-exports AgentKG for import compatibility.

The canonical ``AgentKG`` implementation lives in :mod:`agent_kg.graph`.
This module re-exports it so that code importing ``from agent_kg.kg import AgentKG``
continues to work without modification.
"""

from agent_kg.graph import AgentKG

__all__ = ["AgentKG"]
