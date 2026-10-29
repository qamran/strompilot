"""Tests for Flex-Alarm quiet hours."""

from datetime import datetime

import pytest

from strompilot.flexalarm.quiet import QuietHours, is_quiet, parse_quiet_hours
from strompilot.prices.models import BERLIN


def at(hour: int, minute: int = 0) -> datetime:
    """Build a Berlin wall-clock instant on the test day."""
    return datetime(2026, 6, 1, hour, minute, tzinfo=BERLIN)


def test_defaults_cover_the_night() -> None:
    quiet = parse_quiet_hours(None)
    assert (quiet.start, quiet.end) == ("22:00", "07:00")
    assert is_quiet(at(23, 30), quiet) is True
    assert is_quiet(at(6, 59), quiet) is True
    assert is_quiet(at(7, 0), quiet) is False
    assert is_quiet(at(12, 0), quiet) is False


def test_custom_window_parses() -> None:
    quiet = parse_quiet_hours({"start": "21:30", "end": "06:15"})
    assert is_quiet(at(21, 29), quiet) is False
    assert is_quiet(at(21, 30), quiet) is True
    assert is_quiet(at(6, 14), quiet) is True
    assert is_quiet(at(6, 15), quiet) is False


def test_daytime_window_without_overnight_wrap() -> None:
    quiet = QuietHours(start="13:00", end="15:00")
    assert is_quiet(at(12, 59), quiet) is False
    assert is_quiet(at(13, 0), quiet) is True
    assert is_quiet(at(14, 59), quiet) is True
    assert is_quiet(at(15, 0), quiet) is False


def test_utc_instants_convert_to_berlin() -> None:
    from datetime import UTC

    quiet = parse_quiet_hours(None)
    # 21:30 UTC is 23:30 Berlin in June, inside quiet hours.
    assert is_quiet(datetime(2026, 6, 1, 21, 30, tzinfo=UTC), quiet) is True


def test_malformed_prefs_fall_back_to_defaults() -> None:
    assert parse_quiet_hours({"start": "late", "end": "early"}) == parse_quiet_hours(
        None
    )
    assert parse_quiet_hours("22-7") == parse_quiet_hours(None)
    assert parse_quiet_hours({"start": "22:00"}) == parse_quiet_hours(None)


def test_bad_clock_values_rejected() -> None:
    with pytest.raises(ValueError, match="start"):
        QuietHours(start="24:00", end="07:00")
    with pytest.raises(ValueError, match="end"):
        QuietHours(start="22:00", end="7am")
