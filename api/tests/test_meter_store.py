"""Tests for the meter reading store."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from strompilot.metervision.models import MeterError
from strompilot.metervision.store import MeterStore


def read_at(day: int) -> datetime:
    """Build a June 2026 UTC reading instant."""
    return datetime(2026, 6, day, 8, 0, tzinfo=UTC)


def test_propose_then_confirm(tmp_path: Path) -> None:
    store = MeterStore(tmp_path / "meter.db")
    proposed = store.propose(
        household_id="hh1",
        value_kwh=4217.3,
        read_at=read_at(1),
        confidence="high",
        sam_box=None,
        photo_path="photos/1.png",
    )
    assert proposed.id == 1
    assert proposed.status == "proposed"
    confirmed = store.confirm("hh1", proposed.id, corrected_kwh=None)
    assert confirmed.status == "confirmed"
    assert confirmed.value_kwh == 4217.3
    assert confirmed.read_at == read_at(1)


def test_confirm_accepts_a_correction(tmp_path: Path) -> None:
    store = MeterStore(tmp_path / "meter.db")
    proposed = store.propose(
        household_id="hh1",
        value_kwh=4217.3,
        read_at=read_at(1),
        confidence="low",
        sam_box="box",
        photo_path="photos/1.png",
    )
    confirmed = store.confirm("hh1", proposed.id, corrected_kwh=4218.0)
    assert (confirmed.value_kwh, confirmed.status) == (4218.0, "confirmed")


def test_confirm_rejects_bad_values(tmp_path: Path) -> None:
    store = MeterStore(tmp_path / "meter.db")
    proposed = store.propose(
        household_id="hh1",
        value_kwh=10.0,
        read_at=read_at(1),
        confidence="high",
        sam_box=None,
        photo_path="p",
    )
    with pytest.raises(MeterError, match="value"):
        store.confirm("hh1", proposed.id, corrected_kwh=-1.0)
    with pytest.raises(MeterError, match="not found"):
        store.confirm("hh1", 999, corrected_kwh=None)
    with pytest.raises(MeterError, match="not found"):
        store.confirm("hh2", proposed.id, corrected_kwh=None)


def test_confirmed_lists_only_confirmed(tmp_path: Path) -> None:
    store = MeterStore(tmp_path / "meter.db")
    first = store.propose(
        household_id="hh1",
        value_kwh=10.0,
        read_at=read_at(1),
        confidence="high",
        sam_box=None,
        photo_path="p",
    )
    store.propose(
        household_id="hh1",
        value_kwh=20.0,
        read_at=read_at(2),
        confidence="high",
        sam_box=None,
        photo_path="p",
    )
    store.confirm("hh1", first.id, corrected_kwh=None)
    assert [reading.value_kwh for reading in store.confirmed("hh1")] == [10.0]
    assert len(store.list_readings("hh1")) == 2


def test_confirmed_orders_oldest_first(tmp_path: Path) -> None:
    store = MeterStore(tmp_path / "meter.db")
    for day, value in [(3, 30.0), (1, 10.0), (2, 20.0)]:
        proposed = store.propose(
            household_id="hh1",
            value_kwh=value,
            read_at=read_at(day),
            confidence="high",
            sam_box=None,
            photo_path="p",
        )
        store.confirm("hh1", proposed.id, corrected_kwh=None)
    assert [r.value_kwh for r in store.confirmed("hh1")] == [10.0, 20.0, 30.0]


def test_blank_household_rejected(tmp_path: Path) -> None:
    store = MeterStore(tmp_path / "meter.db")
    with pytest.raises(MeterError, match="household_id"):
        store.list_readings("  ")


def test_households_stay_isolated(tmp_path: Path) -> None:
    store = MeterStore(tmp_path / "meter.db")
    proposed = store.propose(
        household_id="hh1",
        value_kwh=10.0,
        read_at=read_at(1),
        confidence="high",
        sam_box=None,
        photo_path="p",
    )
    store.confirm("hh1", proposed.id, corrected_kwh=None)
    assert store.confirmed("hh2") == []
    assert store.list_readings("hh2") == []
