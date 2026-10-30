"""Tests for annual-use calibration from confirmed readings."""

from datetime import UTC, datetime

from strompilot.metervision.calibrate import FALLBACK_ANNUAL_KWH, calibrate
from strompilot.metervision.models import MeterReading


def reading(
    reading_id: int, value_kwh: float, day: int, status: str = "confirmed"
) -> MeterReading:
    """Build a June 2026 reading with test defaults."""
    stamp = datetime(2026, 6, day, 8, 0, tzinfo=UTC)
    return MeterReading(
        id=reading_id,
        household_id="hh1",
        value_kwh=value_kwh,
        read_at=stamp,
        status=status,
        confidence="high",
        sam_box=None,
        photo_path="p",
        created_at=stamp,
    )


def test_pair_extrapolates_to_annual() -> None:
    calibration = calibrate([reading(1, 4000.0, 1), reading(2, 4010.0, 11)])
    assert calibration is not None
    assert calibration.kwh_per_day == 1.0
    assert calibration.annual_kwh == 365.0
    assert calibration.days == 10.0
    assert (calibration.from_reading_id, calibration.to_reading_id) == (1, 2)


def test_newest_pair_wins() -> None:
    calibration = calibrate(
        [reading(1, 4000.0, 1), reading(2, 4010.0, 11), reading(3, 4030.0, 21)]
    )
    assert calibration is not None
    assert calibration.kwh_per_day == 2.0
    assert (calibration.from_reading_id, calibration.to_reading_id) == (2, 3)


def test_single_reading_cannot_calibrate() -> None:
    assert calibrate([reading(1, 4000.0, 1)]) is None
    assert calibrate([]) is None


def test_backwards_meter_means_replacement_not_use() -> None:
    assert calibrate([reading(1, 4010.0, 1), reading(2, 4000.0, 11)]) is None


def test_same_instant_cannot_calibrate() -> None:
    first = reading(1, 4000.0, 1)
    second = reading(2, 4010.0, 1)
    assert calibrate([first, second]) is None


def test_same_day_readings_cannot_calibrate() -> None:
    from datetime import timedelta

    first = reading(1, 4000.0, 1)
    second = MeterReading(
        **{
            **first.model_dump(),
            "id": 2,
            "value_kwh": 4010.0,
            "read_at": first.read_at + timedelta(hours=6),
        },
    )
    assert calibrate([first, second]) is None


def test_fallback_is_a_documented_typical_household() -> None:
    assert FALLBACK_ANNUAL_KWH == 3500.0
