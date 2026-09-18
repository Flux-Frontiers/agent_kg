# Release Notes -- v0.12.1

> Released: 2026-09-18

A one-fix patch release. AgentKG's Claude Code hooks decide which repository a
session belongs to before they record the conversation into its graph, and the
Stop hook prunes that same graph. This release makes that decision reliable
when the hook's process has inherited a `GIT_DIR` pointing somewhere else.

## What changed

**Repo resolution ignores an inherited `GIT_DIR`.** The resolver normalises a
session's project directory to its git work tree by running `git rev-parse
--show-toplevel`, and it passed the caller's environment through. Git exports
`GIT_DIR` to the processes it spawns during a commit made from a linked
worktree, and with it set, git answers for the repository that variable names
rather than the directory being asked about. A hook running in such a process
could therefore record into, or prune, the wrong repository's graph. The
resolver now strips `GIT_*` variables from git's environment. A hook running
from an ordinary Claude Code prompt, where `GIT_DIR` is not set, was never
affected.

## Upgrading

Upgrade with `pip install -U agent-kg`, or `uv tool upgrade agent-kg` for a
tool install, then run `agentkg install-hooks` once. The installer copies the
hook scripts and the resolver into `~/.agentkg/hooks/`, so hooks keep running
the old copy until it is refreshed. No data migration or configuration change
is needed.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
