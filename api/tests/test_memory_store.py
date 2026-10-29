"""Tests for the household memory store."""

from pathlib import Path

import pytest

from strompilot.memory.models import MemoryError
from strompilot.memory.store import MemoryStore


def test_preference_round_trip(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    saved = store.set_preference("h1", "quiet_hours", {"start": "22:00"})
    assert saved.key == "quiet_hours"
    assert saved.value == {"start": "22:00"}
    assert store.get_preference("h1", "quiet_hours") == {"start": "22:00"}
    assert store.get_preference("h1", "missing") is None


def test_preference_overwrite_and_delete(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    store.set_preference("h1", "k", 1)
    store.set_preference("h1", "k", 2)
    assert store.get_preference("h1", "k") == 2
    assert store.delete_preference("h1", "k") is True
    assert store.delete_preference("h1", "k") is False
    assert store.get_preference("h1", "k") is None


def test_preferences_isolate_households(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    store.set_preference("h1", "k", "a")
    store.set_preference("h2", "k", "b")
    assert store.get_preference("h1", "k") == "a"
    assert store.get_preference("h2", "k") == "b"
    assert [pref.key for pref in store.list_preferences("h1")] == ["k"]


def test_episodes_list_newest_first_with_filters(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    first = store.add_episode("h1", "plan", "erster Plan")
    store.add_episode("h1", "feedback", "mag Abende")
    store.add_episode("h1", "plan", "zweiter Plan")
    episodes = store.list_episodes("h1")
    assert [episode.text for episode in episodes] == [
        "zweiter Plan",
        "mag Abende",
        "erster Plan",
    ]
    assert episodes[0].id > first.id
    plans = store.list_episodes("h1", kind="plan")
    assert [episode.text for episode in plans] == ["zweiter Plan", "erster Plan"]
    assert len(store.list_episodes("h1", limit=2)) == 2
    assert store.list_episodes("h2") == []


def test_search_matches_text_and_respects_households(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    store.add_episode("h1", "note", "Waschmaschine nachts laufen lassen")
    store.add_episode("h1", "note", "Spuelmaschine abends")
    store.add_episode("h2", "note", "Waschmaschine mittags")
    found = store.search_episodes("h1", "waschmaschine")
    assert [episode.text for episode in found] == ["Waschmaschine nachts laufen lassen"]
    assert store.search_episodes("h1", "100% _ sicher") == []


def test_episode_delete_scoped_to_household(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    episode = store.add_episode("h1", "note", "text")
    assert store.delete_episode("h2", episode.id) is False
    assert store.delete_episode("h1", episode.id) is True
    assert store.delete_episode("h1", episode.id) is False


def test_data_survives_reopen(tmp_path: Path) -> None:
    path = tmp_path / "memory.db"
    store = MemoryStore(path)
    store.set_preference("h1", "k", [1, 2])
    store.add_episode("h1", "plan", "alter Plan")
    reopened = MemoryStore(path)
    assert reopened.get_preference("h1", "k") == [1, 2]
    assert [episode.text for episode in reopened.list_episodes("h1")] == ["alter Plan"]


def test_forget_wipes_one_household_only(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    store.set_preference("h1", "k", "a")
    store.add_episode("h1", "note", "vergiss mich")
    store.set_preference("h2", "k", "b")
    store.forget_household("h1")
    assert store.get_preference("h1", "k") is None
    assert store.list_episodes("h1") == []
    assert store.get_preference("h2", "k") == "b"


def test_empty_ids_rejected(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    with pytest.raises(MemoryError):
        store.set_preference("", "k", "v")
    with pytest.raises(MemoryError):
        store.set_preference("h1", "  ", "v")
    with pytest.raises(MemoryError):
        store.add_episode("h1", "note", "   ")


def test_blank_search_rejected(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    store.add_episode("h1", "note", "text")
    with pytest.raises(MemoryError):
        store.search_episodes("h1", "   ")


def test_identifiers_normalized(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    store.set_preference("  h1  ", "  k  ", "v")
    assert store.get_preference("h1", "k") == "v"
    assert store.get_preference("  h1  ", "  k  ") == "v"
    episode = store.add_episode(" h1 ", " note ", "  text  ")
    assert episode.household_id == "h1"
    assert episode.kind == "note"
    assert episode.text == "text"
    assert [found.text for found in store.search_episodes("h1", "text")] == ["text"]


def test_connections_close_after_use(tmp_path: Path) -> None:
    import sqlite3

    store = MemoryStore(tmp_path / "memory.db")
    with store._connect() as conn:
        conn.execute("SELECT 1")
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")
