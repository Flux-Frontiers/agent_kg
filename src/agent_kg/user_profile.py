# Copyright (c) 2026 Eric G. Suchanek, PhD. All rights reserved.
# SPDX-License-Identifier: Elastic-2.0

"""profile.py — UserProfile tree: globally persistent personal knowledge.

Stores Preference, Style, Interest, Expertise, Commitment, and Context
nodes for a person in user-scoped storage (~/.kgrag/profiles/<person_id>/).

This tree is NEVER pruned — it only grows and is updated in place.
One canonical profile exists regardless of which repo you're working in.

Syncs key fields back to KGRAG PersonCorpusEntry metadata at session close.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_kg.schema import Node, NodeKind

_PROFILE_SCHEMA = """
CREATE TABLE IF NOT EXISTS profile_nodes (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL,
    label       TEXT NOT NULL,
    text        TEXT DEFAULT '',
    confidence  REAL DEFAULT 1.0,
    category    TEXT DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    metadata    TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_profile_kind ON profile_nodes(kind);

CREATE TABLE IF NOT EXISTS profile_edges (
    id         TEXT PRIMARY KEY,
    source_id  TEXT NOT NULL,
    target_id  TEXT NOT NULL,
    relation   TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profile_identity (
    id              TEXT PRIMARY KEY DEFAULT 'singleton',
    name            TEXT DEFAULT '',
    email           TEXT DEFAULT '',
    phone           TEXT DEFAULT '',
    address         TEXT DEFAULT '',
    birth_date      TEXT DEFAULT '',
    gender          TEXT DEFAULT '',
    cognitive_score INTEGER DEFAULT 100,
    delta_year      INTEGER DEFAULT 0,
    updated_at      TEXT NOT NULL
);
"""


class UserProfileStore:
    """SQLite-backed UserProfile tree for a single person.

    :param profile_dir: Path to ``~/.kgrag/profiles/<person_id>/``.
    """

    def __init__(self, profile_dir: Path) -> None:
        self._dir = Path(profile_dir)
        self._db_path = self._dir / "userprofile.sqlite"
        self._db: sqlite3.Connection | None = None

    def _get_db(self) -> sqlite3.Connection:
        if self._db is None:
            self._dir.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(str(self._db_path), check_same_thread=False)
            self._db.row_factory = sqlite3.Row
            self._db.executescript(_PROFILE_SCHEMA)
            self._db.commit()
        return self._db

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    def upsert(
        self,
        kind: NodeKind,
        label: str,
        text: str = "",
        confidence: float = 1.0,
        category: str = "",
    ) -> Node:
        """Insert a new profile node or update confidence + text if label exists.

        :param kind: NodeKind (PREFERENCE, EXPERTISE, INTEREST, etc.)
        :param label: Short canonical label for this fact.
        :param text: Full original text for provenance.
        :param confidence: Confidence score 0-1.
        :param category: Optional sub-category.
        :return: The upserted Node.
        """
        import uuid  # noqa: PLC0415

        db = self._get_db()
        now = datetime.now(UTC).isoformat()

        # Check for existing node with same kind + label (case-insensitive)
        row = db.execute(
            "SELECT * FROM profile_nodes WHERE kind = ? AND LOWER(label) = LOWER(?)",
            (str(kind), label),
        ).fetchone()

        if row:
            # Update confidence and text
            new_conf = min(1.0, max(float(row["confidence"]), confidence))
            db.execute(
                "UPDATE profile_nodes SET confidence = ?, text = ?, updated_at = ? WHERE id = ?",
                (new_conf, text or row["text"], now, row["id"]),
            )
            db.commit()
            return self._row_to_node(dict(row))
        node_id = str(uuid.uuid4())
        db.execute(
            """INSERT INTO profile_nodes
               (id, kind, label, text, confidence, category, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (node_id, str(kind), label, text, confidence, category, now, now),
        )
        db.commit()
        return Node(
            id=node_id,
            kind=kind,
            label=label,
            text=text,
            confidence=confidence,
            category=category,
        )

    def apply_updates(self, updates: list[dict[str, Any]]) -> list[Node]:
        """Apply a batch of NLP-extracted preference/commitment/expertise records.

        Each dict must have ``kind``, ``label``, and ``text`` keys.

        :param updates: List of ``{"kind", "label", "text"}`` dicts from
                        :func:`~agent_kg.nlp.preferences.extract_preferences`.
        :return: List of upserted nodes.
        """
        kind_map = {
            "preference": NodeKind.PREFERENCE,
            "style": NodeKind.STYLE,
            "interest": NodeKind.INTEREST,
            "expertise": NodeKind.EXPERTISE,
            "commitment": NodeKind.COMMITMENT,
            "context": NodeKind.CONTEXT,
        }
        nodes = []
        for u in updates:
            kind_key = u.get("kind", "preference")
            node_kind = kind_map.get(kind_key, NodeKind.PREFERENCE)
            node = self.upsert(
                kind=node_kind,
                label=u["label"],
                text=u.get("text", u["label"]),
            )
            nodes.append(node)
        return nodes

    # ------------------------------------------------------------------
    # Identity (structured personal/biographical data)
    # ------------------------------------------------------------------

    def set_identity(
        self,
        name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        address: str | None = None,
        birth_date: str | None = None,
        gender: str | None = None,
        cognitive_score: int | None = None,
        delta_year: int | None = None,
    ) -> dict[str, Any]:
        """Upsert the singleton identity record.

        Only non-None arguments are written — pass only what you want to change.

        :param name: Full name.
        :param email: Email address.
        :param phone: Phone number (any format).
        :param address: Home / mailing address (free-form).
        :param birth_date: ISO date string ``YYYY-MM-DD``.
        :param gender: Gender string.
        :param cognitive_score: Cognitive clarity score 0-100.
        :param delta_year: Year offset from birth for diary entry timestamps
            (0-150).  Lets you simulate writing at a specific life age.
        :return: The updated identity dict.
        """
        db = self._get_db()
        now = datetime.now(UTC).isoformat()

        row = db.execute("SELECT * FROM profile_identity WHERE id = 'singleton'").fetchone()
        if row is None:
            db.execute(
                "INSERT INTO profile_identity (id, updated_at) VALUES ('singleton', ?)",
                (now,),
            )
            db.commit()
            row = db.execute("SELECT * FROM profile_identity WHERE id = 'singleton'").fetchone()

        updates: list[tuple[Any, str]] = []
        if name is not None:
            updates.append((name, "name"))
        if email is not None:
            updates.append((email, "email"))
        if phone is not None:
            updates.append((phone, "phone"))
        if address is not None:
            updates.append((address, "address"))
        if birth_date is not None:
            updates.append((birth_date, "birth_date"))
        if gender is not None:
            updates.append((gender, "gender"))
        if cognitive_score is not None:
            updates.append((max(0, min(100, int(cognitive_score))), "cognitive_score"))
        if delta_year is not None:
            updates.append((max(0, min(150, int(delta_year))), "delta_year"))

        for value, col in updates:
            db.execute(
                f"UPDATE profile_identity SET {col} = ?, updated_at = ?"  # noqa: S608
                " WHERE id = 'singleton'",
                (value, now),
            )
        db.commit()
        return self.get_identity()

    def get_identity(self) -> dict[str, Any]:
        """Return the identity record as a plain dict (empty defaults if not set).

        :return: Dict with keys: ``name``, ``email``, ``phone``, ``address``,
                 ``birth_date``, ``gender``, ``cognitive_score``.
        """
        row = (
            self._get_db()
            .execute("SELECT * FROM profile_identity WHERE id = 'singleton'")
            .fetchone()
        )
        if row is None:
            return {
                "name": "",
                "email": "",
                "phone": "",
                "address": "",
                "birth_date": "",
                "gender": "",
                "cognitive_score": 100,
                "delta_year": 0,
            }
        return {
            "name": row["name"] or "",
            "email": row["email"] or "",
            "phone": row["phone"] or "",
            "address": row["address"] or "",
            "birth_date": row["birth_date"] or "",
            "gender": row["gender"] or "",
            "cognitive_score": row["cognitive_score"]
            if row["cognitive_score"] is not None
            else 100,
            "delta_year": row["delta_year"] if row["delta_year"] is not None else 0,
        }

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_by_kind(self, kind: NodeKind) -> list[Node]:
        """Return all profile nodes of a given kind."""
        rows = (
            self._get_db()
            .execute(
                "SELECT * FROM profile_nodes WHERE kind = ? ORDER BY confidence DESC",
                (str(kind),),
            )
            .fetchall()
        )
        return [self._row_to_node(dict(r)) for r in rows]

    def preferences(self) -> list[Node]:
        """Return all Preference nodes."""
        return self.get_by_kind(NodeKind.PREFERENCE)

    def commitments(self) -> list[Node]:
        """Return all Commitment nodes."""
        return self.get_by_kind(NodeKind.COMMITMENT)

    def expertise(self) -> list[Node]:
        """Return all Expertise nodes."""
        return self.get_by_kind(NodeKind.EXPERTISE)

    def interests(self) -> list[Node]:
        """Return all Interest nodes."""
        return self.get_by_kind(NodeKind.INTEREST)

    def styles(self) -> list[Node]:
        """Return all Style nodes."""
        return self.get_by_kind(NodeKind.STYLE)

    def education(self) -> list[Node]:
        """Return all Education nodes."""
        return self.get_by_kind(NodeKind.EDUCATION)

    def all_nodes(self) -> list[Node]:
        """Return all profile nodes ordered by kind + confidence."""
        rows = (
            self._get_db()
            .execute("SELECT * FROM profile_nodes ORDER BY kind, confidence DESC")
            .fetchall()
        )
        return [self._row_to_node(dict(r)) for r in rows]

    def search(self, q: str, k: int = 8) -> list[dict[str, Any]]:
        """Keyword search over profile nodes (label + text fields).

        Returns nodes whose label or text contains any word from *q*,
        ranked by number of matching words then confidence.  Since profile
        nodes live in a separate SQLite without vector embeddings, this is
        a lightweight text-match fallback rather than semantic search.

        :param q: Query string — matched word-by-word (case-insensitive).
        :param k: Maximum number of results.
        :return: List of ``{"node_id", "kind", "text", "label", "score", "source"}``
                 dicts compatible with the conversation-graph hit format.
        """
        words = [w.lower() for w in q.split() if len(w) > 2]
        if not words:
            return []

        nodes = self.all_nodes()
        scored: list[tuple[float, Node]] = []
        for node in nodes:
            # Include the node kind so queries like "style preference" can match :param: nodes
            haystack = f"{node.kind} {node.label} {node.text or ''}".lower()
            hits = sum(1 for w in words if w in haystack)
            if hits > 0:
                score = round(hits / len(words) * node.confidence, 3)
                scored.append((score, node))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, node in scored[:k]:
            results.append(
                {
                    "node_id": node.id,
                    "kind": str(node.kind),
                    "text": node.text or node.label,
                    "label": node.label,
                    "role": None,
                    "score": score,
                    "source": "profile",
                }
            )
        return results

    def summary(self) -> dict[str, Any]:
        """Return a structured summary of the profile (for PersonCorpusEntry sync)."""
        return {
            "identity": self.get_identity(),
            "education": [n.label for n in self.education()],
            "preferences": [n.label for n in self.preferences()],
            "commitments": [n.label for n in self.commitments()],
            "expertise": [n.label for n in self.expertise()],
            "interests": [n.label for n in self.interests()],
            "styles": [n.label for n in self.styles()],
        }

    def render_markdown(self) -> str:
        """Render the full UserProfile as a Markdown report."""
        lines = ["# UserProfile\n"]

        # Identity section
        identity = self.get_identity()
        identity_fields = [
            ("Name", identity.get("name")),
            ("Email", identity.get("email")),
            ("Phone", identity.get("phone")),
            ("Address", identity.get("address")),
            ("Birth date", identity.get("birth_date")),
            ("Gender", identity.get("gender")),
            (
                "Cognitive score",
                str(identity["cognitive_score"])
                if identity.get("cognitive_score") is not None
                else None,
            ),
            ("Delta year", str(identity["delta_year"]) if identity.get("delta_year") else None),
        ]
        shown = [(k, v) for k, v in identity_fields if v]
        if shown:
            lines.append("## Identity")
            for key, val in shown:
                lines.append(f"- **{key}:** {val}")
            lines.append("")

        # Education
        edu_nodes = self.education()
        if edu_nodes:
            lines.append("## Education")
            for n in edu_nodes:
                lines.append(f"- {n.label}")
            lines.append("")

        # Knowledge graph sections
        sections = [
            ("Commitments", self.commitments()),
            ("Preferences", self.preferences()),
            ("Expertise", self.expertise()),
            ("Interests", self.interests()),
            ("Style", self.styles()),
        ]
        for title, nodes in sections:
            if nodes:
                lines.append(f"## {title}")
                for n in nodes:
                    conf_pct = int(n.confidence * 100)
                    lines.append(f"- {n.label} *(confidence: {conf_pct}%)*")
                lines.append("")
        return "\n".join(lines)

    def delete(self, kind: NodeKind, label: str) -> bool:
        """Delete a single profile node by kind + label (case-insensitive).

        :param kind: NodeKind of the node to remove.
        :param label: Label of the node to remove.
        :return: True if a row was deleted, False if not found.
        """
        db = self._get_db()
        cur = db.execute(
            "DELETE FROM profile_nodes WHERE kind = ? AND LOWER(label) = LOWER(?)",
            (str(kind), label),
        )
        db.commit()
        return cur.rowcount > 0

    def clear_kind(self, kind: NodeKind) -> int:
        """Delete all profile nodes of a given kind.

        :param kind: NodeKind to wipe.
        :return: Number of rows deleted.
        """
        db = self._get_db()
        cur = db.execute("DELETE FROM profile_nodes WHERE kind = ?", (str(kind),))
        db.commit()
        return cur.rowcount

    def stats(self) -> dict[str, Any]:
        """Return total node count and per-kind breakdown."""
        db = self._get_db()
        count = db.execute("SELECT COUNT(*) FROM profile_nodes").fetchone()[0]
        kind_counts: dict[str, int] = {}
        for row in db.execute("SELECT kind, COUNT(*) FROM profile_nodes GROUP BY kind"):
            kind_counts[row[0]] = row[1]
        return {"total": count, "by_kind": kind_counts}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _row_to_node(self, r: dict) -> Node:
        def _dt(s):
            try:
                return datetime.fromisoformat(s)
            except Exception:  # pylint: disable=broad-exception-caught
                return datetime.now(UTC)

        return Node(
            id=r["id"],
            kind=NodeKind(r["kind"]),
            label=r.get("label", ""),
            text=r.get("text", ""),
            confidence=r.get("confidence", 1.0),
            category=r.get("category", ""),
            created_at=_dt(r.get("created_at")),
            updated_at=_dt(r.get("updated_at")),
            metadata=json.loads(r.get("metadata", "{}")),
        )

    def close(self) -> None:
        """Close the database connection."""
        if self._db:
            self._db.close()
            self._db = None
