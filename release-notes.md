# Release Notes — v0.8.2

> Released: 2026-07-29

A small dependency-hygiene release. AgentKG's floor for `kgmodule-utils` had drifted a
release behind what was published, so a fresh install could resolve an older shared core
than the one the package is developed and tested against. The floor now matches the
current release. There are no code changes and no behavioural difference.

## What changed

**`kgmodule-utils[semantic,sqlite-vec]` floor lifted to `>=0.9.0`.** The floor sat at
`0.8.0` while `0.9.0` was the published release. Nothing was broken by that — the lock file
already resolved higher locally — but a consumer installing from the index could land on
the older core, which is precisely the class of drift that makes bug reports hard to
reproduce. The lock has been regenerated and the suite is green against 0.9.0 (228 passed).

This was the last outstanding piece of a `transformers` CVE branch that has since been
closed as obsolete: the CVE it was named for was already fixed on `main`, with the lock
resolving `transformers` to 5.14.1, well clear of the vulnerable `<4.57` range.

**Housekeeping: `.gitignore` normalized across the KG fleet.** All eleven KG repos now
share one canonical set of ignore rules — databases, vector indexes and model caches are
ignored; `snapshots/` never is. AgentKG was not one of the repos losing snapshot history to
the old rules, but its ignore file now matches its siblings.

## Upgrading

Nothing to do. `pip install --upgrade agent-kg` picks up the corrected floor; no rebuild,
no migration, no API change.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
