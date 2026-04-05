# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""agent_kg CLI — command-line interface for AgentKG.

Commands:
  init          — Download embedding model and create profile directory (run first)
  install-hooks — Install pre-commit hook and/or Claude Code auto-ingest hooks
  ingest   — Add a turn to the conversation graph
  query    — Semantic search over the graph
  pack     — Extract context snippets
  assemble — Assemble full context block
  prune    — Run KG Context Pruning
  stats    — Show graph statistics
  analyze  — Full Markdown analysis report
  sessions — List all sessions
  snapshot — Capture a snapshot
  onboard      — Run the UserProfile onboarding interview
  profile      — Show the UserProfile
  profile-set  — Update identity fields / add profile nodes
  profile-remove — Remove specific nodes or wipe categories
  wipe         — Erase local conversation graph and/or global user profile
  viz      — Visualize agent and/or profile trees (terminal or browser)
"""

from __future__ import annotations

import getpass
from pathlib import Path

import click

from agent_kg.graph import AgentKG

# Default to the OS login name so --person is never required on a single-user machine.
_DEFAULT_PERSON = getpass.getuser()

_PERSON_HELP = (
    "Person ID — global profile at ~/.kgrag/profiles/<person>/."
    f" Defaults to your OS username ({_DEFAULT_PERSON})."
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
    default=_DEFAULT_PERSON,
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
    if result.skipped:
        click.echo("Turn skipped (slash command, empty, or system-only content).")
        kg.close()
        return
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
    default=_DEFAULT_PERSON,
    show_default=True,
    help=_PERSON_HELP,
)
@click.option(
    "--include-profile",
    is_flag=True,
    help="Also search profile nodes (preferences, commitments, expertise, style).",
)
def query(query_text: str, k: int, repo: str, person: str, include_profile: bool) -> None:
    """Semantic search over the conversation graph.

    Use --include-profile to also search the global UserProfile (preferences,
    commitments, expertise, style).  Profile hits are ranked by keyword overlap
    and labelled with [preference], [commitment], etc.
    """
    kg = _resolve_kg(repo, person, None)
    hits = kg.query(query_text, k=k)

    if include_profile:
        profile_hits = kg.profile.search(query_text, k=k)
        # Merge and re-sort by score; deduplicate by node_id
        seen: set[str] = {h["node_id"] for h in hits}
        for ph in profile_hits:
            if ph["node_id"] not in seen:
                hits.append(ph)
                seen.add(ph["node_id"])
        hits.sort(key=lambda h: h.get("score", 0.0), reverse=True)
        hits = hits[:k]

    if not hits:
        click.echo("No results found.")
        kg.close()
        return
    for i, h in enumerate(hits, 1):
        score = h.get("score", 0.0)
        kind = h.get("kind", "?")
        source = h.get("source", "")
        source_tag = f" [{source}]" if source == "profile" else ""
        text = h.get("text", "")[:120]
        click.echo(f"{i:2}. [{kind}]{source_tag} (score={score:.3f}) {text}")
    kg.close()


@cli.command()
@click.argument("query_text")
@click.option("--budget", "-b", default=4000, show_default=True, help="Token budget.")
@click.option("--repo", "-p", default=".", show_default=True, help="Repo root path.")
@click.option(
    "--person",
    default=_DEFAULT_PERSON,
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
    default=_DEFAULT_PERSON,
    show_default=True,
    help=_PERSON_HELP,
)
@click.option("--session", default=None, help="Session UUID.")
@click.option(
    "--force",
    is_flag=True,
    help="Skip the readiness check and prune even if turns are in the current session.",
)
def prune_cmd(window: int, repo: str, person: str, session: str | None, force: bool) -> None:
    """Run KG Context Pruning — compress old turns into Summary nodes.

    By default, only turns from completed (closed) sessions are eligible for
    pruning — these are called "cold turns".  If all your turns are in the
    current session, use --force to prune anyway.
    """
    kg = _resolve_kg(repo, person, session)
    if not force and not kg.should_prune():
        all_turns = kg._store.get_all_turns()
        cold_count = max(0, len(all_turns) - window)
        click.echo(
            f"Not enough cold turns to prune yet "
            f"({cold_count} cold, need {3 * 2} minimum from completed sessions).\n"
            "Use --force to prune the current session anyway, "
            "or --window to reduce the hot window."
        )
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
    default=_DEFAULT_PERSON,
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
    default=_DEFAULT_PERSON,
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
    default=_DEFAULT_PERSON,
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
    default=_DEFAULT_PERSON,
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
    default=_DEFAULT_PERSON,
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
    default=_DEFAULT_PERSON,
    show_default=True,
    help=_PERSON_HELP,
)
def profile(repo: str, person: str) -> None:
    """Show the UserProfile for this person."""
    kg = _resolve_kg(repo, person, None)
    click.echo(kg.profile.render_markdown())
    kg.close()


@cli.command("profile-set")
@click.option("--repo", "-p", default=".", show_default=True, help="Repo root path.")
@click.option(
    "--person",
    default=_DEFAULT_PERSON,
    show_default=True,
    help=_PERSON_HELP,
)
@click.option("--name", default=None, help="Full name.")
@click.option("--email", default=None, help="Email address.")
@click.option("--phone", default=None, help="Phone number.")
@click.option("--address", default=None, help="Home / mailing address.")
@click.option("--birth-date", "birth_date", default=None, help="Birth date (YYYY-MM-DD).")
@click.option("--gender", default=None, help="Gender.")
@click.option(
    "--cognitive-score",
    "cognitive_score",
    type=int,
    default=None,
    help="Cognitive clarity score 0-100.",
)
@click.option(
    "--delta-year",
    "delta_year",
    type=int,
    default=None,
    help="Year offset from birth for diary entry timestamps (0-150).",
)
@click.option(
    "--education",
    "education_entries",
    multiple=True,
    help="Add an education entry (repeatable). E.g. --education 'PhD CS, MIT, 1998'.",
)
@click.option("--preference", "preferences", multiple=True, help="Add a preference (repeatable).")
@click.option(
    "--commitment",
    "commitments",
    multiple=True,
    help="Add a standing rule/commitment (repeatable).",
)
@click.option(
    "--expertise", "expertise_entries", multiple=True, help="Add an expertise (repeatable)."
)
@click.option("--interest", "interests", multiple=True, help="Add an interest (repeatable).")
@click.option("--style", "styles", multiple=True, help="Add a style note (repeatable).")
def profile_set(
    repo: str,
    person: str,
    name: str | None,
    email: str | None,
    phone: str | None,
    address: str | None,
    birth_date: str | None,
    gender: str | None,
    cognitive_score: int | None,
    delta_year: int | None,
    education_entries: tuple[str, ...],
    preferences: tuple[str, ...],
    commitments: tuple[str, ...],
    expertise_entries: tuple[str, ...],
    interests: tuple[str, ...],
    styles: tuple[str, ...],
) -> None:
    """Update identity fields and/or add knowledge-graph profile nodes.

    Only the options you pass are written — unspecified fields are unchanged.
    Node options (--preference, --commitment, etc.) are all repeatable.

    Examples::

        agent-kg profile-set --name "Alice Smith" --email alice@example.com
        agent-kg profile-set --commitment "always write pytest tests for new code"
        agent-kg profile-set --preference "concise responses" --style ":param: docstrings"
        agent-kg profile-set --education "BSc Physics, Oxford, 1990" \\
                              --education "PhD CS, MIT, 1995"
    """
    from agent_kg.schema import NodeKind  # noqa: PLC0415

    kg = _resolve_kg(repo, person, None)

    # Update identity fields (only non-None)
    has_identity = any(
        v is not None
        for v in (name, email, phone, address, birth_date, gender, cognitive_score, delta_year)
    )
    if has_identity:
        updated = kg.profile.set_identity(
            name=name,
            email=email,
            phone=phone,
            address=address,
            birth_date=birth_date,
            gender=gender,
            cognitive_score=cognitive_score,
            delta_year=delta_year,
        )
        click.echo("Identity updated:")
        for k, v in updated.items():
            if v not in ("", 0, None) or k in ("cognitive_score", "delta_year"):
                click.echo(f"  {k}: {v}")

    # Knowledge-graph profile nodes
    node_groups = [
        (NodeKind.EDUCATION, education_entries, "Education"),
        (NodeKind.PREFERENCE, preferences, "Preference"),
        (NodeKind.COMMITMENT, commitments, "Commitment"),
        (NodeKind.EXPERTISE, expertise_entries, "Expertise"),
        (NodeKind.INTEREST, interests, "Interest"),
        (NodeKind.STYLE, styles, "Style"),
    ]
    any_nodes = False
    for kind, entries, label in node_groups:
        for entry in entries:
            kg.profile.upsert(kind=kind, label=entry[:120], text=entry)
            click.echo(f"{label} added: {entry}")
            any_nodes = True

    if not has_identity and not any_nodes:
        click.echo("Nothing to update — pass at least one option. Use --help for options.")

    kg.close()


@cli.command("profile-remove")
@click.option("--repo", "-p", default=".", show_default=True, help="Repo root path.")
@click.option(
    "--person",
    default=_DEFAULT_PERSON,
    show_default=True,
    help=_PERSON_HELP,
)
@click.option(
    "--preference", "preferences", multiple=True, help="Remove a preference by label (repeatable)."
)
@click.option(
    "--commitment", "commitments", multiple=True, help="Remove a commitment by label (repeatable)."
)
@click.option(
    "--expertise",
    "expertise_entries",
    multiple=True,
    help="Remove an expertise by label (repeatable).",
)
@click.option(
    "--interest", "interests", multiple=True, help="Remove an interest by label (repeatable)."
)
@click.option("--style", "styles", multiple=True, help="Remove a style note by label (repeatable).")
@click.option(
    "--education",
    "education_entries",
    multiple=True,
    help="Remove an education entry by label (repeatable).",
)
@click.option("--clear-preferences", is_flag=True, help="Wipe all preferences.")
@click.option("--clear-commitments", is_flag=True, help="Wipe all commitments.")
@click.option("--clear-expertise", is_flag=True, help="Wipe all expertise nodes.")
@click.option("--clear-interests", is_flag=True, help="Wipe all interests.")
@click.option("--clear-styles", is_flag=True, help="Wipe all style notes.")
@click.option("--clear-education", is_flag=True, help="Wipe all education entries.")
@click.option("--clear-all", is_flag=True, help="Wipe every profile node (identity is preserved).")
def profile_remove(
    repo: str,
    person: str,
    preferences: tuple[str, ...],
    commitments: tuple[str, ...],
    expertise_entries: tuple[str, ...],
    interests: tuple[str, ...],
    styles: tuple[str, ...],
    education_entries: tuple[str, ...],
    clear_preferences: bool,
    clear_commitments: bool,
    clear_expertise: bool,
    clear_interests: bool,
    clear_styles: bool,
    clear_education: bool,
    clear_all: bool,
) -> None:
    """Remove specific profile nodes or wipe entire categories.

    Examples::

        agent-kg profile-remove --commitment "always write pytest tests for new code"
        agent-kg profile-remove --clear-preferences
        agent-kg profile-remove --clear-all
    """
    from agent_kg.schema import NodeKind  # noqa: PLC0415

    kg = _resolve_kg(repo, person, None)
    did_something = False

    # Wipe entire categories
    clear_map = [
        (clear_all or clear_preferences, NodeKind.PREFERENCE, "preferences"),
        (clear_all or clear_commitments, NodeKind.COMMITMENT, "commitments"),
        (clear_all or clear_expertise, NodeKind.EXPERTISE, "expertise"),
        (clear_all or clear_interests, NodeKind.INTEREST, "interests"),
        (clear_all or clear_styles, NodeKind.STYLE, "styles"),
        (clear_all or clear_education, NodeKind.EDUCATION, "education"),
    ]
    for flag, kind, label in clear_map:
        if flag:
            n = kg.profile.clear_kind(kind)
            click.echo(f"Cleared {n} {label}.")
            did_something = True

    # Remove specific nodes by label
    node_groups = [
        (NodeKind.PREFERENCE, preferences, "Preference"),
        (NodeKind.COMMITMENT, commitments, "Commitment"),
        (NodeKind.EXPERTISE, expertise_entries, "Expertise"),
        (NodeKind.INTEREST, interests, "Interest"),
        (NodeKind.STYLE, styles, "Style"),
        (NodeKind.EDUCATION, education_entries, "Education"),
    ]
    for kind, entries, label in node_groups:
        for entry in entries:
            found = kg.profile.delete(kind=kind, label=entry)
            if found:
                click.echo(f"{label} removed: {entry}")
            else:
                click.echo(f"{label} not found: {entry}")
            did_something = True

    if not did_something:
        click.echo("Nothing to remove — pass at least one option. Use --help for options.")

    kg.close()


# Claude Code hooks block — merged into .claude/settings.json by install-hooks --claude
_CLAUDE_HOOKS = {
    "UserPromptSubmit": [
        {
            "hooks": [
                {
                    "type": "command",
                    "command": (
                        "PROMPT=$(jq -r '.prompt'); "
                        "REPO_ROOT=\"$(git rev-parse --show-toplevel 2>/dev/null || echo '.')\"; "
                        'agent-kg ingest "$PROMPT" --role user --repo "$REPO_ROOT" '
                        "2>/dev/null || true"
                    ),
                    "async": True,
                }
            ]
        }
    ],
    "Stop": [
        {
            "hooks": [
                {
                    "type": "command",
                    "command": (
                        "MSG=$(jq -r '.last_assistant_message // empty'); "
                        "REPO_ROOT=\"$(git rev-parse --show-toplevel 2>/dev/null || echo '.')\"; "
                        '[ -n "$MSG" ] && agent-kg ingest "$MSG" --role assistant '
                        '--repo "$REPO_ROOT" --no-embed 2>/dev/null || true'
                    ),
                    "async": True,
                },
                {
                    "type": "command",
                    "command": (
                        "REPO_ROOT=\"$(git rev-parse --show-toplevel 2>/dev/null || echo '.')\"; "
                        'agent-kg snapshot --repo "$REPO_ROOT" --label "session-end" '
                        "2>/dev/null || true"
                    ),
                    "async": True,
                },
            ]
        }
    ],
}

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
@click.option(
    "--claude",
    "claude_hooks",
    is_flag=True,
    help="Also install Claude Code auto-ingest hooks into .claude/settings.json.",
)
@click.option(
    "--global",
    "global_hooks",
    is_flag=True,
    help="Install Claude Code hooks into ~/.claude/settings.json (all repos).",
)
def install_hooks(repo: str, force: bool, claude_hooks: bool, global_hooks: bool) -> None:
    """Install the AgentKG pre-commit git hook and/or Claude Code auto-ingest hooks.

    Git pre-commit hook (default):
      1. Rebuilds local CodeKG index if codekg is installed
      2. Rebuilds local DocKG index if dockg is installed and docs/ exists
      3. Captures metrics snapshots for both KGs keyed by tree hash
      4. Stages both snapshot directories atomically
      5. Runs pre-commit framework checks (ruff, mypy, detect-secrets, etc.)

    Claude Code hooks (--claude or --global):
      Installs UserPromptSubmit + Stop hooks that auto-ingest every user and
      assistant turn into the AgentKG conversation graph.  Use --claude for
      project-level (.claude/settings.json) or --global for all repos
      (~/.claude/settings.json).
    """
    import json  # noqa: PLC0415
    import stat  # noqa: PLC0415

    repo_root = Path(repo).resolve()

    # ── Git pre-commit hook ───────────────────────────────────────────────────
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

    # ── Claude Code hooks ─────────────────────────────────────────────────────
    targets: list[Path] = []
    if global_hooks:
        targets.append(Path.home() / ".claude" / "settings.json")
    if claude_hooks:
        targets.append(repo_root / ".claude" / "settings.json")

    for settings_path in targets:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict = {}
        if settings_path.exists():
            try:
                existing = json.loads(settings_path.read_text())
            except json.JSONDecodeError:
                click.echo(f"Warning: could not parse {settings_path} — skipping.", err=True)
                continue

        existing_hooks = existing.setdefault("hooks", {})
        updated = False
        for event, entries in _CLAUDE_HOOKS.items():
            if event not in existing_hooks:
                existing_hooks[event] = entries
                updated = True
            else:
                click.echo(f"  {event} hook already present in {settings_path} — skipping.")

        if updated or not settings_path.exists():
            settings_path.write_text(json.dumps(existing, indent=2) + "\n")
            click.echo(f"OK Claude Code hooks written to: {settings_path}")
            click.echo("  Turns will be auto-ingested on UserPromptSubmit and Stop.")
        else:
            click.echo(f"  No changes needed in {settings_path}.")


@cli.command()
@click.option(
    "--person",
    default=_DEFAULT_PERSON,
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
@click.option("--repo", "-p", default=".", show_default=True, help="Repo root path.")
@click.option(
    "--person",
    default=_DEFAULT_PERSON,
    show_default=True,
    help=_PERSON_HELP,
)
@click.option(
    "--local", "wipe_local", is_flag=True, help="Wipe local conversation graph (.agentkg/)."
)
@click.option(
    "--global",
    "wipe_global",
    is_flag=True,
    help="Wipe global user profile (~/.kgrag/profiles/<person>/).",
)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def wipe(repo: str, person: str, wipe_local: bool, wipe_global: bool, yes: bool) -> None:
    """Erase the local conversation graph and/or the global user profile.

    Examples::

        # wipe only the local graph for this repo
        agent-kg wipe --local --person egs

        # wipe the global profile (all repos)
        agent-kg wipe --global --person egs

        # wipe everything without prompting
        agent-kg wipe --local --global --person egs --yes
    """
    import shutil  # noqa: PLC0415

    if not wipe_local and not wipe_global:
        click.echo("Nothing to wipe. Use --local, --global, or both.", err=True)
        raise SystemExit(1)

    repo_root = Path(repo).resolve()
    local_dir = repo_root / ".agentkg"
    global_dir = Path.home() / ".kgrag" / "profiles" / person

    targets = []
    if wipe_local:
        targets.append(("Local conversation graph", local_dir))
    if wipe_global:
        targets.append((f"Global user profile ({person})", global_dir))

    if not yes:
        click.echo("The following will be permanently deleted:")
        for label, path in targets:
            exists = "exists" if path.exists() else "does not exist"
            click.echo(f"  {label}: {path}  [{exists}]")
        click.confirm("Continue?", abort=True)

    for label, path in targets:
        if path.exists():
            shutil.rmtree(path)
            click.echo(f"Wiped: {path}")
        else:
            click.echo(f"Already gone: {path}")


@cli.command()
@click.option("--repo", "-p", default=".", show_default=True, help="Repo root path.")
@click.option("--person", default=_DEFAULT_PERSON, show_default=True, help=_PERSON_HELP)
@click.option(
    "--agent", "show_agent", is_flag=True, default=False, help="Show agent conversation tree."
)
@click.option(
    "--profile", "show_profile", is_flag=True, default=False, help="Show UserProfile tree."
)
@click.option("--html", is_flag=True, help="Render as interactive HTML (opens in browser).")
@click.option(
    "--out", default=None, type=click.Path(), help="Write HTML to this file instead of a temp file."
)
@click.option(
    "--serve", is_flag=True, help="Launch the Streamlit explorer (requires streamlit + pyvis)."
)
@click.option("--port", default="8501", show_default=True, help="Streamlit server port.")
def viz(
    repo: str,
    person: str,
    show_agent: bool,
    show_profile: bool,
    html: bool,
    out: str | None,
    serve: bool,
    port: str,
) -> None:
    """Visualize the agent conversation and/or UserProfile trees.

    Without flags, renders both trees as Rich terminal output.

    Examples::

        # Terminal trees (no deps)
        agent-kg viz --person egs

        # Interactive HTML for the conversation graph
        agent-kg viz --agent --html --person egs

        # Interactive HTML for the profile
        agent-kg viz --profile --html --person egs --out profile.html

        # Full Streamlit explorer
        agent-kg viz --serve --person egs
    """
    import importlib.util  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    import sys  # noqa: PLC0415

    from agent_kg.viz import (  # noqa: PLC0415
        build_agent_html,
        build_profile_html,
        render_agent_tree_rich,
        render_profile_tree_rich,
        write_html,
    )

    repo_root = Path(repo).resolve()
    agent_db = repo_root / ".agentkg" / "graph.sqlite"
    profile_db = Path.home() / ".kgrag" / "profiles" / person / "userprofile.sqlite"

    # Default: show both
    if not show_agent and not show_profile:
        show_agent = True
        show_profile = True

    # ── Streamlit explorer ────────────────────────────────────────────────────
    if serve:
        if importlib.util.find_spec("streamlit") is None:
            raise click.UsageError('streamlit is not installed. Run: pip install "agent-kg[viz]"')
        app_path = Path(__file__).parent.parent / "app.py"
        cmd = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app_path),
            "--server.port",
            port,
            "--",
            "--repo",
            str(repo_root),
            "--person",
            person,
        ]
        click.echo(f"Launching AgentKG Explorer on http://localhost:{port}")
        click.echo("  Press Ctrl+C to stop.\n")
        try:
            subprocess.run(cmd, check=True)
        except KeyboardInterrupt:
            click.echo("\nStopped.")
        return

    # ── HTML output — global first, skip missing local silently ──────────────
    if html:
        if show_profile and profile_db.exists():
            prof_html = build_profile_html(profile_db)
            prof_out = (
                Path(out)
                if (out and not show_agent)
                else Path.home() / ".kgrag" / "profiles" / person / "viz_profile.html"
            )
            write_html(prof_html, prof_out)
            click.echo(f"Profile graph → {prof_out}")

        if show_agent and agent_db.exists():
            agent_html = build_agent_html(agent_db)
            out_path = Path(out) if out else Path(repo_root) / ".agentkg" / "viz_agent.html"
            write_html(agent_html, out_path)
            click.echo(f"Agent graph → {out_path}")
        return

    # ── Rich terminal trees — global (profile) first, then local (agent) ─────
    if show_profile:
        render_profile_tree_rich(profile_db)

    if show_agent:
        render_agent_tree_rich(agent_db)


@cli.command()
def mcp() -> None:
    """Start the AgentKG MCP server."""
    from agent_kg.mcp.server import main as mcp_main  # noqa: PLC0415

    mcp_main()


if __name__ == "__main__":
    cli()
