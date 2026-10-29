"""Tests for the Flex-Alarm composer and alert store."""

from datetime import date
from pathlib import Path

import pytest

from strompilot.flexalarm.compose import compose
from strompilot.flexalarm.models import AlertCandidate, TriageVerdict
from strompilot.flexalarm.store import AlertStore, dedup_key
from strompilot.memory.models import MemoryError


def candidate() -> AlertCandidate:
    """Cheap night window for the composer."""
    return AlertCandidate(
        kind="cheap_window",
        day=date(2026, 6, 1),
        start="02:00",
        end="04:00",
        avg_ct_kwh=8.5,
        mean_ct_kwh=25.0,
        extreme_ct_kwh=8.0,
        hours=2.0,
    )


def test_compose_names_window_and_prices() -> None:
    title, body = compose(candidate(), TriageVerdict(fire=True, reason="ok"))
    assert "02:00" in title and "04:00" in title
    assert "8,50" in body and "25,00" in body


def test_compose_mentions_negative_prices_plainly() -> None:
    stretch = AlertCandidate(
        kind="negative_prices",
        day=date(2026, 6, 1),
        start="11:00",
        end="14:00",
        avg_ct_kwh=-2.67,
        mean_ct_kwh=22.0,
        extreme_ct_kwh=-5.0,
        hours=3.0,
    )
    title, body = compose(stretch, TriageVerdict(fire=True, reason="ok"))
    assert "negativ" in body.lower()


def test_dedup_key_is_stable_per_window() -> None:
    assert dedup_key("hh1", candidate()) == dedup_key("hh1", candidate())
    assert dedup_key("hh1", candidate()) != dedup_key("hh2", candidate())


def test_record_then_duplicate_returns_none(tmp_path: Path) -> None:
    store = AlertStore(tmp_path / "alerts.db")
    key = dedup_key("hh1", candidate())
    first = store.record(
        household_id="hh1",
        dedup_key=key,
        kind="cheap_window",
        title="billig",
        body=" Text ",
        status="delivered",
        channel="log",
        reason="ok",
    )
    assert first is not None
    assert first.id == 1
    assert first.body == " Text "
    again = store.record(
        household_id="hh1",
        dedup_key=key,
        kind="cheap_window",
        title="billig",
        body="other",
        status="delivered",
        channel="log",
        reason="ok",
    )
    assert again is None
    assert [alert.id for alert in store.list_alerts("hh1")] == [1]


def test_blank_household_rejected(tmp_path: Path) -> None:
    store = AlertStore(tmp_path / "alerts.db")
    with pytest.raises(MemoryError, match="household_id"):
        store.list_alerts("  ")


def test_status_updates_stick(tmp_path: Path) -> None:
    store = AlertStore(tmp_path / "alerts.db")
    alert = store.record(
        household_id="hh1",
        dedup_key="k1",
        kind="cheap_window",
        title="t",
        body="b",
        status="held",
        channel=None,
        reason="quiet",
    )
    assert alert is not None
    store.set_status(alert.id, "delivered", "log")
    (updated,) = store.list_alerts("hh1")
    assert (updated.status, updated.channel) == ("delivered", "log")


def test_held_lists_only_held(tmp_path: Path) -> None:
    store = AlertStore(tmp_path / "alerts.db")
    for key, status in [("k1", "held"), ("k2", "delivered"), ("k3", "held")]:
        store.record(
            household_id="hh1",
            dedup_key=key,
            kind="cheap_window",
            title="t",
            body="b",
            status=status,
            channel=None,
            reason="r",
        )
    assert [alert.dedup_key for alert in store.held("hh1")] == ["k1", "k3"]


def test_households_stay_isolated(tmp_path: Path) -> None:
    store = AlertStore(tmp_path / "alerts.db")
    store.record(
        household_id="hh1",
        dedup_key="k1",
        kind="cheap_window",
        title="t",
        body="b",
        status="held",
        channel=None,
        reason="r",
    )
    assert store.list_alerts("hh2") == []
    assert store.held("hh2") == []
