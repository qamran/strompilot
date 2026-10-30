"""Meter reading store: proposed readings plus confirmed ones."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .models import MeterError, MeterReading

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meter_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    household_id TEXT NOT NULL,
    value_kwh REAL NOT NULL,
    read_at TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence TEXT NOT NULL,
    sam_box TEXT,
    photo_path TEXT NOT NULL,
    serial TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_readings_household
    ON meter_readings (household_id, id);
"""


def _require(label: str, value: str) -> str:
    """Normalize identifiers, rejecting blank ones loudly."""
    stripped = value.strip()
    if not stripped:
        raise MeterError(f"{label} must not be blank")
    return stripped


class MeterStore:
    """Household-scoped readings; only confirmed ones feed the math."""

    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as conn:
            conn.executescript(_SCHEMA)
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(meter_readings)")
            }
            if "serial" not in columns:
                conn.execute("ALTER TABLE meter_readings ADD COLUMN serial TEXT")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Yield one committed-plus-closed connection per operation."""
        conn = sqlite3.connect(self._path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def propose(
        self,
        household_id: str,
        value_kwh: float,
        read_at: datetime,
        confidence: str,
        sam_box: str | None,
        photo_path: str,
        serial: str | None = None,
    ) -> MeterReading:
        """Store one vision reading awaiting human confirmation."""
        household_id = _require("household_id", household_id)
        if value_kwh < 0:
            raise MeterError("value_kwh must not be negative")
        stamp = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO meter_readings (household_id, value_kwh, read_at,"
                " status, confidence, sam_box, photo_path, serial, created_at)"
                " VALUES (?, ?, ?, 'proposed', ?, ?, ?, ?, ?)",
                (
                    household_id,
                    value_kwh,
                    read_at.isoformat(),
                    confidence,
                    sam_box,
                    photo_path,
                    serial,
                    stamp,
                ),
            )
            reading_id = cursor.lastrowid or 0
        return MeterReading(
            id=reading_id,
            household_id=household_id,
            value_kwh=value_kwh,
            read_at=read_at,
            status="proposed",
            confidence=confidence,
            sam_box=sam_box,
            photo_path=photo_path,
            serial=serial,
            created_at=datetime.fromisoformat(stamp),
        )

    def confirm(
        self, household_id: str, reading_id: int, corrected_kwh: float | None
    ) -> MeterReading:
        """Confirm one reading, optionally with a corrected value."""
        household_id = _require("household_id", household_id)
        if corrected_kwh is not None and corrected_kwh < 0:
            raise MeterError("value_kwh must not be negative")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, household_id, value_kwh, read_at, status,"
                " confidence, sam_box, photo_path, serial, created_at"
                " FROM meter_readings WHERE household_id = ? AND id = ?",
                (household_id, reading_id),
            ).fetchone()
            if row is None:
                raise MeterError(f"reading {reading_id} not found")
            value = corrected_kwh if corrected_kwh is not None else float(row[2])
            conn.execute(
                "UPDATE meter_readings SET value_kwh = ?, status = 'confirmed'"
                " WHERE id = ?",
                (value, reading_id),
            )
        return self._to_reading(
            (
                row[0],
                row[1],
                value,
                row[3],
                "confirmed",
                row[5],
                row[6],
                row[7],
                row[8],
                row[9],
            )
        )

    def get(self, household_id: str, reading_id: int) -> MeterReading | None:
        """Return one reading of one household, or None when missing."""
        household_id = _require("household_id", household_id)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, household_id, value_kwh, read_at, status,"
                " confidence, sam_box, photo_path, serial, created_at"
                " FROM meter_readings WHERE household_id = ? AND id = ?",
                (household_id, reading_id),
            ).fetchone()
        return self._to_reading(row) if row else None

    def list_readings(self, household_id: str, limit: int = 50) -> list[MeterReading]:
        """List one household's readings, oldest first."""
        household_id = _require("household_id", household_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, household_id, value_kwh, read_at, status,"
                " confidence, sam_box, photo_path, serial, created_at"
                " FROM meter_readings WHERE household_id = ?"
                " ORDER BY id ASC LIMIT ?",
                (household_id, limit),
            ).fetchall()
        return [self._to_reading(row) for row in rows]

    def confirmed(self, household_id: str) -> list[MeterReading]:
        """List one household's confirmed readings, oldest first.

        This is the only path from storage into calibration math:
        proposed readings can never leak in.
        """
        household_id = _require("household_id", household_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, household_id, value_kwh, read_at, status,"
                " confidence, sam_box, photo_path, serial, created_at"
                " FROM meter_readings WHERE household_id = ?"
                " AND status = 'confirmed' ORDER BY read_at ASC, id ASC",
                (household_id,),
            ).fetchall()
        return [self._to_reading(row) for row in rows]

    @staticmethod
    def _to_reading(row: tuple[object, ...]) -> MeterReading:
        """Map one database row to a MeterReading."""
        (
            id_value,
            household,
            value,
            read,
            status,
            confidence,
            box,
            photo,
            serial,
            stamp,
        ) = row
        assert isinstance(id_value, int)
        assert isinstance(household, str)
        assert isinstance(value, float)
        assert isinstance(read, str)
        assert isinstance(status, str)
        assert isinstance(confidence, str)
        assert box is None or isinstance(box, str)
        assert isinstance(photo, str)
        assert serial is None or isinstance(serial, str)
        assert isinstance(stamp, str)
        return MeterReading(
            id=id_value,
            household_id=household,
            value_kwh=value,
            read_at=datetime.fromisoformat(read),
            status=status,
            confidence=confidence,
            sam_box=box,
            photo_path=photo,
            serial=serial,
            created_at=datetime.fromisoformat(stamp),
        )
