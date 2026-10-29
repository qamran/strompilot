"""Household memory store: preferences plus episodes in SQLite."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import Episode, MemoryError, Preference

_SCHEMA = """
CREATE TABLE IF NOT EXISTS preferences (
    household_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (household_id, key)
);
CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    household_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_episodes_household
    ON episodes (household_id, id DESC);
"""


def _require(label: str, value: str) -> str:
    """Normalize identifiers and texts, rejecting blank ones loudly."""
    stripped = value.strip()
    if not stripped:
        raise MemoryError(f"{label} must not be blank")
    return stripped


def _escape_like(value: str) -> str:
    """Escape user text for a LIKE pattern."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class MemoryStore:
    """Household-scoped preferences and episodes with forgetting."""

    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Yield one committed-plus-closed connection per operation."""
        conn = sqlite3.connect(self._path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def set_preference(self, household_id: str, key: str, value: Any) -> Preference:
        """Create or overwrite one preference, returning it."""
        household_id = _require("household_id", household_id)
        key = _require("key", key)
        stamp = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO preferences (household_id, key, value, updated_at)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT (household_id, key) DO UPDATE SET"
                " value = excluded.value, updated_at = excluded.updated_at",
                (household_id, key, json.dumps(value), stamp),
            )
        return Preference(
            household_id=household_id,
            key=key,
            value=value,
            updated_at=datetime.fromisoformat(stamp),
        )

    def get_preference(self, household_id: str, key: str) -> Any | None:
        """Return one preference value, or None when missing."""
        household_id = _require("household_id", household_id)
        key = _require("key", key)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM preferences WHERE household_id = ? AND key = ?",
                (household_id, key),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def list_households(self) -> list[str]:
        """List every household id known to either table, ordered."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT household_id FROM preferences"
                " UNION SELECT household_id FROM episodes"
                " ORDER BY household_id"
            ).fetchall()
        return [str(row[0]) for row in rows]

    def delete_preference(self, household_id: str, key: str) -> bool:
        """Delete one preference, reporting whether it existed."""
        household_id = _require("household_id", household_id)
        key = _require("key", key)
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM preferences WHERE household_id = ? AND key = ?",
                (household_id, key),
            )
        return cursor.rowcount > 0

    def list_preferences(self, household_id: str) -> list[Preference]:
        """List every preference of one household, ordered by key."""
        household_id = _require("household_id", household_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT household_id, key, value, updated_at FROM preferences"
                " WHERE household_id = ? ORDER BY key",
                (household_id,),
            ).fetchall()
        return [
            Preference(
                household_id=row[0],
                key=row[1],
                value=json.loads(row[2]),
                updated_at=datetime.fromisoformat(row[3]),
            )
            for row in rows
        ]

    def add_episode(self, household_id: str, kind: str, text: str) -> Episode:
        """Append one timestamped memory, returning it with its id."""
        household_id = _require("household_id", household_id)
        kind = _require("kind", kind)
        text = _require("text", text)
        stamp = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO episodes (household_id, kind, text, created_at)"
                " VALUES (?, ?, ?, ?)",
                (household_id, kind, text, stamp),
            )
            episode_id = cursor.lastrowid or 0
        return Episode(
            id=episode_id,
            household_id=household_id,
            kind=kind,
            text=text,
            created_at=datetime.fromisoformat(stamp),
        )

    def list_episodes(
        self, household_id: str, kind: str | None = None, limit: int = 50
    ) -> list[Episode]:
        """List one household's memories, newest first."""
        household_id = _require("household_id", household_id)
        query = (
            "SELECT id, household_id, kind, text, created_at FROM episodes"
            " WHERE household_id = ?"
        )
        params: list[object] = [household_id]
        if kind is not None:
            query += " AND kind = ?"
            params.append(kind)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._to_episode(row) for row in rows]

    def search_episodes(
        self, household_id: str, query: str, limit: int = 20
    ) -> list[Episode]:
        """Find one household's memories by case-insensitive substring."""
        household_id = _require("household_id", household_id)
        query = _require("query", query)
        pattern = f"%{_escape_like(query)}%"
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, household_id, kind, text, created_at FROM episodes"
                " WHERE household_id = ? AND text LIKE ? ESCAPE '\\'"
                " ORDER BY id DESC LIMIT ?",
                (household_id, pattern, limit),
            ).fetchall()
        return [self._to_episode(row) for row in rows]

    def delete_episode(self, household_id: str, episode_id: int) -> bool:
        """Delete one memory of one household, reporting success."""
        household_id = _require("household_id", household_id)
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM episodes WHERE household_id = ? AND id = ?",
                (household_id, episode_id),
            )
        return cursor.rowcount > 0

    def forget_household(self, household_id: str) -> None:
        """Delete every preference and memory of one household."""
        household_id = _require("household_id", household_id)
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM preferences WHERE household_id = ?",
                (household_id,),
            )
            conn.execute(
                "DELETE FROM episodes WHERE household_id = ?",
                (household_id,),
            )

    @staticmethod
    def _to_episode(row: tuple[object, ...]) -> Episode:
        """Map one database row to an Episode."""
        id_value, household, kind, text, stamp = row
        assert isinstance(id_value, int)
        assert isinstance(household, str)
        assert isinstance(kind, str)
        assert isinstance(text, str)
        assert isinstance(stamp, str)
        return Episode(
            id=id_value,
            household_id=household,
            kind=kind,
            text=text,
            created_at=datetime.fromisoformat(stamp),
        )
