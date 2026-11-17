# Release Notes -- v0.14.1

> Released: 2026-11-17

### Changed

- **kgmodule-utils floor raised to 0.30.2.** That release stops the `omlx`
  synthesis backend from falling back to `OPENAI_API_KEY`, which sent the
  OpenAI key to oMLX whenever `VLLM_API_KEY` was unset. Together with the hook
  fix below, `agentkg prune` summarizes again on oMLX.

### Fixed

- **The Stop and PreCompact hooks give oMLX its API key.** They run
  `agentkg prune` with `SYNTH_BACKEND=omlx` by default, but a hook process
  has no `VLLM_API_KEY`, so oMLX rejected the summarization requests with
  401. When the backend is omlx and `VLLM_API_KEY` is unset or empty, the
  hooks now read `auth.api_key` from `~/.omlx/settings.json` at run time and
  export it for `prune`. The key is never printed or written to a file; a
  missing settings file or key leaves the variable unset and the hook runs
  as before. Other backends are unaffected. Re-run `agentkg install-hooks --global`
  to deploy the updated scripts.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
