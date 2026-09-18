# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""Unit tests for the ``assemble`` CLI command."""

from __future__ import annotations

from click.testing import CliRunner

from agent_kg.cli.main import cli


def test_assemble_empty_graph_prints_nothing_to_stdout(tmp_path, monkeypatch):
    """An empty graph must not inject a placeholder into stdout.

    The UserPromptSubmit hook reads stdout and treats empty as "inject
    nothing" -- a placeholder string here would get injected on every prompt.
    The "no context" message belongs on stderr instead.
    """
    monkeypatch.setattr("agent_kg.graph._PROFILE_BASE", tmp_path / "profiles")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["assemble", "anything at all here", "--repo", str(tmp_path / "repo")],
    )

    assert result.exit_code == 0
    assert result.stdout == ""
