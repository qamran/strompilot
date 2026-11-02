"""Auth store: single-use magic tokens plus revocable sessions."""

import hashlib
import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .models import AuthError, Session

_SCHEMA = """
CREATE TABLE IF NOT EXISTS auth_tokens (
    token_hash TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT
);
CREATE TABLE IF NOT EXISTS auth_sessions (
    token_hash TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    household_id TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT
);
"""

DEFAULT_TOKEN_TTL = timedelta(minutes=15)
DEFAULT_SESSION_TTL = timedelta(days=30)


def _digest(raw: str) -> str:
    """Hash one raw token for storage, so leaks stay useless."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class AuthStore:
    """Magic-link tokens and sessions in the household database."""

    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as conn:
            conn.executescript(_SCHEMA)

    @staticmethod
    def household_for_email(email: str) -> str:
        """Map one email to its stable household id."""
        normalized = email.strip().lower()
        if not normalized:
            raise AuthError("email must not be blank")
        digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
        return f"hh_{digest}"

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Yield one committed-plus-closed connection per operation."""
        conn = sqlite3.connect(self._path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def issue_token(self, email: str, ttl: timedelta = DEFAULT_TOKEN_TTL) -> str:
        """Create one single-use magic token, returning the raw value once."""
        normalized = email.strip().lower()
        if not normalized:
            raise AuthError("email must not be blank")
        raw = secrets.token_urlsafe(32)
        expires = datetime.now(UTC) + ttl
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO auth_tokens (token_hash, email, expires_at, used_at)"
                " VALUES (?, ?, ?, NULL)",
                (_digest(raw), normalized, expires.isoformat()),
            )
        return raw

    def consume_token(self, raw: str) -> str:
        """Redeem one magic token for its email, failing on reuse or expiry."""
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT email, expires_at, used_at FROM auth_tokens"
                " WHERE token_hash = ?",
                (_digest(raw),),
            ).fetchone()
            if row is None or row[2] is not None or row[1] <= now:
                raise AuthError("magic link is invalid or expired")
            conn.execute(
                "UPDATE auth_tokens SET used_at = ? WHERE token_hash = ?",
                (now, _digest(raw)),
            )
        email = row[0]
        assert isinstance(email, str)
        return email

    def create_session(self, email: str, ttl: timedelta = DEFAULT_SESSION_TTL) -> str:
        """Create one session, returning the raw cookie value once."""
        normalized = email.strip().lower()
        if not normalized:
            raise AuthError("email must not be blank")
        raw = secrets.token_urlsafe(32)
        expires = datetime.now(UTC) + ttl
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO auth_sessions"
                " (token_hash, email, household_id, expires_at, revoked_at)"
                " VALUES (?, ?, ?, ?, NULL)",
                (
                    _digest(raw),
                    normalized,
                    self.household_for_email(normalized),
                    expires.isoformat(),
                ),
            )
        return raw

    def load_session(self, raw: str) -> Session:
        """Load one session, failing on revoke or expiry."""
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT email, household_id, expires_at, revoked_at"
                " FROM auth_sessions WHERE token_hash = ?",
                (_digest(raw),),
            ).fetchone()
        if row is None or row[3] is not None or row[2] <= now:
            raise AuthError("session is invalid or expired")
        email, household_id, expires_at = row[0], row[1], row[2]
        assert isinstance(email, str)
        assert isinstance(household_id, str)
        assert isinstance(expires_at, str)
        return Session(
            email=email,
            household_id=household_id,
            expires_at=datetime.fromisoformat(expires_at),
        )

    def revoke_session(self, raw: str) -> bool:
        """Revoke one session, reporting whether it existed and was live."""
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE auth_sessions SET revoked_at = ?"
                " WHERE token_hash = ? AND revoked_at IS NULL",
                (now, _digest(raw)),
            )
        return cursor.rowcount > 0
