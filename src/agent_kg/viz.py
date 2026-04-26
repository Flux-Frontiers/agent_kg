# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0
# pylint: disable=import-outside-toplevel

"""viz.py — Terminal and HTML visualizations for AgentKG conversation and profile trees.

Two renderers are available:

  Rich tree (always available)
    - ``render_agent_tree_rich(store)`` → prints a session → turn → annotation tree
    - ``render_profile_tree_rich(profile_store)`` → prints the profile tree by kind

  pyvis HTML (requires ``pip install pyvis``)
    - ``build_agent_html(store, edges)`` → returns a self-contained HTML string
    - ``build_profile_html(profile_store)`` → returns a self-contained HTML string
    - ``write_html(html, path)`` → write to file and optionally open in browser
"""

from __future__ import annotations

import sqlite3
import tempfile
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.tree import Tree

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Colour / shape palette — shared by Rich and pyvis renderers
# ---------------------------------------------------------------------------

_KIND_COLOR: dict[str, str] = {
    # Conversation tree
    "turn": "#4A90D9",  # blue
    "topic": "#27AE60",  # green
    "entity": "#E67E22",  # orange
    "intent": "#8E44AD",  # purple
    "task": "#E74C3C",  # red
    "summary": "#F39C12",  # amber
    # UserProfile tree
    "preference": "#1ABC9C",  # teal
    "commitment": "#C0392B",  # crimson
    "expertise": "#2980B9",  # cobalt
    "interest": "#16A085",  # dark-teal
    "style": "#8E44AD",  # purple
    "context": "#7F8C8D",  # grey
}

_KIND_RICH: dict[str, str] = {
    "turn": "bold blue",
    "topic": "green",
    "entity": "yellow",
    "intent": "magenta",
    "task": "bold red",
    "summary": "bold yellow",
    "preference": "bold cyan",
    "commitment": "bold red",
    "expertise": "cyan",
    "interest": "bright_cyan",
    "style": "magenta",
    "context": "bright_black",
}

_KIND_SHAPE: dict[str, str] = {
    "turn": "box",
    "topic": "ellipse",
    "entity": "diamond",
    "intent": "triangle",
    "task": "star",
    "summary": "hexagon",
    "preference": "ellipse",
    "commitment": "star",
    "expertise": "diamond",
    "interest": "dot",
    "style": "triangle",
    "context": "box",
}

_REL_COLOR: dict[str, str] = {
    "FOLLOWS": "#BDC3C7",
    "ADDRESSES": "#3498DB",
    "EXPRESSES": "#9B59B6",
    "MENTIONS": "#E67E22",
    "CREATES": "#27AE60",
    "RESOLVES": "#2ECC71",
    "COMPRESSED_INTO": "#F39C12",
    "RELATED_TO": "#95A5A6",
}


# ---------------------------------------------------------------------------
# Rich terminal renderers
# ---------------------------------------------------------------------------


def render_agent_tree_rich(db_path: Path, *, max_sessions: int = 10, max_turns: int = 20) -> None:
    """Print the agent conversation tree to the terminal using Rich.

    Displays: repo → sessions → turns (with role) → annotations (topics/entities/tasks).

    :param db_path: Path to the agent .agentkg/graph.sqlite database.
    :param max_sessions: Maximum number of sessions to show.
    :param max_turns: Maximum number of turns to show per session.
    """
    console = Console()

    if not db_path.exists():
        return  # silently skip — no local graph yet

    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row

    sessions = db.execute(
        "SELECT * FROM sessions ORDER BY start_time DESC LIMIT ?", (max_sessions,)
    ).fetchall()

    repo_label = str(db_path.parent.parent)
    root = Tree(f"[bold white]Agent Graph[/bold white]  [dim]{repo_label}[/dim]")

    if not sessions:
        root.add("[dim]No sessions yet.[/dim]")
        console.print(root)
        db.close()
        return

    for sess in sessions:
        sid = sess["id"][:8]
        tc = sess["turn_count"] or 0
        pp = sess["pruning_passes"] or 0
        start = (sess["start_time"] or "")[:16]
        sess_label = (
            f"[bold cyan]session {sid}[/bold cyan]"
            f"  [dim]{start}  {tc} turns  {pp} prune passes[/dim]"
        )
        sess_branch = root.add(sess_label)

        turns = db.execute(
            """SELECT * FROM nodes WHERE kind='turn' AND session_id=?
               ORDER BY turn_index LIMIT ?""",
            (sess["id"], max_turns),
        ).fetchall()

        for turn in turns:
            role = turn["role"] or "?"
            role_color = "blue" if role == "user" else "green"
            text = (turn["text"] or "")[:70].replace("\n", " ")
            ellipsis = "…" if len(turn["text"] or "") > 70 else ""
            turn_label = f"[{role_color}]{role}[/{role_color}]  [dim]{text}{ellipsis}[/dim]"
            turn_branch = sess_branch.add(turn_label)

            # Topics
            topics = db.execute(
                """SELECT n.label FROM nodes n
                   JOIN edges e ON e.target_id = n.id
                   WHERE e.source_id=? AND n.kind='topic'""",
                (turn["id"],),
            ).fetchall()
            if topics:
                t_branch = turn_branch.add("[green]topics[/green]")
                for t in topics[:5]:
                    t_branch.add(f"[dim]{t['label']}[/dim]")

            # Entities
            entities = db.execute(
                """SELECT n.label FROM nodes n
                   JOIN edges e ON e.target_id = n.id
                   WHERE e.source_id=? AND n.kind='entity'""",
                (turn["id"],),
            ).fetchall()
            if entities:
                e_branch = turn_branch.add("[yellow]entities[/yellow]")
                for e in entities[:5]:
                    e_branch.add(f"[dim]{e['label']}[/dim]")

            # Tasks
            tasks = db.execute(
                """SELECT n.label FROM nodes n
                   JOIN edges e ON e.target_id = n.id
                   WHERE e.source_id=? AND n.kind='task'""",
                (turn["id"],),
            ).fetchall()
            if tasks:
                tk_branch = turn_branch.add("[bold red]tasks[/bold red]")
                for tk in tasks[:5]:
                    tk_branch.add(f"[dim]{tk['label']}[/dim]")

        # Summaries in this session
        summaries = db.execute(
            "SELECT label FROM nodes WHERE kind='summary' AND session_id=?",
            (sess["id"],),
        ).fetchall()
        if summaries:
            s_branch = sess_branch.add("[bold yellow]summaries[/bold yellow]")
            for s in summaries:
                s_branch.add(f"[dim]{(s['label'] or '')[:80]}[/dim]")

    # Totals
    counts = db.execute("SELECT kind, COUNT(*) as c FROM nodes GROUP BY kind").fetchall()
    db.close()

    totals = root.add("[dim]─── totals ───[/dim]")
    for row in sorted(counts, key=lambda r: r["c"], reverse=True):
        color = _KIND_RICH.get(row["kind"], "white")
        totals.add(f"[{color}]{row['kind']}[/{color}]  {row['c']}")

    console.print(root)


def render_profile_tree_rich(profile_db_path: Path) -> None:
    """Print the UserProfile tree to the terminal using Rich.

    Displays: profile → kind sections → individual nodes with confidence.

    :param profile_db_path: Path to the userprofile.sqlite database.
    """
    console = Console()

    if not profile_db_path.exists():
        console.print(f"[red]No profile found at {profile_db_path}[/red]")
        return

    db = sqlite3.connect(str(profile_db_path))
    db.row_factory = sqlite3.Row

    rows = db.execute("SELECT * FROM profile_nodes ORDER BY kind, confidence DESC").fetchall()
    db.close()

    root = Tree(f"[bold white]UserProfile[/bold white]  [dim]{profile_db_path}[/dim]")

    if not rows:
        root.add("[dim]Empty — run agent-kg onboard --person <you>[/dim]")
        console.print(root)
        return

    from itertools import groupby  # noqa: PLC0415

    for kind, group in groupby(rows, key=lambda r: r["kind"]):
        color = _KIND_RICH.get(kind, "white")
        kind_branch = root.add(f"[{color}]{kind}[/{color}]")
        for node in group:
            conf = int((node["confidence"] or 1.0) * 100)
            label = node["label"] or ""
            kind_branch.add(f"[dim]{label}[/dim]  [bright_black]{conf}%[/bright_black]")

    console.print(root)


# ---------------------------------------------------------------------------
# pyvis HTML builders
# ---------------------------------------------------------------------------


def _require_pyvis() -> None:
    import importlib.util  # noqa: PLC0415

    if importlib.util.find_spec("pyvis") is None:
        raise ImportError(
            'pyvis is not installed. Install the viz extra:\n  pip install "agent-kg[viz]"'
        )


def _node_tooltip(kind: str, label: str, text: str, extra: str = "") -> str:
    """Build a plain-text tooltip (pyvis renders title as text, not HTML)."""
    lines = [f"[{kind}] {label}"]
    if text:
        snippet = (text or "")[:200].replace("\n", " ")
        lines.append(snippet)
    if extra:
        lines.append(extra)
    return "\n".join(lines)


def build_agent_html(db_path: Path, *, height: str = "700px", physics: bool = True) -> str:
    """Build a pyvis interactive graph HTML for the agent conversation tree.

    :param db_path: Path to .agentkg/graph.sqlite.
    :param height: Height of the graph canvas (CSS string).
    :param physics: Whether to enable physics simulation.
    :return: Self-contained HTML string.
    """
    _require_pyvis()
    from pyvis.network import Network  # noqa: PLC0415

    net = Network(height=height, width="100%", bgcolor="#0d1117", font_color="#e0e0e0")
    net.set_options(
        """{
        "physics": {"enabled": """
        + str(physics).lower()
        + """, "stabilization": {"iterations": 150}},
        "edges": {"smooth": {"type": "dynamic"}},
        "interaction": {"hover": true, "tooltipDelay": 100}
    }"""
    )

    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row

    nodes = db.execute("SELECT * FROM nodes").fetchall()
    edges = db.execute("SELECT * FROM edges").fetchall()
    db.close()

    for n in nodes:
        kind = n["kind"]
        label = (n["label"] or n["text"] or kind)[:30]
        color = _KIND_COLOR.get(kind, "#888")
        shape = _KIND_SHAPE.get(kind, "dot")
        role_extra = f"role: {n['role']}" if n["role"] else ""
        size = 20 if kind == "turn" else 12
        net.add_node(
            n["id"],
            label=label,
            color=color,
            shape=shape,
            size=size,
            title=_node_tooltip(kind, label, n["text"] or "", role_extra),
        )

    for e in edges:
        color = _REL_COLOR.get(e["relation"], "#555")
        net.add_edge(
            e["source_id"],
            e["target_id"],
            title=e["relation"],
            color=color,
            arrows="to",
        )

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        tmp = Path(f.name)
    net.save_graph(str(tmp))
    html = tmp.read_text(encoding="utf-8")
    tmp.unlink(missing_ok=True)
    return html


def build_profile_html(profile_db_path: Path, *, height: str = "600px") -> str:
    """Build a pyvis interactive graph HTML for the UserProfile tree.

    :param profile_db_path: Path to userprofile.sqlite.
    :param height: Height of the graph canvas (CSS string).
    :return: Self-contained HTML string.
    """
    _require_pyvis()
    from pyvis.network import Network  # noqa: PLC0415

    net = Network(height=height, width="100%", bgcolor="#0d1117", font_color="#e0e0e0")
    net.set_options(
        """{
        "physics": {"enabled": true, "stabilization": {"iterations": 100}},
        "interaction": {"hover": true, "tooltipDelay": 100}
    }"""
    )

    db = sqlite3.connect(str(profile_db_path))
    db.row_factory = sqlite3.Row
    rows = db.execute("SELECT * FROM profile_nodes ORDER BY kind").fetchall()
    db.close()

    # Group by kind — add a kind hub node, then leaf nodes
    from itertools import groupby  # noqa: PLC0415

    net.add_node(
        "__profile__",
        label="UserProfile",
        color="#ffffff",
        shape="box",
        size=30,
        font={"size": 16, "bold": True},
        title="<b>UserProfile root</b>",
    )

    for kind, group in groupby(rows, key=lambda r: r["kind"]):
        color = _KIND_COLOR.get(kind, "#888")
        shape = _KIND_SHAPE.get(kind, "dot")
        hub_id = f"__kind__{kind}"
        net.add_node(hub_id, label=kind, color=color, shape="box", size=18)
        net.add_edge("__profile__", hub_id, color="#444", arrows="to")

        for node in group:
            conf = int((node["confidence"] or 1.0) * 100)
            label = (node["label"] or "")[:35]
            net.add_node(
                node["id"],
                label=label,
                color=color,
                shape=shape,
                size=10,
                title=_node_tooltip(kind, label, node["text"] or "", f"confidence: {conf}%"),
            )
            net.add_edge(hub_id, node["id"], color=color + "88", arrows="to")

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        tmp = Path(f.name)
    net.save_graph(str(tmp))
    html = tmp.read_text(encoding="utf-8")
    tmp.unlink(missing_ok=True)
    return html


def write_html(html: str, out_path: Path, *, open_browser: bool = True) -> None:
    """Write HTML to a file and optionally open it in the default browser.

    :param html: HTML string to write.
    :param out_path: Destination file path.
    :param open_browser: If True, open the file in the default browser.
    """
    out_path.write_text(html, encoding="utf-8")
    if open_browser:
        webbrowser.open(out_path.as_uri())
