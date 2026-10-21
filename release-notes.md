# Release Notes -- v0.13.0

> Released: 2026-10-21

AgentKG keeps a global profile for each person, and until now that profile
always lived under `~/.kgrag/profiles/`. This release lets the profile root
move: pass `profile_root` to `AgentKG`, or set `AGENTKG_PROFILE_ROOT`.
Programs that run AgentKG for agents other than you, such as the book-tree
agents in gutenberg_kg's moots, can now keep those profiles out of yours.
Nothing changes unless you set one of the two.

## What changed

**Profiles can live in any directory.** The profile location was written out
by hand in seven places: the `AgentKG` constructor, the MCP `agent_kg_profile`
tool, the explorer app, and the `init`, `wipe --global` and `viz` commands.
All of them now ask one resolver, `agent_kg.user_profile.profile_root()`
(with `profile_dir(person_id)` for one person's directory). An explicit
`profile_root` argument wins, then the `AGENTKG_PROFILE_ROOT` environment
variable, then `~/.kgrag/profiles`. Because the CLI, the MCP server and the
app all follow the variable, setting it once in a shell or an MCP config moves
every entry point together, including what `wipe --global` deletes.

**Dependencies are current.** The lock now carries the latest fleet releases,
including `kgmodule-utils` 0.27.1, and the dependency updates that cleared 25
Dependabot alerts. No dependency floor changed. Maintainers no longer get
`doc-kg` and `pycode-kg` from a repo-local Poetry group; those are installed
once as global tools.

**Synthesis tests find a keyed oMLX server.** The integration tests now read
a local backend's key from `OMLX_API` or `OLLAMA_API`. Before this, an oMLX
server started with a key answered 401, and the tests skipped as though no
server were running.

## Upgrading

Upgrade with `pip install -U agent-kg`, or `uv tool upgrade agent-kg` for a
tool install. No data migration is needed, and existing profiles stay where
they are. To move profiles, set `AGENTKG_PROFILE_ROOT` and move the
`<person>/` directories to the new root yourself; AgentKG does not copy them.

Code that patched the private `agent_kg.graph._PROFILE_BASE` constant, as
some tests did, should set `AGENTKG_PROFILE_ROOT` instead. The constant is
gone, so such a patch now fails with an `AttributeError`.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
