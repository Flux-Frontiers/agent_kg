# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""The AgentKG MCP server on the fleet's shared base, ``kg_utils.mcp``.

Import-level regression tests first: an incompatible ``mcp`` release breaks
the server at *import* time, not at call time, which is how mcp 2.0 shipped
past CI in 0.8.0 and left ``agentkg-mcp`` crashing for every PyPI installer.

Then what step 4 of kgrag_priv's MCP centralization plan promises: the five
canonical tools first, AgentKG's seven as extras, unprefixed; ``stats``,
``get_node`` and ``neighbors`` never load the model; the manifest answers
without a graph; ``agentkg``'s other commands do not import ``mcp``; the
installers' ``AGENTKG_REPO``/``AGENTKG_PERSON`` scoping still works; and a
real stdio subprocess serves.

The embedding model is a deterministic keyword fake, so nothing is downloaded.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import anyio
import numpy as np
import pytest
from click.testing import CliRunner
from kg_utils.mcp import CANONICAL_TOOLS, manifest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.memory import create_connected_server_and_client_session

import agent_kg
from agent_kg.cli.main import cli
from agent_kg.graph import AgentKG
from agent_kg.mcp.server import EXTRA_TOOLS, build_server

_SRC = str(Path(agent_kg.__file__).resolve().parents[1])
_EXTRAS = ["ingest", "assemble", "prune", "topics", "tasks", "profile", "analyze"]
_WORDS = ("database", "migration", "testing", "deploy", "python")


class _KeywordModel:
    """Stands in for a SentenceTransformer: one dimension per keyword, unit length."""

    def encode(self, text: str, normalize_embeddings: bool = True):
        vec = np.zeros(384, dtype=np.float32)
        for i, w in enumerate(_WORDS):
            vec[i] = float(w in text.lower())
        vec[383] = 0.01
        return vec / np.linalg.norm(vec)


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTKG_PROFILE_ROOT", str(tmp_path / "profiles"))
    monkeypatch.delenv("AGENTKG_REPO", raising=False)
    monkeypatch.delenv("AGENTKG_SESSION", raising=False)
    monkeypatch.setenv("AGENTKG_PERSON", "tester")


@pytest.fixture
def fake_model(monkeypatch):
    monkeypatch.setattr("agent_kg.store._load_sentence_transformer", lambda _name: _KeywordModel())


@pytest.fixture
def repo(tmp_path, fake_model) -> Path:
    """A repository whose graph holds three ingested turns."""
    root = tmp_path / "repo"
    root.mkdir()
    kg = AgentKG(root, person_id="tester")
    kg.ingest("We should migrate the database schema before the deploy.", role="user")
    kg.ingest("I will write the migration and add testing for it.", role="assistant")
    kg.ingest("Python packaging is the next thing to look at.", role="user")
    kg.close()
    return root


def _session(server, fn):
    async def main():
        async with create_connected_server_and_client_session(server) as client:
            return await fn(client)

    return anyio.run(main)


def _refuse_model(monkeypatch):
    def refuse(*_a, **_k):
        raise RuntimeError("embedding model load refused by test")

    monkeypatch.setattr("agent_kg.store._load_sentence_transformer", refuse)


# ---------------------------------------------------------------------------
# Import level
# ---------------------------------------------------------------------------


def test_server_module_imports():
    """The module must import cleanly against the installed mcp release."""
    importlib.import_module("agent_kg.mcp.server")


def test_entry_point_target_exists():
    """``agentkg-mcp`` resolves to agent_kg.mcp.server:main."""
    assert callable(importlib.import_module("agent_kg.mcp.server").main)


# ---------------------------------------------------------------------------
# The tool surface
# ---------------------------------------------------------------------------


def test_canonical_tools_then_the_extras(tmp_path):
    names = [t["name"] for t in manifest(build_server(tmp_path))["tools"]]
    assert names == [*CANONICAL_TOOLS, *_EXTRAS]
    assert [t.__name__ for t in EXTRA_TOOLS] == _EXTRAS
    assert not any(n.startswith("agent_kg") for n in names)


def test_graph_tools_answer_without_a_model(repo, monkeypatch):
    _refuse_model(monkeypatch)
    kg = AgentKG(repo, person_id="tester")
    turn = kg.index.get_all_turns()[0].id
    kg.close()

    async def calls(client: ClientSession):
        return (
            await client.call_tool("stats", {}),
            await client.call_tool("get_node", {"node_id": turn}),
            await client.call_tool("neighbors", {"node_id": turn}),
            await client.call_tool("get_node", {"node_id": "nope"}),
            await client.call_tool("topics", {}),
        )

    stats, node, near, missing, topics = _session(build_server(repo), calls)
    assert not stats.isError and stats.structuredContent["kind"] == "agent"
    assert stats.structuredContent["person_id"] == "tester"
    assert not node.isError and node.structuredContent["id"] == turn
    assert isinstance(node.structuredContent["metadata"], dict)
    assert not near.isError and near.structuredContent["edges"]
    assert all(turn in (e["src"], e["dst"]) for e in near.structuredContent["edges"])
    assert missing.isError and "no node with id 'nope'" in missing.content[0].text
    assert not topics.isError and topics.content[0].text.startswith("Topics (")


def test_query_pack_and_ingest_through_mcp(repo, fake_model):
    async def calls(client: ClientSession):
        return (
            await client.call_tool("query", {"q": "database migration", "k": 2}),
            await client.call_tool("query", {"q": "database migration", "k": 1, "hop": 1}),
            await client.call_tool("pack", {"q": "database migration", "k": 2}),
            await client.call_tool("ingest", {"turn_text": "Remember to deploy on Friday."}),
            await client.call_tool("ingest", {"turn_text": "x", "role": "robot"}),
            await client.call_tool("stats", {}),
        )

    found, expanded, packed, ingested, bad_role, stats = _session(build_server(repo), calls)
    hits = found.structuredContent["hits"]
    assert hits and all(h["hop"] == 0 for h in hits)
    assert all(any(w in h["text"].lower() for w in ("database", "migrat")) for h in hits)
    seeds, rest = expanded.structuredContent["hits"][:1], expanded.structuredContent["hits"][1:]
    assert rest and all(h["hop"] == 1 and h["via_seed"] == seeds[0]["node_id"] for h in rest)
    assert "database" in packed.content[0].text.lower()
    assert not ingested.isError and "Ingested turn (role=user)" in ingested.content[0].text
    assert bad_role.isError and "role must be" in bad_role.content[0].text
    assert stats.structuredContent["turn_count"] == 4


# ---------------------------------------------------------------------------
# AgentKG's canonical surface
# ---------------------------------------------------------------------------


def test_hop_zero_keeps_the_old_hits(repo, fake_model):
    kg = AgentKG(repo, person_id="tester")
    hits = kg.query("database migration", k=2)
    assert all(h["hop"] == 0 and h["via_seed"] == h["node_id"] for h in hits)
    assert len(kg.query("database migration", k=2, hop=2, max_nodes=3)) == 3
    with pytest.raises(ValueError, match="hop"):
        kg.query("x", hop=6)
    with pytest.raises(ValueError, match="max_nodes"):
        kg.pack("x", max_nodes=0)
    kg.close()


def test_neighbors_contract(repo):
    kg = AgentKG(repo, person_id="tester")
    turn = kg.index.get_all_turns()[0].id
    both = kg.neighbors(turn)
    edges = [(e["rel"], e["src"], e["dst"]) for e in both["edges"]]
    assert edges == sorted(edges)
    out = kg.neighbors(turn, direction="out")
    assert all(e["src"] == turn for e in out["edges"])
    assert len(kg.neighbors(turn, limit=1)["edges"]) == 1
    assert kg.neighbors("nope") is None
    for bad in ({"direction": "up"}, {"limit": 0}):
        with pytest.raises(ValueError):
            kg.neighbors(turn, **bad)
    kg.close()


def test_explicit_paths_are_honoured(tmp_path):
    kg = AgentKG(tmp_path, db_path=tmp_path / "g.sqlite", vectors_path=tmp_path / "v.sqlite")
    assert (kg.db_path, kg.vectors_path, kg.repo_root) == (
        tmp_path / "g.sqlite",
        tmp_path / "v.sqlite",
        tmp_path.resolve(),
    )
    kg.close()


# ---------------------------------------------------------------------------
# The command
# ---------------------------------------------------------------------------


def test_manifest_answers_and_opens_nothing(tmp_path):
    result = CliRunner().invoke(cli, ["mcp", "--repo", str(tmp_path), "--manifest"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["canonical"] == list(CANONICAL_TOOLS)
    assert not (tmp_path / ".agentkg").exists()


def test_agentkg_repo_scopes_the_server_unless_repo_is_given(repo, tmp_path, monkeypatch, capsys):
    """The installers write ``agentkg mcp`` with AGENTKG_REPO and no --repo."""
    from agent_kg.cli import main as cli_main

    seen: list[Path] = []
    monkeypatch.setattr(
        "agent_kg.mcp.server.build_server", lambda r, *_a: seen.append(Path(r)) or build_server(r)
    )
    monkeypatch.setenv("AGENTKG_REPO", str(repo))
    assert CliRunner().invoke(cli_main.cli, ["mcp", "--manifest"]).exit_code == 0
    assert (
        CliRunner().invoke(cli_main.cli, ["mcp", "--repo", str(tmp_path), "--manifest"]).exit_code
        == 0
    )
    assert seen == [repo, tmp_path]


def test_sse_is_refused(tmp_path):
    result = CliRunner().invoke(cli, ["mcp", "--repo", str(tmp_path), "--transport", "sse"])
    assert result.exit_code == 2


def test_other_commands_do_not_import_mcp():
    out = subprocess.run(
        [sys.executable, "-c", "import sys, agent_kg.cli.main; print('mcp' in sys.modules)"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert out == "False"


def test_stdio_subprocess_serves(repo, tmp_path):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-c", "from agent_kg.mcp.server import main; main()"],
        env={
            **os.environ,
            "PYTHONPATH": _SRC,
            "AGENTKG_REPO": str(repo),
            "AGENTKG_PERSON": "tester",
            "AGENTKG_PROFILE_ROOT": str(tmp_path / "profiles"),
        },
    )

    async def run():
        with open(tmp_path / "stderr.log", "w", encoding="utf-8") as errlog:
            async with stdio_client(params, errlog=errlog) as (read, write):
                async with ClientSession(read, write) as client:
                    init = await client.initialize()
                    tools = await client.list_tools()
                    stats = await client.call_tool("stats", {})
                    return init, tools, stats

    init, tools, stats = anyio.run(run)
    assert (init.serverInfo.name, init.serverInfo.version) == ("agentkg", agent_kg.__version__)
    assert [t.name for t in tools.tools] == [*CANONICAL_TOOLS, *_EXTRAS]
    assert stats.structuredContent["turn_count"] == 3
    err = (tmp_path / "stderr.log").read_text(encoding="utf-8")
    assert "agentkg MCP server starting (stdio)" in err
    assert f"repo    : {repo.resolve()}" in err
