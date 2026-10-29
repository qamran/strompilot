"""Tests for the Flex-Alarm watcher loop."""

from datetime import datetime
from pathlib import Path

from strompilot.flexalarm.loop import release_due, run_all, run_once
from strompilot.flexalarm.models import Alert
from strompilot.flexalarm.senders import LoggingSender, SendError
from strompilot.flexalarm.store import AlertStore
from strompilot.memory.store import MemoryStore
from strompilot.prices.models import BERLIN
from tests.fakes import FakeRouter, day_series, reply


def prices() -> list[float]:
    """Cheap night plus an evening spike."""
    values = [25.0] * 24
    values[2] = 8.0
    values[3] = 9.0
    values[18] = 60.0
    return values


def stores(tmp_path: Path) -> tuple[MemoryStore, AlertStore]:
    """Memory plus alert stores sharing one database file."""
    path = tmp_path / "memory.db"
    return MemoryStore(path), AlertStore(path)


def noon() -> datetime:
    """Midday Berlin, safely outside quiet hours."""
    return datetime(2026, 6, 1, 12, 0, tzinfo=BERLIN)


def test_run_once_fires_and_delivers(tmp_path: Path) -> None:
    memory, alerts = stores(tmp_path)
    router = FakeRouter({"watcher": [reply('{"fire": true, "reason": "gut"}')] * 3})
    report = run_once(
        household_id="hh1",
        series=day_series(prices()),
        memory=memory,
        alerts=alerts,
        router=router,
        senders=[LoggingSender()],
        now=noon(),
    )
    assert report.candidates == 2
    assert (report.fired, report.delivered) == (2, 2)
    assert report.held == 0 and report.duplicates == 0
    assert [a.status for a in alerts.list_alerts("hh1")] == [
        "delivered",
        "delivered",
    ]


def test_triage_skip_stores_nothing_and_reports(tmp_path: Path) -> None:
    memory, alerts = stores(tmp_path)
    router = FakeRouter({"watcher": [reply('{"fire": false, "reason": "nervt"}')] * 3})
    report = run_once(
        household_id="hh1",
        series=day_series(prices()),
        memory=memory,
        alerts=alerts,
        router=router,
        senders=[LoggingSender()],
        now=noon(),
    )
    assert report.skipped == 2
    assert alerts.list_alerts("hh1") == []


def test_rerun_dedups_without_model_calls(tmp_path: Path) -> None:
    memory, alerts = stores(tmp_path)
    router = FakeRouter({"watcher": [reply('{"fire": true, "reason": "gut"}')] * 3})
    first = run_once(
        household_id="hh1",
        series=day_series(prices()),
        memory=memory,
        alerts=alerts,
        router=router,
        senders=[LoggingSender()],
        now=noon(),
    )
    assert first.fired == 2
    router.calls.clear()
    second = run_once(
        household_id="hh1",
        series=day_series(prices()),
        memory=memory,
        alerts=alerts,
        router=router,
        senders=[LoggingSender()],
        now=noon(),
    )
    assert second.duplicates == 2
    assert router.calls == []
    assert len(alerts.list_alerts("hh1")) == 2


def test_quiet_hours_hold_delivery(tmp_path: Path) -> None:
    memory, alerts = stores(tmp_path)
    router = FakeRouter({"watcher": [reply('{"fire": true, "reason": "gut"}')] * 3})
    night = datetime(2026, 6, 1, 23, 30, tzinfo=BERLIN)
    report = run_once(
        household_id="hh1",
        series=day_series(prices()),
        memory=memory,
        alerts=alerts,
        router=router,
        senders=[LoggingSender()],
        now=night,
    )
    assert (report.fired, report.held) == (2, 2)
    assert report.delivered == 0
    assert [a.status for a in alerts.list_alerts("hh1")] == ["held", "held"]


def test_release_due_delivers_after_quiet_hours(tmp_path: Path) -> None:
    memory, alerts = stores(tmp_path)
    router = FakeRouter({"watcher": [reply('{"fire": true, "reason": "gut"}')] * 3})
    night = datetime(2026, 6, 1, 23, 30, tzinfo=BERLIN)
    run_once(
        household_id="hh1",
        series=day_series(prices()),
        memory=memory,
        alerts=alerts,
        router=router,
        senders=[LoggingSender()],
        now=night,
    )
    summary = release_due(
        household_id="hh1",
        memory=memory,
        alerts=alerts,
        senders=[LoggingSender()],
        now=noon(),
    )
    assert (summary["delivered"], summary["failed"]) == (2, 0)
    assert [a.status for a in alerts.list_alerts("hh1")] == [
        "delivered",
        "delivered",
    ]


def test_release_during_quiet_hours_keeps_holding(tmp_path: Path) -> None:
    memory, alerts = stores(tmp_path)
    router = FakeRouter({"watcher": [reply('{"fire": true, "reason": "gut"}')] * 3})
    night = datetime(2026, 6, 1, 23, 30, tzinfo=BERLIN)
    run_once(
        household_id="hh1",
        series=day_series(prices()),
        memory=memory,
        alerts=alerts,
        router=router,
        senders=[LoggingSender()],
        now=night,
    )
    summary = release_due(
        household_id="hh1",
        memory=memory,
        alerts=alerts,
        senders=[LoggingSender()],
        now=night,
    )
    assert (summary["delivered"], summary["failed"]) == (0, 0)
    assert [a.status for a in alerts.list_alerts("hh1")] == ["held", "held"]


def test_sender_failure_falls_through_to_next_sender(tmp_path: Path) -> None:
    class Failing:
        channel = "webhook"

        def send(self, alert: Alert) -> None:
            raise SendError("hook down")

    memory, alerts = stores(tmp_path)
    router = FakeRouter({"watcher": [reply('{"fire": true, "reason": "gut"}')] * 3})
    report = run_once(
        household_id="hh1",
        series=day_series(prices()),
        memory=memory,
        alerts=alerts,
        router=router,
        senders=[Failing(), LoggingSender()],
        now=noon(),
    )
    assert report.delivered == 2
    assert {a.channel for a in alerts.list_alerts("hh1")} == {"log"}


def test_total_sender_failure_marks_failed_with_error(tmp_path: Path) -> None:
    class Failing:
        channel = "webhook"

        def send(self, alert: Alert) -> None:
            raise SendError("hook down")

    memory, alerts = stores(tmp_path)
    router = FakeRouter({"watcher": [reply('{"fire": true, "reason": "gut"}')] * 3})
    report = run_once(
        household_id="hh1",
        series=day_series(prices()),
        memory=memory,
        alerts=alerts,
        router=router,
        senders=[Failing()],
        now=noon(),
    )
    assert report.delivered == 0
    assert len(report.errors) == 2
    assert [a.status for a in alerts.list_alerts("hh1")] == ["failed", "failed"]


def test_devices_and_recent_alerts_reach_triage(tmp_path: Path) -> None:
    memory, alerts = stores(tmp_path)
    memory.set_preference("hh1", "devices", ["E-Auto"])
    router = FakeRouter({"watcher": [reply('{"fire": true, "reason": "gut"}')] * 3})
    run_once(
        household_id="hh1",
        series=day_series(prices()),
        memory=memory,
        alerts=alerts,
        router=router,
        senders=[LoggingSender()],
        now=noon(),
    )
    assert "E-Auto" in router.prompts[0]


def test_run_once_releases_held_from_earlier_passes(tmp_path: Path) -> None:
    memory, alerts = stores(tmp_path)
    router = FakeRouter({"watcher": [reply('{"fire": true, "reason": "gut"}')] * 3})
    night = datetime(2026, 6, 1, 23, 30, tzinfo=BERLIN)
    run_once(
        household_id="hh1",
        series=day_series(prices()),
        memory=memory,
        alerts=alerts,
        router=router,
        senders=[LoggingSender()],
        now=night,
    )
    report = run_once(
        household_id="hh1",
        series=day_series(prices()),
        memory=memory,
        alerts=alerts,
        router=router,
        senders=[LoggingSender()],
        now=noon(),
    )
    assert report.released == 2
    assert report.duplicates == 2
    assert [a.status for a in alerts.list_alerts("hh1")] == [
        "delivered",
        "delivered",
    ]


def test_run_all_covers_every_household(tmp_path: Path) -> None:
    memory, alerts = stores(tmp_path)
    memory.set_preference("hh1", "devices", [])
    memory.set_preference("hh2", "devices", [])
    router = FakeRouter({"watcher": [reply('{"fire": true, "reason": "gut"}')] * 6})
    reports = run_all(
        series=day_series(prices()),
        memory=memory,
        alerts=alerts,
        router=router,
        senders=[LoggingSender()],
        now=noon(),
    )
    assert {report.household_id for report in reports} == {"hh1", "hh2"}
    assert all(report.fired == 2 for report in reports)
