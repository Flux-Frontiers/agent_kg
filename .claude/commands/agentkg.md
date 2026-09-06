# AgentKG Skill

Activate expert knowledge for installing, configuring, and using AgentKG -- conversational memory as a live, queryable knowledge graph.

Read and follow the instructions in `.claude/skills/agent-kg/SKILL.md`, then assist the user with their AgentKG request.

If the user provided an argument (e.g. `/agentkg assemble`), treat it as their specific question or task within the AgentKG domain.

If no argument was provided, briefly summarize what AgentKG is and what you can help with, then ask what the user needs.
