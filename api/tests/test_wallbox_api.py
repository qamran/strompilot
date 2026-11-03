"""Tests for the wallbox HTTP API."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from strompilot.main import app, get_wallbox_client
from strompilot.wallbox.client import WallboxError
from tests.auth_helpers import sign_in
from tests.fakes import FakeWallbox, idle_wallbox_status


@pytest.fixture
def wallbox_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, FakeWallbox]]:
    """Signed-in test client with a scripted wallbox driver."""
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    driver = FakeWallbox([idle_wallbox_status()])
    app.dependency_overrides[get_wallbox_client] = lambda: driver
    client = TestClient(app)
    sign_in(client, "h1")
    yield client, driver
    app.dependency_overrides.clear()


def test_status_requires_a_session(
    wallbox_setup: tuple[TestClient, FakeWallbox],
) -> None:
    client, driver = wallbox_setup
    client.cookies.clear()
    assert client.get("/wallbox/status").status_code == 401
    assert driver.status_calls == 0


def test_program_requires_a_session(
    wallbox_setup: tuple[TestClient, FakeWallbox],
) -> None:
    client, driver = wallbox_setup
    client.cookies.clear()
    response = client.post(
        "/wallbox/program",
        json={"day": "2026-06-01", "start": "02:00", "end": "04:00", "max_kw": 11.0},
    )
    assert response.status_code == 401
    assert driver.programs == []


def test_status_reports_live_state(
    wallbox_setup: tuple[TestClient, FakeWallbox],
) -> None:
    client, driver = wallbox_setup
    response = client.get("/wallbox/status")
    assert response.status_code == 200
    assert response.json()["plugged"] is True
    assert driver.status_calls == 1


def test_program_behind_gates(wallbox_setup: tuple[TestClient, FakeWallbox]) -> None:
    client, driver = wallbox_setup
    response = client.post(
        "/wallbox/program",
        json={"day": "2026-06-01", "start": "02:00", "end": "04:00", "max_kw": 11.0},
    )
    assert response.status_code == 200
    assert driver.programs == [
        ("2026-06-01T02:00:00+02:00", "2026-06-01T04:00:00+02:00", 11.0)
    ]


def test_program_blocks_over_power(
    wallbox_setup: tuple[TestClient, FakeWallbox],
) -> None:
    client, driver = wallbox_setup
    response = client.post(
        "/wallbox/program",
        json={"day": "2026-06-01", "start": "02:00", "end": "04:00", "max_kw": 30.0},
    )
    assert response.status_code == 422
    assert driver.programs == []


def test_program_rejects_bad_clock(
    wallbox_setup: tuple[TestClient, FakeWallbox],
) -> None:
    client, _ = wallbox_setup
    response = client.post(
        "/wallbox/program",
        json={"day": "2026-06-01", "start": "soon", "end": "04:00", "max_kw": 11.0},
    )
    assert response.status_code == 422


def test_driver_error_returns_502(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Failing:
        def status(self):  # type: ignore[no-untyped-def]
            raise WallboxError("sim down")

        def program(self, start_iso: str, end_iso: str, max_kw: float):  # type: ignore[no-untyped-def]
            del start_iso, end_iso, max_kw
            raise WallboxError("sim down")

    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    app.dependency_overrides[get_wallbox_client] = lambda: Failing()
    try:
        client = TestClient(app)
        sign_in(client, "h1")
        assert client.get("/wallbox/status").status_code == 502
    finally:
        app.dependency_overrides.clear()
