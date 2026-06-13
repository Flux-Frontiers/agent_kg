# AgentKG ↔ Sister-Repo Alignment Assessment

**Repository:** https://github.com/Flux-Frontiers/agent_kg
**Reference sister repo:** https://github.com/Flux-Frontiers/pycode_kg (`pycode-kg` 0.19.3)
**Date:** 2026-06-13
**Scope:** Parity of shared build/CI/tooling/agent-harness conventions across the KGModule family — *not* the domain code, which is correctly different per package.

---

## 1. The Sister-Repo Ecosystem

AgentKG is one member of a family of domain knowledge-graph tools that all sit on the
same foundation and are designed to interoperate. Understanding the family is what makes
"alignment" meaningful — these repos are deliberately kept structurally identical so a
change learned in one transfers to all.

| Project | Package | Indexes | Storage | Exposed via |
|---|---|---|---|---|
| **CodeKG → PyCodeKG** | `pycode-kg` | Python source (AST + semantics) | SQLite + LanceDB | MCP |
| **DocKG** | `doc-kg` | Document corpora (`.md`/`.txt`) | SQLite + LanceDB | MCP |
| **AgentKG** *(this repo)* | `agent-kg` | Conversational memory (turns, topics, entities, intents, tasks, preferences) | SQLite + LanceDB | MCP |
| **MetaKG / Metabo_kg** | `metabokg` | Metabolic data | SQLite + LanceDB | MCP |
| **KGRAG** | `kgrag` | — (federation layer) | cross-KG registry | MCP |
| **kgmodule-utils** | `kgmodule-utils` | — (shared SDK) | — | — |

**Shared substrate every repo inherits:**
- Poetry 2.x + PEP 621 (`[project]`) packaging, Elastic-2.0 license, single author.
- Identical dev toolchain: **ruff** (lint+format), **ty** (type-check), **pylint**,
  **detect-secrets**, **pytest** — wired through `.pre-commit-config.yaml` and a
  three-job CI (`Lint & Format` / `Type Check` / `Test`).
- A `Publish` workflow on `v*` tags that builds + cuts a GitHub Release.
- Snapshot CI (`.github/SNAPSHOTS_CI.md`) that commits KG snapshots into `.<kg>/snapshots/`.
- A `.claude/` harness: per-KG **skill** + slash-**commands**, shared cross-cutting skills
  (`kgrag`, `dockg`, `new-kg-module`, `publish`, `skill-creator`, `documentation-lookup`),
  and an MCP server entry point.
- Federation: `new-kg-module` scaffolds a new domain on the SDK; KGRAG registers and
  queries across all of them.

The relevant consequence: **CodeKG was renamed to PyCodeKG** (`code-kg` is gone from
PyPI; `pycode-kg` is the live package). That rename is the single biggest source of
residual drift in this repo.

---

## 2. What This Round of Alignment Already Fixed (merged, PR #1)

| Area | Change |
|---|---|
| Type checker | Migrated **mypy → ty** (Astral) in `pyproject.toml` (`[tool.ty.environment]` + `[tool.ty.rules]`), the `dev`/`all` extras, the pre-commit local hook, and the CI `Type Check` step. Converted one mypy-style `# type: ignore[arg-type]` to ty's `# ty: ignore[invalid-argument-type]`. |
| Lint | Bumped `ruff-pre-commit` `v0.9.10 → v0.15.13` (`ruff` → `ruff-check`). |
| Dep floors | `pycode-kg >=0.16.0 → >=0.19.0`, `doc-kg >=0.11.0 → >=0.15.2`, `kgmodule-utils >=0.2.0 → >=0.3.1` (0.2.0 no longer resolves on PyPI — was blocking the lock). Regenerated `poetry.lock`. |
| Stale refs | Removed dead `.codekg/` entries from pre-commit excludes (repo uses `.pycodekg/`). |
| Publish | Dropped the `poetry publish` step to match the sister (GitHub-Release-only). |

CI is green on all three jobs post-merge.

---

## 3. Residual Gaps (prioritised)

Legend: **P1** = correctness/latent-bug or breaks the family invariant · **P2** = harness/DX
parity · **P3** = cosmetic/historical.

### P1 — pytest markers are used but not registered
`ci.yml` runs `pytest -m "not integration"`, but `[tool.pytest.ini_options]` declares **no**
`markers`. The sister repo registers them:

```toml
markers = [
    "slow: marks tests as slow (deselect with '-m not slow')",
    "integration: marks tests that exercise real external dependencies (model, LanceDB)",
]
```

Today this only emits `PytestUnknownMarkWarning` (CI doesn't run `-W error`), and no test
actually carries `@pytest.mark.integration`, so `-m "not integration"` silently selects
everything. But it's a latent trap: the moment someone adds `filterwarnings = ["error"]`
(common hardening) or tags an integration test, behaviour diverges from intent.
**Fix:** add the `markers` block; tag the LanceDB/model-dependent tests. Low effort.

### P1 — `code-kg` → `pycode-kg` rename is only half-applied
`pyproject.toml` correctly depends on `pycode-kg`, but the `.claude/` harness and configs
still speak the old `codekg` name:
- `.claude/skills/codekg/` and `.claude/skills/codekg-thorough-analysis/` (sister:
  `pycodekg/`, `pycodekg-thorough-analysis/`).
- `.claude/commands/codekg.md`, `.claude/commands/setup-codekg-mcp.md` (sister:
  `pycodekg.md`, `setup-pycodekg-mcp.md`).
- `.mcp.json.bak` defines an MCP server `"codekg"` → `.venv/bin/codekg` — that binary no
  longer exists; the entry point is `pycodekg`.
- ~240 `codekg` string references across those skill docs, `release.md`, `sync-mcp-docs.md`,
  CHANGELOG, and `analysis/`.

This is a self-consistency/breakage issue (the MCP entry and CLI names are wrong), not just
cosmetics. **Fix:** rename the two skill dirs + two command files, repoint `.mcp.json.bak`,
and sweep `codekg` → `pycodekg` in the skill/command bodies. It's mechanical but large; best
done as its own focused PR (mirrors what the sister already did).

### P2 — Missing `CLAUDE.md`
The sister ships a root `CLAUDE.md` (agent identity, project overview, toolkit table,
copilot/agents/commands index, session-management + project rules incl. "MCP Instruction
Sync"). AgentKG has none, so an agent landing here gets no house guidance. **Fix:** author an
AgentKG-flavoured `CLAUDE.md` from the sister's section template, swapping the PyCodeKG
toolkit table for the `agent-kg-*` CLI/MCP surface.

### P2 — Missing `.claude/agents/`
Sister has reusable subagents `doc.md` (technical writer) and `qa.md` (test strategy); both
are domain-agnostic and copy over verbatim. AgentKG lacks the `agents/` dir entirely.

### P2 — Thin `.vscode/`
Sister: `settings.json`, `extensions.json`, `mcp.json`, `tasks.json`, `copilot-instructions.md`.
AgentKG: only a (differing) `settings.json`. The `mcp.json`/`tasks.json`/`copilot-instructions.md`
give IDE users the same MCP wiring and task runner the rest of the family enjoys (adapt the
MCP server name to `agent-kg-mcp`).

### P2 — Shared-skill drift
The cross-cutting skills that are *supposed* to be identical across the family have diverged:
`kgrag` (SKILL + all 3 references), `kgrag-usage`, `new-kg-module`, and `publish` differ from
the sister; `dockg`, `skill-creator`, `documentation-lookup` are already identical. The sister
copies are newer. **Fix:** re-sync the four drifted skills from the canonical source (these
are family-wide, so they should track one upstream, not be edited per-repo).

### P3 — Minor / judgement calls
- `[[tool.poetry.source]] testpypi` and the root `settings.json` / `settings.json.template`
  exist here but not in the sister. Likely intentional (AgentKG isn't on PyPI yet, so a
  TestPyPI source + settings template make sense) — flagged, not recommended for removal.
- Extra `.claude/commands/continue.md` (not in sister) — harmless, keep.
- **Publishing is now manual** post-PR #1. That's correct *for now* (agent-kg isn't on PyPI),
  but when AgentKG does ship to PyPI, the publish path must be re-decided (re-add the step or
  publish via the `publish` skill) — noted so it isn't forgotten.

---

## 4. Recommended Sequencing

1. **Quick win (this could be a tiny PR):** register the pytest `markers` (P1) — closes the
   one latent correctness gap and finishes the pyproject alignment.
2. **`codekg` → `pycodekg` sweep (own PR):** rename skill dirs + command files, fix
   `.mcp.json.bak`, sweep doc references (P1). High value, mechanical, mirrors the sister.
3. **Harness parity (own PR):** add `CLAUDE.md`, `.claude/agents/`, and the missing `.vscode/`
   files (P2), adapted to the `agent-kg` surface.
4. **Skill re-sync (own PR or automated):** pull the four drifted shared skills from canonical
   (P2). Consider a `make sync-skills` / CI check so the family doesn't drift again.

---

## 5. Bottom Line

After PR #1, AgentKG's **build + CI toolchain is in parity** with the family (ruff/ty/pylint/
detect-secrets/pytest, aligned pre-commit, aligned publish, current dep floors). The remaining
drift is concentrated in two places: (a) the **half-finished `codekg`→`pycodekg` rename**
inside the agent harness — the only item with actual broken references — and (b) **harness
parity** (`CLAUDE.md`, `agents/`, `.vscode/`, drifted shared skills). None of it is
architecturally risky; it's mechanical catch-up to conventions the sister already adopted. The
single highest-leverage next step is the pytest-marker fix (trivial), followed by the
`pycodekg` rename sweep.
