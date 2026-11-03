"""Shared SQLite connector: WAL mode plus a busy timeout everywhere.

Every store and the thread database go through :func:`connect`, so a
background run can never wedge a reader with "database is locked".
"""

import sqlite3
from pathlib import Path

BUSY_TIMEOUT_MS = 30_000


def connect(path: Path | str) -> sqlite3.Connection:
    """Open one SQLite connection in WAL mode with a busy timeout."""
    if isinstance(path, Path):
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        path, timeout=BUSY_TIMEOUT_MS / 1000, check_same_thread=False
    )
    try:
        conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.Error:
        conn.close()
        raise
    return conn
