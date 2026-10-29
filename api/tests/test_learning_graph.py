"""Tests for learned windows inside graph runs."""

from pathlib import Path

from strompilot.agents.supervisor import build_graph
from strompilot.llm.client import SPARK_OPEN_MODEL
from strompilot.memory.store import MemoryStore
from tests.fakes import ANALYST_JSON, CLEAN_NARRATION, FakeRouter, reply, stub_loader
from tests.test_graph import APPROVE, happy_router


def memory_with_learned(tmp_path: Path) -> MemoryStore:
    """Memory where the washer learned to start five hours later."""
    memory = MemoryStore(tmp_path / "memory.db")
    memory.set_preference(
        "h1",
        "learned_windows",
        {"Waschmaschine": {"earliest_shift_h": 5, "latest_shift_h": 0}},
    )
    return memory


def test_learned_windows_shift_the_schedule(tmp_path: Path) -> None:
    router = FakeRouter(
        {
            "supervisor": [reply("plan")],
            "analyst": [reply(ANALYST_JSON)],
            "explainer": [reply(CLEAN_NARRATION, SPARK_OPEN_MODEL)] * 2,
            "critic": [reply(APPROVE)],
        }
    )
    graph = build_graph(router, stub_loader, memory=memory_with_learned(tmp_path))
    final = graph.invoke(
        {"request": "plane meinen Tag", "approval": "approved", "household_id": "h1"}
    )
    assert final["schedule"][0]["start"] == "12:00"
    assert final["schedule"][0]["end"] == "14:00"


def test_no_memory_keeps_baseline(tmp_path: Path) -> None:
    graph = build_graph(happy_router(), stub_loader)
    final = graph.invoke(
        {"request": "plane meinen Tag", "approval": "approved", "household_id": "h1"}
    )
    assert final["schedule"][0]["start"] == "02:00"


def test_memory_without_learned_pref_keeps_baseline(tmp_path: Path) -> None:
    memory = MemoryStore(tmp_path / "memory.db")
    memory.set_preference("h1", "devices", [])
    graph = build_graph(happy_router(), stub_loader, memory=memory)
    final = graph.invoke(
        {"request": "plane meinen Tag", "approval": "approved", "household_id": "h1"}
    )
    assert final["schedule"][0]["start"] == "02:00"


def test_malformed_learned_pref_keeps_baseline(tmp_path: Path) -> None:
    memory = MemoryStore(tmp_path / "memory.db")
    memory.set_preference("h1", "learned_windows", "later please")
    graph = build_graph(happy_router(), stub_loader, memory=memory)
    final = graph.invoke(
        {"request": "plane meinen Tag", "approval": "approved", "household_id": "h1"}
    )
    assert final["schedule"][0]["start"] == "02:00"


def test_other_household_keeps_baseline(tmp_path: Path) -> None:
    graph = build_graph(
        happy_router(), stub_loader, memory=memory_with_learned(tmp_path)
    )
    final = graph.invoke(
        {"request": "plane meinen Tag", "approval": "approved", "household_id": "h2"}
    )
    assert final["schedule"][0]["start"] == "02:00"
