# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""Unit tests for where profiles live: profile_root, profile_dir and AgentKG(profile_root=)."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_kg.schema import NodeKind
from agent_kg.user_profile import PROFILE_ROOT_ENV, profile_dir, profile_root


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A throwaway HOME with no profile-root override set."""
    fake = tmp_path / "home"
    fake.mkdir()
    monkeypatch.setenv("HOME", str(fake))
    monkeypatch.delenv(PROFILE_ROOT_ENV, raising=False)
    return fake


class TestProfileRoot:
    """profile_root(): explicit root, then the environment, then ~/.kgrag/profiles."""

    def test_default_is_under_home(self, home):
        assert profile_root() == home / ".kgrag" / "profiles"

    def test_environment_moves_the_root(self, home, tmp_path, monkeypatch):
        monkeypatch.setenv(PROFILE_ROOT_ENV, str(tmp_path / "elsewhere"))
        assert profile_root() == tmp_path / "elsewhere"

    def test_blank_environment_is_ignored(self, home, monkeypatch):
        monkeypatch.setenv(PROFILE_ROOT_ENV, "   ")
        assert profile_root() == home / ".kgrag" / "profiles"

    def test_explicit_root_beats_the_environment(self, home, tmp_path, monkeypatch):
        monkeypatch.setenv(PROFILE_ROOT_ENV, str(tmp_path / "env"))
        assert profile_root(tmp_path / "explicit") == tmp_path / "explicit"

    def test_tilde_is_expanded(self, home):
        assert profile_root("~/moots") == home / "moots"

    def test_profile_dir_appends_the_person(self, home, tmp_path):
        assert profile_dir("pepys", tmp_path) == tmp_path / "pepys"
        assert profile_dir("egs") == home / ".kgrag" / "profiles" / "egs"


class TestAgentKGProfileRoot:
    """AgentKG(profile_root=) keeps the profile out of ~/.kgrag entirely."""

    def test_profile_lands_under_the_given_root(self, home, tmp_path):
        from agent_kg.graph import AgentKG

        root = tmp_path / "moots" / "profiles"
        kg = AgentKG(repo_path=tmp_path / "repo", person_id="pepys", profile_root=root)
        try:
            kg.profile.upsert(NodeKind.INTEREST, "the theater")
        finally:
            kg.close()
        assert (root / "pepys" / "userprofile.sqlite").exists()
        assert not (home / ".kgrag").exists()

    def test_environment_applies_without_the_argument(self, home, tmp_path, monkeypatch):
        from agent_kg.graph import AgentKG

        root = tmp_path / "env-root"
        monkeypatch.setenv(PROFILE_ROOT_ENV, str(root))
        kg = AgentKG(repo_path=tmp_path / "repo", person_id="evelyn")
        try:
            kg.profile.upsert(NodeKind.INTEREST, "gardens")
        finally:
            kg.close()
        assert (root / "evelyn" / "userprofile.sqlite").exists()
        assert not (home / ".kgrag").exists()


def test_cli_init_honors_the_environment(home, tmp_path, monkeypatch):
    """`agentkg init` creates the profile directory under $AGENTKG_PROFILE_ROOT."""
    from agent_kg.cli import main as cli_main

    root = tmp_path / "cli-root"
    monkeypatch.setenv(PROFILE_ROOT_ENV, str(root))
    # Skip the model download and load; only the profile directory matters here.
    monkeypatch.setattr("kg_utils.embed.resolve_model_path", lambda model: Path(home))

    class _Model:
        def encode(self, *_a, **_kw):
            return [[0.0]]

    monkeypatch.setattr("agent_kg.store._load_sentence_transformer", lambda model: _Model())
    result = CliRunner().invoke(cli_main.cli, ["init", "--person", "boswell"])
    assert result.exit_code == 0, result.output
    assert (root / "boswell").is_dir()
    assert f"Profile directory: {root / 'boswell'}" in result.output
    assert not (home / ".kgrag" / "profiles").exists()
