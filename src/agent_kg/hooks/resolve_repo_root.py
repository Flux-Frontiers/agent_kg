# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""Resolve the repository a Claude Code session belongs to.

A hook process inherits whatever working directory the agent's shell last moved
to. Deriving the repo from that directory points the conversation graph -- and,
via the Stop hook, ``prune`` -- at whichever sibling repo the session happened
to inspect, which is how an unrelated repo's history gets rewritten. This module
resolves the session's own project directory instead.

Order of preference:

1. ``CLAUDE_PROJECT_DIR``, exported by Claude Code for hook commands.
2. The first ``cwd`` recorded in the session transcript. Entries are appended in
   order and the first is written at session start, before any tool has run, so
   it names the project directory; later entries follow the shell and must not
   be used.
3. The process working directory, as a last resort -- the previous behaviour.

The result is normalized to the enclosing git work tree when there is one.

Deliberately free of ``agent_kg`` imports: this runs on the critical path of
every user prompt, where the package's import cost would be paid twice.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path


def first_transcript_cwd(transcript_path: str | os.PathLike[str]) -> str | None:
    """Return the first ``cwd`` recorded in a session transcript.

    :param transcript_path: Path to the session's ``.jsonl`` transcript.
    :return: The recorded directory, or None if unreadable or absent.
    """
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if isinstance(entry, dict):
                    cwd = entry.get("cwd")
                    if isinstance(cwd, str) and cwd:
                        return cwd
    except OSError:
        return None
    return None


def git_toplevel(path: str | os.PathLike[str]) -> str | None:
    """Return the git work tree containing ``path``, if any.

    :param path: Directory to inspect.
    :return: Absolute path to the work tree root, or None.
    """
    try:
        done = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    root = done.stdout.strip()
    return root if done.returncode == 0 and root else None


def resolve_repo_root(
    transcript_path: str | None = None,
    env: Mapping[str, str] | None = None,
    cwd: str | None = None,
) -> str:
    """Resolve the repository root for the current session.

    :param transcript_path: Path to the session transcript, if the hook got one.
    :param env: Environment to read ``CLAUDE_PROJECT_DIR`` from (default os.environ).
    :param cwd: Fallback working directory (default the process cwd).
    :return: Absolute path to the resolved repository root.
    """
    environ: Mapping[str, str] = os.environ if env is None else env
    working_dir: str = os.getcwd() if cwd is None else cwd

    candidate: str | None = None

    project_dir = environ.get("CLAUDE_PROJECT_DIR", "").strip()
    if project_dir and Path(project_dir).is_dir():
        candidate = project_dir

    if candidate is None and transcript_path:
        recorded = first_transcript_cwd(transcript_path)
        if recorded and Path(recorded).is_dir():
            candidate = recorded

    if candidate is None:
        candidate = working_dir

    return git_toplevel(candidate) or str(Path(candidate).resolve())


def main(argv: list[str] | None = None) -> int:
    """Print the resolved repository root.

    :param argv: Optional argument list; ``argv[0]`` is the transcript path.
    :return: Process exit status.
    """
    args = sys.argv[1:] if argv is None else argv
    print(resolve_repo_root(transcript_path=args[0] if args else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
