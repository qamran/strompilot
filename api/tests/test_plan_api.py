"""Tests for the plan trigger, plan detail, and trace stream."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from strompilot.main import PlanRunner, app, get_plan_runner
from strompilot.memory.store import MemoryStore
from tests.fakes import (
    FakeRouter,
    FakeWallbox,
    idle_wallbox_status,
    reply,
    stub_loader,
)
from tests.test_graph import APPROVE

ANALYST_JSON = """{"facts": ["billig nachts"],
"devices": [
{"device": "Waschmaschine", "power_kw": 2.0, "duration_h": 2.0,
"earliest": "00:00", "latest": "23:00", "shiftable": true}
],
"notes": ""}"""

NARRATION = (
    "Die Waschmaschine läuft von 02:00 bis 04:00 Uhr und kostet 0,60 €. "
    "Die Gesamtkosten betragen 0,60 €."
)


def scripted_runner(tmp_path: Path) -> PlanRunner:
    """Plan runner on fakes with scratch databases."""
    from strompilot.llm.client import SPARK_OPEN_MODEL, WONDER_MODEL

    router = FakeRouter(
        {
            "supervisor": [reply("plan")] * 4,
            "analyst": [reply(ANALYST_JSON)] * 4,
            "explainer": [reply(NARRATION, SPARK_OPEN_MODEL)] * 4,
            "critic": [reply(APPROVE, WONDER_MODEL)] * 4,
        }
    )
    return PlanRunner(
        router=router,
        loader_for=lambda day: stub_loader,
        threads_db=tmp_path / "threads.db",
        memory=MemoryStore(tmp_path / "memory.db"),
        wallbox=FakeWallbox([idle_wallbox_status()] * 4),
    )


@pytest.fixture
def plan_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Test client with a scripted plan runner."""
    monkeypatch.setenv("THREADS_DB", str(tmp_path / "threads.db"))
    runner = scripted_runner(tmp_path)
    app.dependency_overrides[get_plan_runner] = lambda: runner
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_plan_runs_to_pause(plan_setup: TestClient) -> None:
    created = plan_setup.post(
        "/plan",
        json={
            "household_id": "h1",
            "text": "Waschmaschine nachts laufen lassen",
            "plan_day": "2026-06-01",
        },
    )
    assert created.status_code == 202
    thread_id = created.json()["thread_id"]
    detail = plan_setup.get(f"/plan/{thread_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["status"] == "paused"
    assert payload["schedule"][0]["device"] == "Waschmaschine"
    assert payload["total_cost_eur"] == 0.60
    assert "Waschmaschine" in payload["narration"]


def test_approve_then_plan_publishes(plan_setup: TestClient) -> None:
    created = plan_setup.post("/plan", json={"household_id": "h1", "text": "waschen"})
    thread_id = created.json()["thread_id"]
    decided = plan_setup.post(
        f"/approvals/threads/{thread_id}/decide", json={"approved": True}
    )
    assert decided.status_code == 200
    detail = plan_setup.get(f"/plan/{thread_id}")
    assert detail.json()["status"] == "published"


def test_trace_streams_audit_then_closes(plan_setup: TestClient) -> None:
    created = plan_setup.post("/plan", json={"household_id": "h1", "text": "waschen"})
    thread_id = created.json()["thread_id"]
    plan_setup.post(f"/approvals/threads/{thread_id}/decide", json={"approved": True})
    trace = plan_setup.get(f"/plan/{thread_id}/trace")
    assert trace.status_code == 200
    assert "text/event-stream" in trace.headers["content-type"]
    lines = [line for line in trace.text.splitlines() if line.startswith("data: ")]
    assert len(lines) >= 5
    assert any("publish" in line for line in lines)


def test_unknown_thread_returns_404(plan_setup: TestClient) -> None:
    assert plan_setup.get("/plan/nope").status_code == 404
    assert plan_setup.get("/plan/nope/trace").status_code == 404


def test_blank_input_rejected(plan_setup: TestClient) -> None:
    assert (
        plan_setup.post("/plan", json={"household_id": " ", "text": "x"}).status_code
        == 422
    )
    assert (
        plan_setup.post("/plan", json={"household_id": "h1", "text": "  "}).status_code
        == 422
    )
