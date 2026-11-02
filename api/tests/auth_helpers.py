"""Shared sign-in helper for API tests.

Creates a real session row for an explicit household id and puts the
cookie on the test client, so existing tests keep their household
strings while the session verification path stays fully real.
"""

import hashlib
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from strompilot.auth.store import AuthStore
from strompilot.main import SESSION_COOKIE, _memory_db


def sign_in(
    client: TestClient, household_id: str, email: str = "test@example.de"
) -> str:
    """Sign one test client in as one household, returning its email."""
    AuthStore(_memory_db())
    raw = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + timedelta(days=30)
    with sqlite3.connect(_memory_db()) as conn:
        with conn:
            conn.execute(
                "INSERT INTO auth_sessions"
                " (token_hash, email, household_id, expires_at, revoked_at)"
                " VALUES (?, ?, ?, ?, NULL)",
                (
                    hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                    email,
                    household_id,
                    expires.isoformat(),
                ),
            )
    client.cookies.set(SESSION_COOKIE, raw)
    return email
