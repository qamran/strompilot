"""Tests for the auth store: magic-link tokens plus sessions."""

import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from strompilot.auth.models import AuthError
from strompilot.auth.store import AuthStore


def test_magic_token_verifies_once_then_expires(tmp_path: Path) -> None:
    """A magic token is single-use: first verify wins, second fails."""
    store = AuthStore(tmp_path / "memory.db")
    raw = store.issue_token("lena@example.de")
    assert store.consume_token(raw) == "lena@example.de"
    with pytest.raises(AuthError):
        store.consume_token(raw)


def test_concurrent_redeem_wins_once(tmp_path: Path) -> None:
    """Eight threads racing one token produce exactly one winner."""
    store = AuthStore(tmp_path / "memory.db")
    raw = store.issue_token("lena@example.de")
    barrier = threading.Barrier(8)
    wins: list[str] = []
    lock = threading.Lock()

    def attempt() -> None:
        barrier.wait(timeout=10)
        try:
            email = store.consume_token(raw)
        except AuthError:
            return
        with lock:
            wins.append(email)

    threads = [threading.Thread(target=attempt) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert wins == ["lena@example.de"]


def test_expired_magic_token_fails(tmp_path: Path) -> None:
    """A token past its TTL is rejected."""
    store = AuthStore(tmp_path / "memory.db")
    raw = store.issue_token("lena@example.de", ttl=timedelta(seconds=-1))
    with pytest.raises(AuthError):
        store.consume_token(raw)


def test_unknown_magic_token_fails(tmp_path: Path) -> None:
    """A token that was never issued is rejected."""
    store = AuthStore(tmp_path / "memory.db")
    with pytest.raises(AuthError):
        store.consume_token("never-issued-token")


def test_session_loads_until_revoked_or_expired(tmp_path: Path) -> None:
    """A session loads while valid and dies on revoke or expiry."""
    store = AuthStore(tmp_path / "memory.db")
    raw = store.create_session("lena@example.de")
    session = store.load_session(raw)
    assert session.email == "lena@example.de"
    assert session.household_id == AuthStore.household_for_email("lena@example.de")
    assert session.expires_at > datetime.now(UTC)
    assert store.revoke_session(raw) is True
    with pytest.raises(AuthError):
        store.load_session(raw)
    stale = store.create_session("lena@example.de", ttl=timedelta(seconds=-1))
    with pytest.raises(AuthError):
        store.load_session(stale)


def test_token_carries_sign_in_consent(tmp_path: Path) -> None:
    """Tokens remember the sign-in consent choice, defaulting to no."""
    store = AuthStore(tmp_path / "memory.db")
    agreed = store.issue_token("lena@example.de", consent_agreed=True)
    assert store.read_token_consent(agreed) is True
    plain = store.issue_token("lena@example.de")
    assert store.read_token_consent(plain) is False


def test_old_token_table_gains_consent_column(tmp_path: Path) -> None:
    """Opening a pre-consent database migrates the tokens table."""
    import sqlite3

    path = tmp_path / "memory.db"
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE auth_tokens (token_hash TEXT PRIMARY KEY,"
            " email TEXT NOT NULL, expires_at TEXT NOT NULL,"
            " used_at TEXT)"
        )
    store = AuthStore(path)
    raw = store.issue_token("lena@example.de", consent_agreed=True)
    assert store.read_token_consent(raw) is True


def test_household_id_is_stable_and_email_scoped(tmp_path: Path) -> None:
    """The same email always maps to the same household id."""
    first = AuthStore.household_for_email("Lena@Example.de")
    second = AuthStore.household_for_email("lena@example.de")
    other = AuthStore.household_for_email("max@example.de")
    assert first == second
    assert first != other
    assert first.startswith("hh_")
