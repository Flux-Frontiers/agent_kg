# Release Notes — v0.10.0

> Released: 2026-09-06

AgentKG's snapshots move onto the fleet's shared model, and a one-line
installer now sets up the whole AI-agent integration in a single command.

## What changed

**Snapshots are built on the shared `kg_utils.snapshots` model.** Until now,
AgentKG's snapshot support was a completely standalone reimplementation with
no relationship to the rest of the fleet: a bare timestamp filename, no
manifest, no tag keying, and no `subject`/`tool`/`tool_version` provenance.
It had none of the fixes the shared infrastructure has picked up over the
past several releases, including a fix shipped just this week for a
backfilled delta that silently dropped domain-specific fields.

`AgentKG.snapshot()` and `agentkg snapshot` now take an optional release tag
and a `--subject`, the same convention every other KG module in the fleet
uses: pass the tag when snapshotting a release, omit it for an ordinary
conversation graph and get a UTC timestamp instead. `.agentkg/snapshots/`
keeps its directory layout, but the files in it now carry the shared schema,
and a `manifest.json` index is written alongside them for the first time.
This is a breaking format change for anything reading those files directly;
nothing in this repo does.

**A one-line installer.** `scripts/install-skill.sh` sets up everything a
repository needs to give an AI coding agent persistent conversational
memory: the skill files, the `/agentkg` slash command, the CLI itself if
it's missing, the embedding model, the auto-ingest hooks, and MCP server
configuration for Claude Code, Kilo Code, GitHub Copilot, and Cline.

```bash
curl -fsSL https://raw.githubusercontent.com/Flux-Frontiers/agent_kg/main/scripts/install-skill.sh | bash
```

It's idempotent, supports a `--dry-run` preview, and backs up
`~/.claude.json` before writing to it.

**PyPI publishing.** The previous release, `v0.9.0`, was tagged and
GitHub-released but never reached PyPI — the workflow had no publish step.
This release adds one, using PyPI's Trusted Publishing.

## Upgrading

Dependency floors moved to match currently-published releases:
`kgmodule-utils` to `>=0.19.1` (needed for the snapshot delta fix to take
effect), `doc-kg` to `>=0.24.1`, `pycode-kg` to `>=0.26.0`.

If your own code reads `.agentkg/snapshots/*.json` directly, expect the new
schema. Nothing else requires action — `AgentKG.snapshot()` and
`agentkg snapshot` work without arguments exactly as before, just with
richer output when you pass a tag and subject.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
