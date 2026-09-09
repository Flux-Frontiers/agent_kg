# Release Notes — v0.11.0

> Released: 2026-09-08

AgentKG's `SnapshotManager` sheds the last of its hand-rolled boilerplate,
now that the fleet's shared snapshot base carries what every KG module was
independently reimplementing.

## What changed

**`SnapshotManager.__init__` is gone.** It existed only to forward to
`super().__init__()` and set one string. `kgmodule-utils` 0.20.0 replaced
that pattern fleet-wide with a `package_name` class attribute, and AgentKG's
override — along with the same override in seven of the fleet's eight other
KG modules — is retired in favor of it. Nothing else about snapshot capture,
storage, or the on-disk schema changes.

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

If you subclassed `agent_kg.snapshots.SnapshotManager` and called
`super().__init__()` yourself, that call now resolves to the shared base
class directly — nothing further is required unless your subclass depended
on AgentKG's `__init__` running any AgentKG-specific logic, which it never
did. Otherwise, bump `kgmodule-utils` to `>=0.20.0` and `poetry install`;
no other action is needed.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
