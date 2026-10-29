"""Tests for the approval HTTP flows."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.sqlite import SqliteSaver

from strompilot.agents.supervisor import build_graph
from strompilot.main import app, get_approval_graph
from tests.fakes import (
    ANALYST_JSON,
    CLEAN_NARRATION,
    FakeRouter,
    reply,
    stub_loader,
    thread_config,
)
from tests.test_graph import APPROVE


def scripted_router() -> FakeRouter:
    from strompilot.llm.client import SPARK_OPEN_MODEL, WONDER_MODEL

    return FakeRouter(
        {
            "supervisor": [reply("plan")],
            "analyst": [reply(ANALYST_JSON)],
            "explainer": [reply(CLEAN_NARRATION, SPARK_OPEN_MODEL)],
            "critic": [reply(APPROVE, WONDER_MODEL)],
        }
    )


def pause_thread(saver_path: Path, thread_id: str) -> None:
    """Run one thread to its approval pause through the library."""
    with SqliteSaver.from_conn_string(str(saver_path)) as saver:
        graph = build_graph(scripted_router(), stub_loader, checkpointer=saver)
        graph.invoke(
            {"request": "plane meinen Tag", "approval": "pending"},
            thread_config(thread_id),
        )


@pytest.fixture
def approval_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, Path]]:
    """Test client with the approval graph on a scratch database."""
    saver_path = tmp_path / "threads.db"
    monkeypatch.setenv("THREADS_DB", str(saver_path))

    def override() -> Any:
        with SqliteSaver.from_conn_string(str(saver_path)) as saver:
            yield build_graph(FakeRouter({}), stub_loader, checkpointer=saver)

    app.dependency_overrides[get_approval_graph] = override
    yield TestClient(app), saver_path
    app.dependency_overrides.clear()


def test_approve_flow_end_to_end(
    approval_setup: tuple[TestClient, Path],
) -> None:
    client, saver_path = approval_setup
    pause_thread(saver_path, "t1")
    paused = client.get("/approvals/threads/t1")
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    review = paused.json()["review"]
    assert review["schedule"][0]["device"] == "Waschmaschine"
    assert review["total_cost_eur"] == 0.60
    decided = client.post("/approvals/threads/t1/decide", json={"approved": True})
    assert decided.status_code == 200
    assert decided.json()["status"] == "published"
    assert decided.json()["published"] is True
    final = client.get("/approvals/threads/t1")
    assert final.json()["status"] == "published"


def test_reject_flow_end_to_end(
    approval_setup: tuple[TestClient, Path],
) -> None:
    client, saver_path = approval_setup
    pause_thread(saver_path, "t1")
    decided = client.post("/approvals/threads/t1/decide", json={"approved": False})
    assert decided.status_code == 200
    assert decided.json()["status"] == "blocked"
    assert "rejected" in decided.json()["error"]
    final = client.get("/approvals/threads/t1")
    assert final.json()["status"] == "blocked"


def test_finished_thread_without_plan_reports_done(
    approval_setup: tuple[TestClient, Path],
) -> None:
    from langgraph.checkpoint.sqlite import SqliteSaver

    from strompilot.agents.supervisor import build_graph

    client, saver_path = approval_setup
    router = FakeRouter({"supervisor": [reply("other")]})
    with SqliteSaver.from_conn_string(str(saver_path)) as saver:
        graph = build_graph(router, stub_loader, checkpointer=saver)
        graph.invoke({"request": "erzaehl einen Witz"}, thread_config("t9"))
    response = client.get("/approvals/threads/t9")
    assert response.status_code == 200
    assert response.json()["status"] == "done"


def test_unknown_thread_returns_404(
    approval_setup: tuple[TestClient, Path],
) -> None:
    client, _ = approval_setup
    assert client.get("/approvals/threads/nope").status_code == 404
    assert (
        client.post(
            "/approvals/threads/nope/decide", json={"approved": True}
        ).status_code
        == 404
    )


def test_decide_on_settled_thread_returns_409(
    approval_setup: tuple[TestClient, Path],
) -> None:
    client, saver_path = approval_setup
    pause_thread(saver_path, "t1")
    first = client.post("/approvals/threads/t1/decide", json={"approved": True})
    assert first.status_code == 200
    second = client.post("/approvals/threads/t1/decide", json={"approved": True})
    assert second.status_code == 409


def test_missing_keys_returns_500(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("THREADS_DB", str(tmp_path / "threads.db"))
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    client = TestClient(app)
    assert client.get("/approvals/threads/t1").status_code == 500
