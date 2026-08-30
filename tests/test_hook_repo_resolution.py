# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""Unit tests for the hook repo-root resolver.

Regression coverage for a defect that rewrote an unrelated repository: the
hooks derived their target from the process working directory, which a hook
inherits from the agent's shell. A session that merely inspected a sibling repo
therefore ingested into it and, via the Stop hook's prune, compressed its
history.

The module is loaded from its file path rather than imported as
``agent_kg.hooks.resolve_repo_root`` because ``hooks/`` ships as package data
with no ``__init__.py`` -- the hooks invoke it as a standalone script, and these
tests exercise it the same way.
"""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "src/agent_kg/hooks/resolve_repo_root.py"


def _load():
    spec = importlib.util.spec_from_file_location("resolve_repo_root", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


resolver = _load()


def _git_repo(path):
    """Create a git work tree at ``path`` and return it."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True, capture_output=True)
    return path


def _transcript(path, cwds):
    """Write a JSONL transcript recording ``cwds`` in order."""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"type": "header", "sessionId": "abc"}) + "\n")
        for cwd in cwds:
            fh.write(json.dumps({"type": "user", "cwd": cwd}) + "\n")
    return path


# ---------------------------------------------------------------------------
# Preference order
# ---------------------------------------------------------------------------


def test_claude_project_dir_wins(tmp_path):
    """An exported project directory takes precedence over everything else."""
    project = _git_repo(tmp_path / "project")
    other = _git_repo(tmp_path / "other")
    transcript = _transcript(tmp_path / "t.jsonl", [str(other)])

    got = resolver.resolve_repo_root(
        transcript_path=str(transcript),
        env={"CLAUDE_PROJECT_DIR": str(project)},
        cwd=str(other),
    )

    assert Path(got).resolve() == project.resolve()


def test_falls_back_to_transcript_when_env_absent(tmp_path):
    """Without the env var, the transcript names the session's project."""
    project = _git_repo(tmp_path / "project")
    other = _git_repo(tmp_path / "other")
    transcript = _transcript(tmp_path / "t.jsonl", [str(project)])

    got = resolver.resolve_repo_root(transcript_path=str(transcript), env={}, cwd=str(other))

    assert Path(got).resolve() == project.resolve()


def test_nonexistent_project_dir_is_ignored(tmp_path):
    """A stale CLAUDE_PROJECT_DIR must not win over a usable transcript."""
    project = _git_repo(tmp_path / "project")
    transcript = _transcript(tmp_path / "t.jsonl", [str(project)])

    got = resolver.resolve_repo_root(
        transcript_path=str(transcript),
        env={"CLAUDE_PROJECT_DIR": str(tmp_path / "gone")},
        cwd=str(tmp_path),
    )

    assert Path(got).resolve() == project.resolve()


def test_falls_back_to_cwd_without_env_or_transcript(tmp_path):
    """With nothing else available the process directory is still used."""
    project = _git_repo(tmp_path / "project")

    got = resolver.resolve_repo_root(transcript_path=None, env={}, cwd=str(project))

    assert Path(got).resolve() == project.resolve()


# ---------------------------------------------------------------------------
# The drift the resolver exists to prevent
# ---------------------------------------------------------------------------


def test_uses_first_recorded_cwd_not_later_drift(tmp_path):
    """Later transcript entries follow the shell and must be ignored.

    This is the exact shape of the incident: the session began in one repo and
    its shell later moved into a sibling, so the last recorded cwd names the
    wrong repository.
    """
    project = _git_repo(tmp_path / "project")
    sibling = _git_repo(tmp_path / "sibling")
    transcript = _transcript(tmp_path / "t.jsonl", [str(project), str(sibling), str(sibling)])

    got = resolver.resolve_repo_root(transcript_path=str(transcript), env={}, cwd=str(sibling))

    assert Path(got).resolve() == project.resolve()
    assert Path(got).resolve() != sibling.resolve()


def test_subdirectory_normalizes_to_work_tree_root(tmp_path):
    """A cwd inside the repo resolves to the repo root, not the subdirectory."""
    project = _git_repo(tmp_path / "project")
    nested = project / "src" / "deep"
    nested.mkdir(parents=True)
    transcript = _transcript(tmp_path / "t.jsonl", [str(nested)])

    got = resolver.resolve_repo_root(transcript_path=str(transcript), env={}, cwd=str(tmp_path))

    assert Path(got).resolve() == project.resolve()


# ---------------------------------------------------------------------------
# Transcript parsing
# ---------------------------------------------------------------------------


def test_first_transcript_cwd_skips_entries_without_one(tmp_path):
    """Header entries carry no cwd and must not stop the scan."""
    t = tmp_path / "t.jsonl"
    t.write_text(
        json.dumps({"type": "header"})
        + "\n"
        + json.dumps({"type": "user"})
        + "\n"
        + json.dumps({"type": "user", "cwd": "/somewhere"})
        + "\n",
        encoding="utf-8",
    )

    assert resolver.first_transcript_cwd(t) == "/somewhere"


def test_malformed_lines_are_tolerated(tmp_path):
    """A truncated or corrupt line must not abort resolution."""
    t = tmp_path / "t.jsonl"
    t.write_text(
        "{not json\n" + json.dumps({"type": "user", "cwd": "/somewhere"}) + "\n",
        encoding="utf-8",
    )

    assert resolver.first_transcript_cwd(t) == "/somewhere"


@pytest.mark.parametrize("missing", ["nope.jsonl", ""])
def test_unreadable_transcript_returns_none(tmp_path, missing):
    """A missing transcript is a normal condition, not an error."""
    assert resolver.first_transcript_cwd(tmp_path / missing) is None


def test_non_git_directory_resolves_to_itself(tmp_path):
    """Outside a work tree the directory itself is the answer."""
    plain = tmp_path / "plain"
    plain.mkdir()

    got = resolver.resolve_repo_root(transcript_path=None, env={}, cwd=str(plain))

    assert Path(got).resolve() == plain.resolve()
