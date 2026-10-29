"""Tests for thread persistence through the SQLite checkpointer."""

from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from strompilot.agents.supervisor import build_graph
from tests.fakes import (
    ANALYST_JSON,
    CLEAN_NARRATION,
    FakeRouter,
    reply,
    stub_loader,
    thread_config,
)
from tests.test_graph import APPROVE


def make_router() -> FakeRouter:
    from strompilot.llm.client import SPARK_OPEN_MODEL, WONDER_MODEL

    return FakeRouter(
        {
            "supervisor": [reply("plan")],
            "analyst": [reply(ANALYST_JSON)],
            "explainer": [reply(CLEAN_NARRATION, SPARK_OPEN_MODEL)],
            "critic": [reply(APPROVE, WONDER_MODEL)],
        }
    )


def test_run_persists_thread_state(tmp_path: Path) -> None:
    with SqliteSaver.from_conn_string(str(tmp_path / "threads.db")) as saver:
        graph = build_graph(make_router(), stub_loader, checkpointer=saver)
        config = thread_config("t1")
        final = graph.invoke(
            {"request": "plane meinen Tag", "approval": "approved"}, config
        )
        assert final["published"] is True
        state = graph.get_state(config)
        assert state.values["published"] is True
        assert state.values["narration"] == CLEAN_NARRATION
        assert state.values["total_cost_eur"] == 0.60


def test_threads_survive_saver_reopen(tmp_path: Path) -> None:
    path = str(tmp_path / "threads.db")
    with SqliteSaver.from_conn_string(path) as saver:
        graph = build_graph(make_router(), stub_loader, checkpointer=saver)
        graph.invoke(
            {"request": "plane meinen Tag", "approval": "approved"},
            thread_config("t1"),
        )
    with SqliteSaver.from_conn_string(path) as reopened:
        graph = build_graph(make_router(), stub_loader, checkpointer=reopened)
        state = graph.get_state(thread_config("t1"))
        assert state.values["published"] is True
        assert state.values["schedule"][0]["start"] == "02:00"


def test_threads_stay_isolated(tmp_path: Path) -> None:
    with SqliteSaver.from_conn_string(str(tmp_path / "threads.db")) as saver:
        graph = build_graph(make_router(), stub_loader, checkpointer=saver)
        graph.invoke(
            {"request": "plane meinen Tag", "approval": "approved"},
            thread_config("t1"),
        )
        other = graph.get_state(thread_config("t2"))
        assert "published" not in other.values
