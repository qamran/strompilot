"""Alert store: deduplicated alerts in SQLite."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from strompilot.memory.models import MemoryError

from .models import Alert, AlertCandidate

_SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    household_id TEXT NOT NULL,
    dedup_key TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL,
    channel TEXT,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    delivered_at TEXT,
    last_error TEXT
);
CREATE INDEX IF NOT EXISTS idx_alerts_household
    ON alerts (household_id, id DESC);
"""


def _require(label: str, value: str) -> str:
    """Normalize identifiers, rejecting blank ones loudly."""
    stripped = value.strip()
    if not stripped:
        raise MemoryError(f"{label} must not be blank")
    return stripped


def dedup_key(household_id: str, candidate: AlertCandidate) -> str:
    """Build the stable idempotency key for one judged window."""
    household_id = _require("household_id", household_id)
    return (
        f"{household_id}:{candidate.day.isoformat()}:{candidate.kind}"
        f":{candidate.start}-{candidate.end}"
    )


class AlertStore:
    """Household-scoped alerts with insert-level deduplication."""

    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as conn:
            conn.executescript(_SCHEMA)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(alerts)")}
            if "delivered_at" not in columns:
                conn.execute("ALTER TABLE alerts ADD COLUMN delivered_at TEXT")
            if "last_error" not in columns:
                conn.execute("ALTER TABLE alerts ADD COLUMN last_error TEXT")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Yield one committed-plus-closed connection per operation."""
        conn = sqlite3.connect(self._path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def record(
        self,
        household_id: str,
        dedup_key: str,
        kind: str,
        title: str,
        body: str,
        status: str,
        channel: str | None,
        reason: str,
    ) -> Alert | None:
        """Store one alert, or None when its key already exists."""
        household_id = _require("household_id", household_id)
        dedup_key = _require("dedup_key", dedup_key)
        stamp = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO alerts (household_id, dedup_key, kind,"
                " title, body, status, channel, reason, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    household_id,
                    dedup_key,
                    kind,
                    title,
                    body,
                    status,
                    channel,
                    reason,
                    stamp,
                ),
            )
            if cursor.rowcount == 0:
                return None
            alert_id = cursor.lastrowid or 0
        return Alert(
            id=alert_id,
            household_id=household_id,
            dedup_key=dedup_key,
            kind=kind,
            title=title,
            body=body,
            status=status,
            channel=channel,
            reason=reason,
            created_at=datetime.fromisoformat(stamp),
        )

    def known_keys(self, household_id: str) -> set[str]:
        """Return every dedup key already stored for one household."""
        household_id = _require("household_id", household_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT dedup_key FROM alerts WHERE household_id = ?",
                (household_id,),
            ).fetchall()
        return {str(row[0]) for row in rows}

    def list_alerts(self, household_id: str, limit: int = 50) -> list[Alert]:
        """List one household's alerts, oldest first."""
        household_id = _require("household_id", household_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, household_id, dedup_key, kind, title, body,"
                " status, channel, reason, created_at, delivered_at,"
                " last_error FROM alerts"
                " WHERE household_id = ? ORDER BY id ASC LIMIT ?",
                (household_id, limit),
            ).fetchall()
        return [self._to_alert(row) for row in rows]

    def held(self, household_id: str) -> list[Alert]:
        """List one household's quiet-held alerts, oldest first."""
        household_id = _require("household_id", household_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, household_id, dedup_key, kind, title, body,"
                " status, channel, reason, created_at, delivered_at,"
                " last_error FROM alerts"
                " WHERE household_id = ? AND status = 'held' ORDER BY id ASC",
                (household_id,),
            ).fetchall()
        return [self._to_alert(row) for row in rows]

    def set_status(
        self,
        alert_id: int,
        status: str,
        channel: str | None,
        error: str | None = None,
    ) -> None:
        """Move one alert to a new delivery state with its receipt."""
        stamp = (
            datetime.now(UTC).isoformat() if status in ("delivered", "failed") else None
        )
        with self._connect() as conn:
            conn.execute(
                "UPDATE alerts SET status = ?, channel = ?,"
                " delivered_at = ?, last_error = ? WHERE id = ?",
                (status, channel, stamp, error, alert_id),
            )

    def has_data(self, household_id: str) -> bool:
        """Report whether one household owns any alert."""
        household_id = _require("household_id", household_id)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM alerts WHERE household_id = ? LIMIT 1",
                (household_id,),
            ).fetchone()
        return row is not None

    def copy_household(self, source: str, target: str) -> int:
        """Copy one household's alerts into another household.

        Household-scoped keys are re-scoped to the target so the copied
        alerts keep deduplicating; foreign keys are skipped on collision.
        """
        source = _require("source", source)
        target = _require("target", target)
        prefix = f"{source}:"
        scoped = f"{target}:"
        with self._connect() as conn:
            count = conn.execute(
                "INSERT OR IGNORE INTO alerts (household_id, dedup_key, kind,"
                " title, body, status, channel, reason, created_at,"
                " delivered_at, last_error)"
                " SELECT ?, CASE WHEN SUBSTR(dedup_key, 1, ?) = ?"
                " THEN ? || SUBSTR(dedup_key, ?) ELSE dedup_key END,"
                " kind, title, body, status, channel, reason, created_at,"
                " delivered_at, last_error"
                " FROM alerts WHERE household_id = ? ORDER BY id",
                (target, len(prefix), prefix, scoped, len(prefix) + 1, source),
            ).rowcount
        return count

    @staticmethod
    def _to_alert(row: tuple[object, ...]) -> Alert:
        """Map one database row to an Alert."""
        (
            id_value,
            household,
            key,
            kind,
            title,
            body,
            status,
            channel,
            reason,
            stamp,
            delivered,
            last_error,
        ) = row
        assert isinstance(id_value, int)
        assert isinstance(household, str)
        assert isinstance(key, str)
        assert isinstance(kind, str)
        assert isinstance(title, str)
        assert isinstance(body, str)
        assert isinstance(status, str)
        assert channel is None or isinstance(channel, str)
        assert isinstance(reason, str)
        assert isinstance(stamp, str)
        assert delivered is None or isinstance(delivered, str)
        assert last_error is None or isinstance(last_error, str)
        return Alert(
            id=id_value,
            household_id=household,
            dedup_key=key,
            kind=kind,
            title=title,
            body=body,
            status=status,
            channel=channel,
            reason=reason,
            created_at=datetime.fromisoformat(stamp),
            delivered_at=(datetime.fromisoformat(delivered) if delivered else None),
            last_error=last_error,
        )
