# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""Tests that the prune-running hooks hand oMLX its API key.

The Stop and PreCompact hooks run ``agentkg prune`` with ``SYNTH_BACKEND=omlx``
by default. oMLX rejects requests without a key, and a hook process has no
``VLLM_API_KEY`` of its own, so the hooks read it from
``~/.omlx/settings.json``. These tests run the real hook scripts against a fake
``agentkg`` that records only whether the key it received matches, never the
key itself.
"""

import json
import os
import stat
import subprocess
import time
from pathlib import Path

import pytest

_HOOK_DIR = Path(__file__).resolve().parents[1] / "src/agent_kg/hooks"
_KEY = "test-omlx-key"  # pragma: allowlist secret

_FAKE_AGENTKG = """#!/bin/bash
if [ "$1" = "prune" ]; then
    if [ -z "${VLLM_API_KEY+x}" ]; then
        state=unset
    elif [ "$VLLM_API_KEY" = "$EXPECTED_KEY" ]; then
        state=match
    else
        state=other
    fi
    echo "$state" > "$MARKER"
fi
"""


def _run_hook(tmp_path, hook, *, settings=True, extra_env=None):
    """Run ``hook`` in a sandbox and return (process, marker path, home).

    :param tmp_path: pytest temporary directory.
    :param hook: Hook script file name.
    :param settings: Write a fake oMLX settings file when true.
    :param extra_env: Variables added to the hook's environment.
    """
    home = tmp_path / "home"
    home.mkdir()
    if settings:
        (home / ".omlx").mkdir()
        (home / ".omlx/settings.json").write_text(json.dumps({"auth": {"api_key": _KEY}}))

    project = tmp_path / "project"
    (project / ".agentkg").mkdir(parents=True)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "agentkg"
    fake.write_text(_FAKE_AGENTKG)
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)

    # The Stop hook prunes only every 20 user messages.
    transcript = tmp_path / "t.jsonl"
    with open(transcript, "w", encoding="utf-8") as fh:
        for _ in range(20):
            fh.write(json.dumps({"message": {"role": "user", "content": "hi"}}) + "\n")

    marker = tmp_path / "marker"
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("GIT_", "SYNTH_", "VLLM_")) and k != "CLAUDE_PROJECT_DIR"
    }
    env.update(
        HOME=str(home),
        PATH=f"{bin_dir}{os.pathsep}{env.get('PATH', '')}",
        CLAUDE_PROJECT_DIR=str(project),
        EXPECTED_KEY=_KEY,
        MARKER=str(marker),
    )
    env.update(extra_env or {})

    payload = json.dumps({"session_id": "s1", "transcript_path": str(transcript)})
    proc = subprocess.run(
        ["bash", str(_HOOK_DIR / hook)],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
        timeout=60,
        check=False,
    )
    # The Stop hook runs prune in the background.
    deadline = time.monotonic() + 10
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    return proc, marker, home


_HOOKS = ["agent_kg_stop_hook.sh", "agent_kg_precompact_hook.sh"]


@pytest.mark.parametrize("hook", _HOOKS)
def test_key_read_from_settings_and_not_printed(tmp_path, hook):
    """The key reaches prune and appears in no output or log."""
    proc, marker, home = _run_hook(tmp_path, hook)

    assert proc.returncode == 0
    assert marker.read_text().strip() == "match"
    assert _KEY not in proc.stdout
    assert _KEY not in proc.stderr
    for log in (home / ".agentkg").rglob("*"):
        if log.is_file():
            assert _KEY not in log.read_text(errors="replace")


@pytest.mark.parametrize("hook", _HOOKS)
def test_existing_key_wins(tmp_path, hook):
    """A non-empty VLLM_API_KEY already in the environment is kept."""
    _, marker, _ = _run_hook(tmp_path, hook, extra_env={"VLLM_API_KEY": "preset"})
    assert marker.read_text().strip() == "other"


@pytest.mark.parametrize("hook", _HOOKS)
def test_other_backend_gets_no_key(tmp_path, hook):
    """A non-omlx backend is not given oMLX's key."""
    _, marker, _ = _run_hook(tmp_path, hook, extra_env={"SYNTH_BACKEND": "openai"})
    assert marker.read_text().strip() == "unset"


@pytest.mark.parametrize("hook", _HOOKS)
def test_missing_settings_is_silent(tmp_path, hook):
    """No settings file leaves the key unset and the hook still succeeds."""
    proc, marker, _ = _run_hook(tmp_path, hook, settings=False)
    assert proc.returncode == 0
    assert proc.stdout.strip() == "{}"
    assert proc.stderr == ""
    assert marker.read_text().strip() == "unset"
