# Release Notes — v0.11.0

> Released: 2026-09-08

AgentKG's `SnapshotManager` drops its last hand-rolled override, now that
the fleet's shared snapshot base covers it.

## What changed

**`SnapshotManager.__init__` is gone.** It forwarded to `super().__init__()`
to set one string. `kgmodule-utils` 0.20.0 replaces that pattern fleet-wide
with a `package_name` class attribute; AgentKG's override, along with the
same override in seven of the fleet's eight other KG modules, is retired in
favor of it. Snapshot capture, storage, and the on-disk schema are
unchanged.

**The `kgmodule-utils` floor moves to `>=0.20.0`**, and it's a hard
requirement rather than a preference: against 0.19.x, the base class has no
`package_name` attribute, and every snapshot's `tool` field would silently
read `"kg-utils"` instead of `"agent-kg"`.

**Tooling pins for `doc-kg` and `pycode-kg` moved up** to the releases that
retired those packages' own snapshot overrides — 0.26.0 and 0.27.0
respectively — so `poetry install --with kg` can no longer resolve a version
of either that predates the shared extension points it now depends on.

**The README gained a Citation section**, with APA and BibTeX blocks
matching the convention used across the rest of the fleet, alongside the
existing `CITATION.cff`.

## Upgrading

Bump `kgmodule-utils` to `>=0.20.0` and run `poetry install`. If you
subclassed `agent_kg.snapshots.SnapshotManager` and called
`super().__init__()`, that call now resolves to the shared base class
directly; AgentKG's `__init__` never did anything beyond that.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
