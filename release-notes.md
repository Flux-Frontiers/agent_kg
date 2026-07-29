# Release Notes — v0.8.1

> Released: 2026-07-29

A patch over [v0.8.0](https://github.com/Flux-Frontiers/agent_kg/releases/tag/v0.8.0), which carried the sqlite-vec migration. It fixes a dependency bound that left the MCP server unusable for anyone installing from PyPI. Since 0.8.0 was built but never published to PyPI, 0.8.1 is the first release of this line to land there — the migration notes in 0.8.0 still describe what you are upgrading into, and remain required reading.

## What changed

**`agentkg-mcp` no longer crashes on a fresh install.** The `mcp` dependency was declared as `>=1.0.0` with no upper bound. mcp 2.0.0 removed the low-level `Server` decorator API that `agent_kg.mcp.server` registers its handlers on, so a clean `pip install agent-kg` resolved a version where the module raised `AttributeError` at import — taking down the `agentkg-mcp` console script and any `.mcp.json` integration with it. The dependency is now pinned to `mcp>=1.0.0,<2`, which is the 1.28.x line the lock file and test suite had been exercising all along. Porting to the mcp 2.x API is a rewrite rather than a rename, and is deferred to a later release.

**A regression test that would have caught it.** Nothing in the suite imported `agent_kg.mcp.server`, so a module that fails at import time still reported green in CI — the handlers are registered by module-level decorators, meaning breakage happens on import, not on call. `tests/test_mcp_server.py` now covers the import, the console-script target, and tool registration. It was verified to fail against mcp 2.0 and pass against 1.28.1.

## Upgrading

Nothing to do beyond the 0.8.0 migration, which still applies if you are coming from 0.7.x: delete `.agentkg/lancedb/` and run `agentkg reindex`. If you installed 0.8.0 from the GitHub release artifacts and your MCP server stopped working, upgrading to 0.8.1 restores it with no configuration change.

The broader lesson is worth stating: a lock file constrains only this repository's own installs, never what a downstream consumer resolves from an unbounded range. Version floors without ceilings on packages that expose an evolving API are a publishing risk, not a local one.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
