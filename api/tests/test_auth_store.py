"""Tests for the auth store: magic-link tokens plus sessions."""

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


def test_household_id_is_stable_and_email_scoped(tmp_path: Path) -> None:
    """The same email always maps to the same household id."""
    first = AuthStore.household_for_email("Lena@Example.de")
    second = AuthStore.household_for_email("lena@example.de")
    other = AuthStore.household_for_email("max@example.de")
    assert first == second
    assert first != other
    assert first.startswith("hh_")
