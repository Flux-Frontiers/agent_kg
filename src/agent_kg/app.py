# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0
# pylint: disable=import-outside-toplevel

"""app.py — AgentKG Streamlit Explorer

Interactive visualizer for the AgentKG conversation and UserProfile trees.

Tabs:
  Agent Graph   — pyvis interactive graph of the conversation tree
  Profile Graph — pyvis interactive graph of the UserProfile tree
  Query         — hybrid semantic search + context assembly
  Stats         — node/edge counts, session list, profile breakdown

Run with:
    agent-kg viz --serve
    # or directly:
    streamlit run src/agent_kg/app.py -- --repo . --person egs
"""

from __future__ import annotations

import argparse
import getpass
import sqlite3
import sys
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="AgentKG Explorer",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stTabs [data-baseweb="tab-list"] { gap: 12px; }
    .stTabs [data-baseweb="tab"] { font-size: 1rem; padding: 6px 18px; }
    .hit-card {
        background: #1e1e2e;
        border-left: 4px solid #4A90D9;
        border-radius: 6px;
        padding: 10px 14px;
        margin-bottom: 8px;
        font-family: monospace;
        font-size: 0.85rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Kind colours (matches viz.py)
# ---------------------------------------------------------------------------

_KIND_COLOR: dict[str, str] = {
    "turn": "#4A90D9",
    "topic": "#27AE60",
    "entity": "#E67E22",
    "intent": "#8E44AD",
    "task": "#E74C3C",
    "summary": "#16A085",
    "preference": "#F39C12",
    "commitment": "#C0392B",
    "expertise": "#2980B9",
    "interest": "#27AE60",
    "style": "#8E44AD",
    "context": "#7F8C8D",
}

# ---------------------------------------------------------------------------
# Argument parsing — Streamlit passes args after "--"
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--repo", default=".")
    p.add_argument("--person", default=getpass.getuser())
    args, _ = p.parse_known_args(sys.argv[1:])
    return args


_args = _parse_args()

# ---------------------------------------------------------------------------
# Session-state initialisation
# ---------------------------------------------------------------------------


def _init_state() -> None:
    defaults = {
        "query_results": None,
        "query_context": None,
        "last_query": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    if Path("docs/logo.png").exists():
        st.image("docs/logo.png", use_container_width=True)
    st.title("AgentKG Explorer")
    st.caption("Conversational memory as a knowledge graph")
    st.divider()

    repo = st.text_input("Repo root", value=_args.repo)
    person = st.text_input("Person ID", value=_args.person)

    agent_db = Path(repo) / ".agentkg" / "graph.sqlite"
    profile_db = Path.home() / ".kgrag" / "profiles" / person / "userprofile.sqlite"

    st.divider()
    st.caption(f"**Agent DB:** `{agent_db}`")
    st.caption(f"  exists: {'✓' if agent_db.exists() else '✗'}")
    st.caption(f"**Profile DB:** `{profile_db}`")
    st.caption(f"  exists: {'✓' if profile_db.exists() else '✗'}")

    st.divider()
    st.subheader("Query settings")
    k = st.slider("Top-K results", 1, 30, 8)
    budget = st.slider("Context budget (tokens)", 500, 8000, 4000, step=500)
    include_profile = st.checkbox(
        "Include profile nodes",
        value=False,
        help="Also search UserProfile for preferences, commitments, style",
    )
    kind_filter = st.selectbox(
        "Kind filter",
        ["(all)", "turn", "topic", "entity", "intent", "task", "summary"],
        index=0,
    )

    st.divider()
    physics = st.toggle("Physics simulation", value=True)
    max_nodes = st.slider("Max nodes (agent graph)", 50, 500, 200, step=50)


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner="Loading agent graph…")
def _load_agent(db_path: str, _max_nodes: int):
    p = Path(db_path)
    if not p.exists():
        return [], [], []
    db = sqlite3.connect(str(p))
    db.row_factory = sqlite3.Row
    nodes = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM nodes ORDER BY created_at DESC LIMIT ?", (_max_nodes,)
        ).fetchall()
    ]
    node_ids = {n["id"] for n in nodes}
    edges = [
        dict(r)
        for r in db.execute("SELECT * FROM edges").fetchall()
        if r["source_id"] in node_ids and r["target_id"] in node_ids
    ]
    sessions = [
        dict(r) for r in db.execute("SELECT * FROM sessions ORDER BY start_time DESC").fetchall()
    ]
    db.close()
    return nodes, edges, sessions


@st.cache_data(show_spinner="Loading user profile…")
def _load_profile(db_path: str):
    p = Path(db_path)
    if not p.exists():
        return []
    db = sqlite3.connect(str(p))
    db.row_factory = sqlite3.Row
    rows = [
        dict(r)
        for r in db.execute("SELECT * FROM profile_nodes ORDER BY kind, confidence DESC").fetchall()
    ]
    db.close()
    return rows


# ---------------------------------------------------------------------------
# pyvis HTML builders
# ---------------------------------------------------------------------------


def _agent_html(nodes, edges, physics_on: bool) -> str:
    from agent_kg.viz import (  # noqa: PLC0415
        _KIND_COLOR as VIZ_COLOR,
    )
    from agent_kg.viz import (
        _KIND_SHAPE,
        _REL_COLOR,
        _node_tooltip,
        _require_pyvis,
    )

    _require_pyvis()
    import tempfile  # noqa: PLC0415

    from pyvis.network import Network  # noqa: PLC0415

    net = Network(height="650px", width="100%", bgcolor="#0d1117", font_color="#e0e0e0")
    net.set_options(
        '{"physics":{"enabled":' + str(physics_on).lower() + ',"stabilization":{"iterations":150}},'
        '"interaction":{"hover":true,"tooltipDelay":100}}'
    )
    for n in nodes:
        kind = n["kind"]
        label = (n.get("label") or n.get("text") or kind)[:30]
        net.add_node(
            n["id"],
            label=label,
            color=VIZ_COLOR.get(kind, "#888"),
            shape=_KIND_SHAPE.get(kind, "dot"),
            size=20 if kind == "turn" else 10,
            title=_node_tooltip(kind, label, n.get("text") or "", n.get("role") or ""),
        )
    for e in edges:
        net.add_edge(
            e["source_id"],
            e["target_id"],
            title=e["relation"],
            color=_REL_COLOR.get(e["relation"], "#555"),
            arrows="to",
        )
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        tmp = Path(f.name)
    net.save_graph(str(tmp))
    html = tmp.read_text(encoding="utf-8")
    tmp.unlink(missing_ok=True)
    return html


def _profile_html(rows: list[dict]) -> str:
    from itertools import groupby  # noqa: PLC0415

    from agent_kg.viz import (  # noqa: PLC0415
        _KIND_COLOR as VIZ_COLOR,
    )
    from agent_kg.viz import (
        _KIND_SHAPE,
        _node_tooltip,
        _require_pyvis,
    )

    _require_pyvis()
    import tempfile  # noqa: PLC0415

    from pyvis.network import Network  # noqa: PLC0415

    net = Network(height="600px", width="100%", bgcolor="#0d1117", font_color="#e0e0e0")
    net.set_options(
        '{"physics":{"enabled":true,"stabilization":{"iterations":100}},'
        '"interaction":{"hover":true,"tooltipDelay":100}}'
    )
    net.add_node(
        "__profile__",
        label="UserProfile",
        color="#ffffff",
        shape="box",
        size=30,
        title="<b>UserProfile root</b>",
    )
    for kind, group in groupby(rows, key=lambda r: r["kind"]):
        color = VIZ_COLOR.get(kind, "#888")
        hub = f"__kind__{kind}"
        net.add_node(hub, label=kind, color=color, shape="box", size=18)
        net.add_edge("__profile__", hub, color="#444", arrows="to")
        for node in group:
            conf = int((node["confidence"] or 1.0) * 100)
            label = (node["label"] or "")[:35]
            net.add_node(
                node["id"],
                label=label,
                color=color,
                shape=_KIND_SHAPE.get(kind, "dot"),
                size=10,
                title=_node_tooltip(kind, label, node.get("text") or "", f"confidence: {conf}%"),
            )
            net.add_edge(hub, node["id"], color=color + "88", arrows="to")
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        tmp = Path(f.name)
    net.save_graph(str(tmp))
    html = tmp.read_text(encoding="utf-8")
    tmp.unlink(missing_ok=True)
    return html


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def _kind_badge(kind: str) -> str:
    color = _KIND_COLOR.get(kind, "#888")
    return (
        f'<span style="background:{color};color:#fff;border-radius:4px;'
        f'padding:2px 8px;font-size:11px;font-weight:bold;font-family:monospace;">'
        f"{kind}</span>"
    )


def _render_hit(hit: dict, idx: int) -> None:
    kind = hit.get("kind", "")
    score = hit.get("score", 0.0)
    text = hit.get("text") or hit.get("label") or ""
    label = hit.get("label") or ""
    role = hit.get("role") or hit.get("source") or ""
    source_tag = f" · <i>{role}</i>" if role else ""
    preview = text[:300].replace("<", "&lt;").replace(">", "&gt;")
    if len(text) > 300:
        preview += "…"
    color = _KIND_COLOR.get(kind, "#888")

    st.markdown(
        f"""
        <div style="background:#1e1e2e;border-left:4px solid {color};
                    border-radius:6px;padding:10px 14px;margin-bottom:8px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
            <span>{_kind_badge(kind)}{source_tag}</span>
            <span style="font-family:monospace;font-size:12px;color:#888;">
              score: <b style="color:#e0e0e0;">{score:.3f}</b>
              &nbsp;#{idx + 1}
            </span>
          </div>
          {
            '<div style="font-size:12px;color:#aaa;font-family:monospace;margin-bottom:2px;">'
            + label[:80]
            + "</div>"
            if label and label != text[: len(label)]
            else ""
        }
          <div style="font-size:13px;color:#c9d1d9;
            white-space:pre-wrap;word-break:break-word;">{preview}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _run_query(
    db_path: str,
    profile_path: str,
    q: str,
    k: int,
    budget: int,
    include_profile: bool,
    kind_filter: str | None,
) -> tuple[list[dict], str]:
    """Execute query and context assembly; return (hits, context_md)."""
    from agent_kg.assemble import assemble_context  # noqa: PLC0415
    from agent_kg.query import query as kg_query  # noqa: PLC0415
    from agent_kg.store import AgentKGStore  # noqa: PLC0415

    agentkg_dir = Path(db_path).parent
    store = AgentKGStore(agentkg_dir / "graph.sqlite", agentkg_dir / "lancedb")
    hits = kg_query(store, q, k=k, kind_filter=kind_filter)

    if include_profile:
        from agent_kg.user_profile import UserProfileStore  # noqa: PLC0415

        profile = UserProfileStore(Path(profile_path).parent)
        profile_hits = profile.search(q, k=k)
        hits = hits + profile_hits

    hits.sort(key=lambda h: h.get("score", 0.0), reverse=True)

    context_md = assemble_context(store, q, budget=budget)
    return hits, context_md


# ---------------------------------------------------------------------------
# Main UI — load data
# ---------------------------------------------------------------------------

nodes, edges, sessions = _load_agent(str(agent_db), max_nodes)
profile_rows = _load_profile(str(profile_db))

tab_agent, tab_profile, tab_query, tab_stats = st.tabs(
    ["Agent Graph", "Profile Graph", "Query", "Stats"]
)

# ── Agent Graph ──────────────────────────────────────────────────────────────
with tab_agent:
    st.subheader(f"Conversation Graph — {repo}")
    if not nodes:
        st.info(f"No agent graph at `{agent_db}`. Run `agent-kg ingest` to populate it.")
    else:
        try:
            html = _agent_html(nodes, edges, physics)
            st.components.v1.html(html, height=670, scrolling=False)
            st.caption(f"{len(nodes)} nodes · {len(edges)} edges (capped at {max_nodes})")
        except ImportError as exc:
            st.error(str(exc))

# ── Profile Graph ─────────────────────────────────────────────────────────────
with tab_profile:
    st.subheader(f"UserProfile — {person}")
    if not profile_rows:
        st.info(
            f"No profile at `{profile_db}`. Run `agent-kg onboard --person {person}` to build one."
        )
    else:
        try:
            html = _profile_html(profile_rows)
            st.components.v1.html(html, height=620, scrolling=False)
            st.caption(f"{len(profile_rows)} profile nodes")
        except ImportError as exc:
            st.error(str(exc))

# ── Query ─────────────────────────────────────────────────────────────────────
with tab_query:
    st.subheader("Hybrid Semantic Query")

    if not agent_db.exists():
        st.warning(f"No agent graph at `{agent_db}`. Run `agent-kg ingest` first.")
    else:
        q_col, btn_col = st.columns([5, 1])
        with q_col:
            query_text = st.text_input(
                "Query",
                placeholder="e.g. authentication strategy",
                label_visibility="collapsed",
                key="query_input",
            )
        with btn_col:
            run_btn = st.button("▶ Run", type="primary", use_container_width=True)

        if run_btn and query_text.strip():
            with st.spinner("Searching…"):
                try:
                    kf = kind_filter if kind_filter != "(all)" else None
                    hits, context_md = _run_query(
                        str(agent_db),
                        str(profile_db),
                        query_text.strip(),
                        k=k,
                        budget=budget,
                        include_profile=include_profile,
                        kind_filter=kf,
                    )
                    st.session_state.query_results = hits
                    st.session_state.query_context = context_md
                    st.session_state.last_query = query_text.strip()
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    st.error(f"Query failed: {exc}")

        results = st.session_state.query_results
        context_md = st.session_state.query_context

        if results is None:
            st.info("Enter a query above and click **▶ Run**.")
        elif not results:
            st.warning("No results found.")
        else:
            last_q = st.session_state.last_query
            res_tab, ctx_tab = st.tabs([f"Results ({len(results)})", "Assembled Context"])

            with res_tab:
                st.caption(
                    f"Query: **{last_q}** · k={k}"
                    + (" · +profile" if include_profile else "")
                    + (f" · kind={kind_filter}" if kind_filter != "(all)" else "")
                )
                for i, hit in enumerate(results):
                    _render_hit(hit, i)

            with ctx_tab:
                st.caption(f"Token budget: ~{budget} · query: **{last_q}**")
                st.download_button(
                    "⬇ Download context",
                    data=context_md,
                    file_name="agentkg_context.md",
                    mime="text/markdown",
                )
                st.markdown(context_md)

# ── Stats ─────────────────────────────────────────────────────────────────────
with tab_stats:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Agent Graph")
        if nodes:
            from collections import Counter  # noqa: PLC0415

            kind_counts = Counter(n["kind"] for n in nodes)
            st.dataframe(
                [{"kind": k, "count": v} for k, v in sorted(kind_counts.items())],
                use_container_width=True,
                hide_index=True,
            )
            st.caption(f"**Sessions:** {len(sessions)}")
            if sessions:
                st.dataframe(
                    [
                        {
                            "id": s["id"][:8],
                            "start": (s["start_time"] or "")[:16],
                            "turns": s["turn_count"],
                            "prune passes": s["pruning_passes"],
                        }
                        for s in sessions
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
        else:
            st.info("No agent graph loaded.")

    with col2:
        st.subheader("UserProfile")
        if profile_rows:
            from collections import Counter  # noqa: PLC0415

            kind_counts = Counter(r["kind"] for r in profile_rows)
            st.dataframe(
                [{"kind": k, "count": v} for k, v in sorted(kind_counts.items())],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No profile loaded.")
