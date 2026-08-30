# Release Notes — v0.9.0

> Released: 2026-08-30

This release closes out a month of work that had accumulated without a version bump, and
most of it is about trust in what the graph actually contains. The headline fix enforces
foreign keys that had silently never been active: every node deletion since the first
release left its edges behind, and sampled fleet graphs carried tens of thousands of
edges pointing at nodes that no longer existed. A second, related fix stops `ingest` from
storing the same turn twice — roughly half the turns in some production graphs were
duplicates — and corrects the recall path that was supposed to filter them back out but
never actually excluded anything. Hooks also got a round of session-isolation fixes after
a live incident where one session working in a sibling repo pruned another repo's history
by mistake.

## What changed

**Data integrity.** Foreign-key enforcement was always declared on the schema but never
turned on at the connection level, so `ON DELETE CASCADE` did nothing and orphaned edges
piled up indefinitely. Turning the pragma on required rewriting `upsert_node` to update in
place instead of delete-and-reinsert, and reworking the dedup migration to repoint edges
before removing duplicate nodes rather than after. A one-time migration cleans up the
historical damage on next open.

**Duplicate turns.** A caller invoking `ingest` twice for the same turn went uncaught,
inflating stored history and burning through the recall token budget on copies. `ingest`
now rejects a same-session repeat within a five-second window, narrow enough that a
genuinely repeated short message minutes later still gets recorded. `assemble`'s recall
path is deduplicated the same way.

**Session isolation.** Hooks previously inferred which repository and session they
belonged to from the process's working directory, which a hook does not control reliably.
That let one session's activity leak into a different repo's history and let concurrent
conversations get merged into a single pruning pass. Both are now bound explicitly:
repository resolution prefers `CLAUDE_PROJECT_DIR` or the session transcript's recorded
starting directory, and every hook call now passes its session id through instead of
letting the store guess.

**Recall actually recalls.** `UserPromptSubmit` used to only write into the graph and
return nothing; it now assembles a token-budgeted context block from the graph and returns
it as `additionalContext`, so retrieval is finally wired into the conversation loop it was
built for.

**Temporal contract.** `Node.temporal()` adopts the shared `kg_utils.temporal` interval
contract, so a federated time-window query now matches a topic anywhere across its
first-seen-to-last-seen span rather than only at the moment it first appeared.

**Housekeeping.** Dependency floors (`kgmodule-utils`, `doc-kg`, `pycode-kg`) were brought
current; dev tooling moved from a pip-installable extra to an optional Poetry group so it
no longer ships in the wheel; `pytest`, `cryptography`, `gitpython`, `setuptools`, and
`torch` were bumped to close known security advisories; and the pre-commit hook chain was
reordered so index rebuilds no longer race `pre-commit run`'s stash/restore cycle.

## Upgrading

Existing graphs pick up the orphaned-edge cleanup automatically on next open — it's
idempotent and a no-op once a graph is clean. Anyone with Claude Code hooks installed
should re-run `agentkg install-hooks --force` to pick up the session-binding and
ordering fixes; hooks are written per-clone and are not updated automatically.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
