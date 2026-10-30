"""Calibration: annual household use from confirmed readings."""

from .models import Calibration, MeterReading

# Typical German household before any meter proof exists. The BDEW
# Stromspiegel brackets a 2-person flat around 2,000-3,500 kWh per year;
# we take the top of that bracket as the conservative illustration
# value. The first confirmed reading pair replaces it.
FALLBACK_ANNUAL_KWH = 3500.0


def calibrate(readings: list[MeterReading]) -> Calibration | None:
    """Extrapolate annual use from the two newest readings.

    Callers pass confirmed readings only (see MeterStore.confirmed).
    A backwards meter means replacement, not negative use, and a pair
    less than a day apart carries no signal, so it refuses to calibrate
    rather than inventing a number.
    """
    if len(readings) < 2:
        return None
    first, second = readings[-2], readings[-1]
    days = (second.read_at - first.read_at).total_seconds() / 86400
    used = second.value_kwh - first.value_kwh
    if days < 1 or used < 0:
        return None
    per_day = used / days
    return Calibration(
        annual_kwh=round(per_day * 365, 2),
        kwh_per_day=round(per_day, 4),
        days=round(days, 2),
        from_reading_id=first.id,
        to_reading_id=second.id,
    )
