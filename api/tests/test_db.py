"""Tests for the shared SQLite connector (WAL mode plus busy timeout)."""

import sqlite3
from pathlib import Path

import pytest

from strompilot.auth.store import AuthStore
from strompilot.db import connect
from strompilot.flexalarm.store import AlertStore
from strompilot.memory.store import MemoryStore
from strompilot.metervision.store import MeterStore


def test_connect_enables_wal_and_busy_timeout(tmp_path: Path) -> None:
    """Every connection gets WAL mode and a generous busy timeout."""
    path = tmp_path / "probe.db"
    conn = connect(path)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 30_000
    finally:
        conn.close()


@pytest.mark.parametrize("store_cls", [AuthStore, AlertStore, MemoryStore, MeterStore])
def test_stores_create_wal_databases(tmp_path: Path, store_cls: object) -> None:
    """All four stores keep their files in WAL mode under concurrency."""
    path = tmp_path / "store.db"
    store_cls(path)  # type: ignore[operator]
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
