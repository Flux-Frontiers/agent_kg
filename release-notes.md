# Release Notes — v0.4.0

> Released: 2026-04-05

### Added

- **`UserProfileStore.set_identity()` / `get_identity()`** — singleton identity record
  with structured personal/biographical fields: `name`, `email`, `phone`, `address`,
  `birth_date`, `gender`, `cognitive_score` (0–100, clamped), `delta_year` (0–150, clamped)
- **`NodeKind.EDUCATION`** — new graph node kind for education entries
  (e.g. `"PhD CS, MIT, 1998"`); stored as repeatable nodes, shown in `profile` output
- **`UserProfileStore.delete()` / `clear_kind()`** — remove a single node by kind+label
  (case-insensitive) or wipe all nodes of a given kind; return row count
- **`UserProfileStore.education()`** — convenience accessor for EDUCATION nodes
- **`agent-kg profile-set`** CLI command — update identity fields and/or add preference,
  commitment, expertise, interest, style, or education nodes in one call; all node options
  are repeatable; only supplied options are written
- **`agent-kg profile-remove`** CLI command — remove specific nodes by label or wipe
  entire categories with `--clear-<kind>` flags; `--clear-all` wipes every node while
  preserving the identity record
- **`install-hooks --claude`** flag — writes Claude Code `UserPromptSubmit` + `Stop`
  auto-ingest hooks into `.claude/settings.json` of the target repo
- **`install-hooks --global`** flag — writes the same hooks into `~/.claude/settings.json`
  so every repo captures turns automatically
- **`Stop` hook ingests assistant turns** — `last_assistant_message` field captured from
  the Stop hook payload and ingested as an assistant turn with `--no-embed`
- **Onboarding Phase 0 (Personal Identity)** — structured identity questions (name, email,
  phone, address, birth date, gender, cognitive score, delta year) collected before the
  existing phases and written directly to the identity record
- **Onboarding Phase 0b (Education)** — free-entry loop stores each line as an EDUCATION node
- **`render_markdown()` Identity + Education sections** — profile output now opens with
  structured identity fields and education entries above the graph node sections
- **`summary()` includes `identity` and `education` keys** for PersonCorpusEntry sync

### Fixed

- **`whenever` NLP commitment pattern** — added `whenever` to `_COMMITMENT_ALWAYS` regex
  so turns like `"whenever we write new code, write pytest tests"` are auto-extracted
  as commitments without requiring manual `profile-set`
- **`profile-set` mypy error** — replaced `**identity_kwargs` unpacking (typed as
  `dict[str, str | int | None]`) with explicit keyword arguments to satisfy mypy

### Changed

- **`install-hooks` docstring and module header** updated to describe both git pre-commit
  and Claude Code hook installation paths

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
