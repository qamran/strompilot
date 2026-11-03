"""Tests for the plan trigger, plan detail, and trace stream."""

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from strompilot.llm.client import WONDER_MODEL
from strompilot.main import (
    PlanRunner,
    _run_plan_to_pause,
    app,
    get_plan_runner,
    read_run_error,
)
from strompilot.memory.store import MemoryStore
from tests.fakes import (
    FakeRouter,
    FakeWallbox,
    idle_wallbox_status,
    reply,
    stub_loader,
)
from tests.test_graph import APPROVE

from .auth_helpers import sign_in

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
    """Signed-in test client with a scripted plan runner."""
    monkeypatch.setenv("THREADS_DB", str(tmp_path / "threads.db"))
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    runner = scripted_runner(tmp_path)
    app.dependency_overrides[get_plan_runner] = lambda: runner
    client = TestClient(app)
    sign_in(client, "h1")
    yield client
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


def test_plan_detail_reports_day_and_price_source(plan_setup: TestClient) -> None:
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
    assert payload["plan_day"] == "2026-06-01"
    assert payload["price_source"] == "test"
    assert payload["price_stale"] is False
    assert payload["attribution"]["schedule"] == "deterministic"
    assert payload["attribution"]["verdict"] == WONDER_MODEL
    assert any(" · " in event for event in payload["audit"])
    assert payload["prices"][2] == {
        "hour": 2,
        "price_ct_kwh": 15.0,
        "source": "test",
        "start_utc": None,
    }


def test_plan_unknown_thread_is_404(plan_setup: TestClient) -> None:
    response = plan_setup.get("/plan/does-not-exist")
    assert response.status_code == 404


def test_trace_unknown_thread_is_404(plan_setup: TestClient) -> None:
    response = plan_setup.get("/plan/does-not-exist/trace")
    assert response.status_code == 404


def test_plan_broken_store_is_503_with_retry_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    garbage = tmp_path / "threads.db"
    garbage.write_bytes(b"not a database")
    monkeypatch.setenv("THREADS_DB", str(garbage))
    client = TestClient(app, raise_server_exceptions=False)
    sign_in(client, "h1")
    with caplog.at_level("ERROR", logger="strompilot.main"):
        response = client.get("/plan/does-not-exist")
    assert response.status_code == 503
    assert "retry" in response.json()["detail"].lower()
    assert any("plan read" in message for message in caplog.messages)


def test_trace_broken_store_is_503_with_retry_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    garbage = tmp_path / "threads.db"
    garbage.write_bytes(b"not a database")
    monkeypatch.setenv("THREADS_DB", str(garbage))
    client = TestClient(app, raise_server_exceptions=False)
    sign_in(client, "h1")
    response = client.get("/plan/does-not-exist/trace")
    assert response.status_code == 503
    assert "retry" in response.json()["detail"].lower()


def test_plan_reads_ignore_runner_and_keys(
    plan_setup: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reads never build the model router, so missing keys cannot break them."""
    created = plan_setup.post("/plan", json={"household_id": "h1", "text": "waschen"})
    thread_id = created.json()["thread_id"]
    decided = plan_setup.post(
        f"/approvals/threads/{thread_id}/decide", json={"approved": True}
    )
    assert decided.status_code == 200

    def boom() -> object:
        raise AssertionError("reads must not touch the plan runner")

    app.dependency_overrides[get_plan_runner] = boom
    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    try:
        detail = plan_setup.get(f"/plan/{thread_id}")
        assert detail.status_code == 200
        assert detail.json()["status"] == "published"
        trace = plan_setup.get(f"/plan/{thread_id}/trace")
        assert trace.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_just_started_thread_reads_running(
    plan_setup: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A recorded start without a checkpoint yet reads as running, not 404."""
    import strompilot.main as main_module

    threads_db = Path(main_module._threads_db())
    main_module.record_run_started(threads_db, "t-fresh", "h1")
    response = plan_setup.get("/plan/t-fresh")
    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_stale_thread_reads_blocked_with_retry(
    plan_setup: TestClient,
) -> None:
    """A run older than the timeout without progress reads back as blocked."""
    import sqlite3

    import strompilot.main as main_module

    threads_db = Path(main_module._threads_db())
    main_module.record_run_started(threads_db, "t-stale", "h1")
    with sqlite3.connect(threads_db) as conn:
        with conn:
            conn.execute(
                "UPDATE runs SET started_at = ? WHERE thread_id = ?",
                ("2020-01-01T00:00:00+00:00", "t-stale"),
            )
    response = plan_setup.get("/plan/t-stale")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "blocked"
    assert "retry" in payload["error"].lower()


def test_trace_stream_always_ends_with_done(plan_setup: TestClient) -> None:
    created = plan_setup.post("/plan", json={"household_id": "h1", "text": "waschen"})
    thread_id = created.json()["thread_id"]
    plan_setup.post(f"/approvals/threads/{thread_id}/decide", json={"approved": True})
    trace = plan_setup.get(f"/plan/{thread_id}/trace")
    assert trace.status_code == 200
    lines = [line for line in trace.text.splitlines() if line.startswith("data: ")]
    assert lines[-1] == "data: [done]"


def test_trace_events_yield_done_on_timeout(tmp_path: Path) -> None:
    """Even a thread that never settles closes the stream with [done]."""
    from strompilot.main import _trace_events

    events = list(_trace_events("t-never", tmp_path / "threads.db", 2, 0))
    assert events[-1] == "data: [done]\n\n"


def test_trace_stream_stays_open_for_slow_runs() -> None:
    """The live trace outlasts a five-minute run before timing out."""
    import inspect

    from strompilot.main import _trace_events

    params = inspect.signature(_trace_events).parameters
    polls = params["max_polls"].default
    interval = params["interval"].default
    assert polls * interval >= 300


def test_background_crash_is_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    threads_db = tmp_path / "threads.db"
    router = FakeRouter(
        {
            "supervisor": [reply("plan")],
            "analyst": [reply("not json"), reply("not json")],
        }
    )
    runner = PlanRunner(
        router=router,
        loader_for=lambda day: stub_loader,
        threads_db=threads_db,
        memory=MemoryStore(tmp_path / "memory.db"),
        wallbox=FakeWallbox([]),
    )
    _run_plan_to_pause(runner, "t1", "h1", "plane", date(2026, 6, 1))
    recorded = read_run_error(threads_db, "t1")
    assert recorded is not None and "extraction failed" in recorded


def test_plan_speaks_english_when_asked(plan_setup: TestClient) -> None:
    created = plan_setup.post(
        "/plan",
        json={
            "household_id": "h1",
            "text": "run the washer at night",
            "plan_day": "2026-06-01",
            "lang": "en",
        },
    )
    assert created.status_code == 202
    detail = plan_setup.get(f"/plan/{created.json()['thread_id']}")
    payload = detail.json()
    assert payload["status"] == "paused"
    assert payload["schedule"][0]["reason"].startswith("Cheapest 2h between")
    claims = " ".join(citation["claim"] for citation in payload["citations"])
    assert "runs 02:00 to 04:00" in claims


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


def test_crashed_run_reads_back_as_blocked_with_error(
    plan_setup: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A crashing run stays a readable blocked plan, not a 500."""
    import strompilot.main as main_module

    def boom(*args: object, **kwargs: object) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr(main_module, "build_graph", boom)
    created = plan_setup.post("/plan", json={"household_id": "h1", "text": "waschen"})
    thread_id = created.json()["thread_id"]
    detail = plan_setup.get(f"/plan/{thread_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["status"] == "blocked"
    assert "boom" in payload["error"]
    assert "Traceback" in caplog.text
    assert thread_id in caplog.text


def test_plan_text_too_long_rejected(plan_setup: TestClient) -> None:
    response = plan_setup.post("/plan", json={"household_id": "h1", "text": "x" * 2001})
    assert response.status_code == 422


def test_blank_input_rejected(plan_setup: TestClient) -> None:
    assert (
        plan_setup.post("/plan", json={"household_id": " ", "text": "x"}).status_code
        == 422
    )
    assert (
        plan_setup.post("/plan", json={"household_id": "h1", "text": "  "}).status_code
        == 422
    )
