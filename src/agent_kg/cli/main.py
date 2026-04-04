# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""agent_kg CLI — command-line interface for AgentKG.

Commands:
  init          — Download embedding model and create profile directory (run first)
  install-hooks — Install pre-commit hook (rebuilds CodeKG + DocKG, captures snapshots)
  ingest   — Add a turn to the conversation graph
  query    — Semantic search over the graph
  pack     — Extract context snippets
  assemble — Assemble full context block
  prune    — Run KG Context Pruning
  stats    — Show graph statistics
  analyze  — Full Markdown analysis report
  sessions — List all sessions
  snapshot — Capture a snapshot
  onboard  — Run the UserProfile onboarding interview
  profile  — Show the UserProfile
"""

from __future__ import annotations

from pathlib import Path

import click

from agent_kg.graph import AgentKG

_PERSON_HELP = (
    "Person ID — profile stored at ~/.kgrag/profiles/<person>/."
    " Use the same value across all commands."
)


def _resolve_kg(repo: str, person_id: str, session_id: str | None) -> AgentKG:
    return AgentKG(repo_path=repo, person_id=person_id, session_id=session_id or None)


@click.group()
@click.version_option()
def cli() -> None:
    """AgentKG — conversational memory as a knowledge graph."""


@cli.command()
@click.argument("text")
@click.option(
    "--role",
    "-r",
    default="user",
    show_default=True,
    type=click.Choice(["user", "assistant"]),
    help="Turn role.",
)
@click.option("--repo", "-p", default=".", show_default=True, help="Repo root path.")
@click.option(
    "--person",
    default="default",
    show_default=True,
    help=_PERSON_HELP,
)
@click.option("--session", default=None, help="Session UUID to resume.")
@click.option("--no-embed", is_flag=True, help="Defer embedding to consolidate pass.")
def ingest(
    text: str, role: str, repo: str, person: str, session: str | None, no_embed: bool
) -> None:
    """Add a turn to the conversation graph."""
    kg = _resolve_kg(repo, person, session)
    result = kg.ingest(text=text, role=role, embed=not no_embed)
    click.echo(f"Ingested turn #{kg.session.turn_count - 1} (role={role})")
    click.echo(f"  Topics: {[t.label for t in result.topic_nodes]}")
    click.echo(f"  Entities: {[e.label for e in result.entity_nodes]}")
    click.echo(f"  Tasks created: {len(result.task_nodes)}")
    click.echo(f"  Profile updates: {len(result.profile_updates)}")
    kg.close()


@cli.command()
@click.argument("query_text")
@click.option("--k", "-k", default=8, show_default=True, help="Number of results.")
@click.option("--repo", "-p", default=".", show_default=True, help="Repo root path.")
@click.option(
    "--person",
    default="default",
    show_default=True,
    help=_PERSON_HELP,
)
def query(query_text: str, k: int, repo: str, person: str) -> None:
    """Semantic search over the conversation graph."""
    kg = _resolve_kg(repo, person, None)
    hits = kg.query(query_text, k=k)
    if not hits:
        click.echo("No results found.")
        return
    for i, h in enumerate(hits, 1):
        score = h.get("score", 0.0)
        kind = h.get("kind", "?")
        text = h.get("text", "")[:120]
        click.echo(f"{i:2}. [{kind}] (score={score:.3f}) {text}")
    kg.close()


@cli.command()
@click.argument("query_text")
@click.option("--budget", "-b", default=4000, show_default=True, help="Token budget.")
@click.option("--repo", "-p", default=".", show_default=True, help="Repo root path.")
@click.option(
    "--person",
    default="default",
    show_default=True,
    help=_PERSON_HELP,
)
@click.option("--session", default=None, help="Session UUID.")
def assemble(query_text: str, budget: int, repo: str, person: str, session: str | None) -> None:
    """Assemble a token-budgeted context block from the graph."""
    kg = _resolve_kg(repo, person, session)
    ctx = kg.assemble_context(query_text, budget=budget)
    click.echo(ctx)
    kg.close()


@cli.command()
@click.option(
    "--window", "-w", default=20, show_default=True, help="Keep N most-recent turns verbatim."
)
@click.option("--repo", "-p", default=".", show_default=True, help="Repo root path.")
@click.option(
    "--person",
    default="default",
    show_default=True,
    help=_PERSON_HELP,
)
@click.option("--session", default=None, help="Session UUID.")
def prune_cmd(window: int, repo: str, person: str, session: str | None) -> None:
    """Run KG Context Pruning — compress old turns into Summary nodes."""
    kg = _resolve_kg(repo, person, session)
    if not kg.should_prune():
        click.echo("Not enough cold turns to prune yet.")
        kg.close()
        return
    report = kg.prune(window=window)
    click.echo(f"Pruning pass {report.pruning_pass} complete.")
    click.echo(f"  Summaries created: {report.summaries_created}")
    click.echo(f"  Turns pruned: {report.turns_pruned}")
    click.echo(f"  Nodes removed: {report.nodes_removed}")
    click.echo(f"  Token savings ~{report.token_savings_approx}")
    kg.close()


# Register prune under the name 'prune'
cli.add_command(prune_cmd, name="prune")


@cli.command()
@click.option("--repo", "-p", default=".", show_default=True, help="Repo root path.")
@click.option(
    "--person",
    default="default",
    show_default=True,
    help=_PERSON_HELP,
)
def stats(repo: str, person: str) -> None:
    """Show graph statistics."""
    kg = _resolve_kg(repo, person, None)
    s = kg.stats()
    click.echo(f"AgentKG: {repo}")
    click.echo(f"  Nodes:     {s['node_count']}")
    click.echo(f"  Edges:     {s['edge_count']}")
    click.echo(f"  Session:   {s['session_id'][:8]}...")
    click.echo(f"  Turns:     {s['turn_count']}")
    if s.get("kind_counts"):
        click.echo("  By kind:")
        for kind, count in sorted(s["kind_counts"].items()):
            click.echo(f"    {kind:15} {count}")
    kg.close()


@cli.command()
@click.option("--repo", "-p", default=".", show_default=True, help="Repo root path.")
@click.option(
    "--person",
    default="default",
    show_default=True,
    help=_PERSON_HELP,
)
def analyze(repo: str, person: str) -> None:
    """Print a full Markdown analysis report."""
    kg = _resolve_kg(repo, person, None)
    click.echo(kg.analyze())
    kg.close()


@cli.command()
@click.option("--repo", "-p", default=".", show_default=True, help="Repo root path.")
@click.option(
    "--person",
    default="default",
    show_default=True,
    help=_PERSON_HELP,
)
def sessions(repo: str, person: str) -> None:
    """List all sessions for this repo."""
    kg = _resolve_kg(repo, person, None)
    all_sessions = kg._store.list_sessions()
    if not all_sessions:
        click.echo("No sessions found.")
        kg.close()
        return
    click.echo(f"{'ID':10} {'Start':20} {'Turns':6} {'Prune':6}")
    click.echo("-" * 50)
    for s in all_sessions:
        sid = s["id"][:8] + "..."
        start = s.get("start_time", "")[:19]
        tc = s.get("turn_count", 0)
        pp = s.get("pruning_passes", 0)
        click.echo(f"{sid:10} {start:20} {tc:6} {pp:6}")
    kg.close()


@cli.command()
@click.option("--repo", "-p", default=".", show_default=True, help="Repo root path.")
@click.option(
    "--person",
    default="default",
    show_default=True,
    help=_PERSON_HELP,
)
@click.option("--label", "-l", default=None, help="Human-readable snapshot label.")
def snapshot(repo: str, person: str, label: str | None) -> None:
    """Capture a point-in-time snapshot."""
    kg = _resolve_kg(repo, person, None)
    snap = kg.snapshot(label=label)
    click.echo(f"Snapshot captured: {snap['timestamp']}")
    click.echo(f"  Nodes: {snap['node_count']}, Edges: {snap['edge_count']}")
    click.echo(f"  Turns: {snap.get('turn_count', 0)}, Summaries: {snap.get('summary_count', 0)}")
    kg.close()


@cli.command()
@click.option("--repo", "-p", default=".", show_default=True, help="Repo root path.")
@click.option(
    "--person",
    default="default",
    show_default=True,
    help=_PERSON_HELP,
)
@click.option("--update", is_flag=True, help="Run in update mode (re-run to refine preferences).")
@click.option("--skip-optional", is_flag=True, help="Skip the optional Personal phase.")
def onboard(repo: str, person: str, update: bool, skip_optional: bool) -> None:  # pylint: disable=unused-argument
    """Run the structured UserProfile onboarding interview."""
    kg = _resolve_kg(repo, person, None)
    from agent_kg.onboard import run_onboard_interview  # noqa: PLC0415

    run_onboard_interview(
        profile=kg.profile,
        skip_optional=skip_optional,
    )
    kg.close()


@cli.command()
@click.option("--repo", "-p", default=".", show_default=True, help="Repo root path.")
@click.option(
    "--person",
    default="default",
    show_default=True,
    help=_PERSON_HELP,
)
def profile(repo: str, person: str) -> None:
    """Show the UserProfile for this person."""
    kg = _resolve_kg(repo, person, None)
    click.echo(kg.profile.render_markdown())
    kg.close()


_PRE_COMMIT_HOOK = """\
#!/usr/bin/env bash
# AgentKG pre-commit hook — rebuilds CodeKG + DocKG indices and captures
# metrics snapshots BEFORE quality checks run.
# Installed by: agent-kg install-hooks
# Skip with: AGENTKG_SKIP_SNAPSHOT=1 git commit ...
set -euo pipefail

[ "${AGENTKG_SKIP_SNAPSHOT:-0}" = "1" ] && exit 0

REPO_ROOT="$(git rev-parse --show-toplevel)"

cd "$REPO_ROOT"

# Capture tree hash of staged index NOW — before any tool modifies files.
TREE_HASH=$(git write-tree)
BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Rebuild CodeKG index if codekg is available.
if command -v codekg &>/dev/null || [ -x "$REPO_ROOT/.venv/bin/codekg" ]; then
    CODEKG="${REPO_ROOT}/.venv/bin/codekg"
    [ -x "$CODEKG" ] || CODEKG="codekg"
    "$CODEKG" build --repo "$REPO_ROOT" || exit 1
    "$CODEKG" snapshot save \\
        --repo "$REPO_ROOT" \\
        --tree-hash "$TREE_HASH" \\
        --branch "$BRANCH" \\
      || { echo "[codekg] snapshot skipped (run 'codekg build' to initialize)" >&2; }
    git add .codekg/snapshots/ 2>/dev/null || true
fi

# Rebuild DocKG index if dockg is available and a docs directory exists.
if [ -d "$REPO_ROOT/docs" ] && { command -v dockg &>/dev/null || [ -x "$REPO_ROOT/.venv/bin/dockg" ]; }; then
    DOCKG="${REPO_ROOT}/.venv/bin/dockg"
    [ -x "$DOCKG" ] || DOCKG="dockg"
    "$DOCKG" build --repo "$REPO_ROOT" --wipe || true
    if [ -d "$REPO_ROOT/.dockg" ]; then
        "$DOCKG" snapshot save \\
            --repo "$REPO_ROOT" \\
            --tree-hash "$TREE_HASH" \\
            --branch "$BRANCH" || true
        git add .dockg/snapshots/ 2>/dev/null || true
    fi
fi

# Run pre-commit framework checks (ruff, mypy, detect-secrets, etc.) AFTER
# snapshots are captured and staged.
PRECOMMIT="$REPO_ROOT/.venv/bin/pre-commit"
if [ -x "$PRECOMMIT" ]; then
    "$PRECOMMIT" run || exit 1
elif command -v pre-commit &>/dev/null; then
    pre-commit run || exit 1
fi

exit 0
"""


@cli.command("install-hooks")
@click.option(
    "--repo", default=".", type=click.Path(exists=True), show_default=True, help="Repository root."
)
@click.option("--force", is_flag=True, help="Overwrite an existing pre-commit hook.")
def install_hooks(repo: str, force: bool) -> None:
    """Install the AgentKG pre-commit git hook.

    After installation, before each commit:
      1. Rebuilds local CodeKG index if codekg is installed
      2. Rebuilds local DocKG index if dockg is installed and docs/ exists
      3. Captures metrics snapshots for both KGs keyed by tree hash
      4. Stages both snapshot directories atomically
      5. Runs pre-commit framework checks (ruff, mypy, detect-secrets, etc.)
    """
    import stat  # noqa: PLC0415

    repo_root = Path(repo).resolve()
    git_dir = repo_root / ".git"

    if not git_dir.is_dir():
        click.echo(f"Error: {repo_root} is not a git repository.", err=True)
        raise SystemExit(1)

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    hook_path = hooks_dir / "pre-commit"

    if hook_path.exists() and not force:
        click.echo(f"Hook already exists: {hook_path}")
        click.echo("Use --force to overwrite.")
        raise SystemExit(1)

    hook_path.write_text(_PRE_COMMIT_HOOK)
    mode = hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    hook_path.chmod(mode)

    click.echo(f"OK Installed pre-commit hook: {hook_path}")
    click.echo("  CodeKG + DocKG indices will be rebuilt before each commit.")
    click.echo("  Skip with: AGENTKG_SKIP_SNAPSHOT=1 git commit ...")


@cli.command()
@click.option(
    "--person",
    default="default",
    show_default=True,
    help=_PERSON_HELP,
)
@click.option(
    "--model",
    default="all-MiniLM-L6-v2",
    show_default=True,
    help="Sentence-transformers model to pre-download.",
)
def init(person: str, model: str) -> None:
    """Initialize AgentKG: download the embedding model and create the profile directory."""
    from sentence_transformers import SentenceTransformer  # noqa: PLC0415

    profile_dir = Path.home() / ".kgrag" / "profiles" / person
    profile_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"Profile directory: {profile_dir}")

    click.echo(f"Downloading embedding model '{model}' (cached after first run)...")
    st = SentenceTransformer(model)
    _ = st.encode(["warmup"], normalize_embeddings=True)
    click.echo(f"Model ready: {model}")
    click.echo(f"\nAll set. Run 'agent-kg onboard --person {person}' to build your profile.")


@cli.command()
def mcp() -> None:
    """Start the AgentKG MCP server."""
    from agent_kg.mcp.server import main as mcp_main  # noqa: PLC0415

    mcp_main()


if __name__ == "__main__":
    cli()
