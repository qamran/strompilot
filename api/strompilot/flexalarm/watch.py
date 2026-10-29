"""Window scanner: propose notable price windows for triage."""

from strompilot.prices.models import BERLIN, PriceSeries

from .models import AlertCandidate

_CHEAP_SPAN_HOURS = 2
_SPIKE_FACTOR = 1.5


def _hourly_ct(series: PriceSeries) -> list[tuple[int, float]]:
    """Average each Berlin clock hour to one ct/kWh value."""
    buckets: dict[int, list[float]] = {}
    for point in series.prices:
        hour = point.start.astimezone(BERLIN).hour
        buckets.setdefault(hour, []).append(point.ct_per_kwh)
    return [
        (hour, sum(values) / len(values)) for hour, values in sorted(buckets.items())
    ]


def _clock(hour: int) -> str:
    """Format a clock hour as HH:MM."""
    return f"{hour:02d}:00"


def scan_windows(series: PriceSeries) -> list[AlertCandidate]:
    """Propose cheap, spiky, and negative windows for the judge.

    The scanner only proposes: every candidate still needs a fire
    verdict from triage before it becomes an alert.
    """
    hours = _hourly_ct(series)
    if not hours:
        return []
    mean = sum(value for _, value in hours) / len(hours)
    stretch = _negative_stretch(series, hours, mean)
    cheap = _cheap_window(series, hours, mean)
    candidates = []
    if stretch is None or not _overlaps(cheap, stretch):
        candidates.append(cheap)
    spike = _spike(series, hours, mean)
    if spike is not None:
        candidates.append(spike)
    if stretch is not None:
        candidates.append(stretch)
    return candidates


def _overlaps(first: AlertCandidate, second: AlertCandidate) -> bool:
    """Tell whether two candidate windows share any hour."""
    first_start, first_end = int(first.start[:2]), int(first.end[:2])
    second_start, second_end = int(second.start[:2]), int(second.end[:2])
    return first_start < second_end and second_start < first_end


def _cheap_window(
    series: PriceSeries, hours: list[tuple[int, float]], mean: float
) -> AlertCandidate:
    """Find the cheapest continuous two-hour block."""
    indexed = {hour: value for hour, value in hours}
    best: tuple[int, float] | None = None
    for hour in range(24 - _CHEAP_SPAN_HOURS + 1):
        span_hours = [hour + offset for offset in range(_CHEAP_SPAN_HOURS)]
        if any(span not in indexed for span in span_hours):
            continue
        span = [indexed[span] for span in span_hours]
        avg = sum(span) / len(span)
        if best is None or avg < best[1]:
            best = (hour, avg)
    if best is None:
        first_hour, first_value = hours[0]
        return AlertCandidate(
            kind="cheap_window",
            day=series.date,
            start=_clock(first_hour),
            end=_clock((first_hour + 1) % 24),
            avg_ct_kwh=round(first_value, 2),
            mean_ct_kwh=round(mean, 2),
            extreme_ct_kwh=round(first_value, 2),
            hours=1.0,
        )
    start_hour, avg = best
    span_values = [indexed[start_hour + offset] for offset in range(_CHEAP_SPAN_HOURS)]
    return AlertCandidate(
        kind="cheap_window",
        day=series.date,
        start=_clock(start_hour),
        end=_clock(start_hour + _CHEAP_SPAN_HOURS),
        avg_ct_kwh=round(avg, 2),
        mean_ct_kwh=round(mean, 2),
        extreme_ct_kwh=round(min(span_values), 2),
        hours=float(_CHEAP_SPAN_HOURS),
    )


def _spike(
    series: PriceSeries, hours: list[tuple[int, float]], mean: float
) -> AlertCandidate | None:
    """Flag the priciest hour when it towers over the daily mean."""
    if mean <= 0:
        return None
    hour, value = max(hours, key=lambda item: item[1])
    if value < _SPIKE_FACTOR * mean:
        return None
    return AlertCandidate(
        kind="price_spike",
        day=series.date,
        start=_clock(hour),
        end=_clock((hour + 1) % 24),
        avg_ct_kwh=round(value, 2),
        mean_ct_kwh=round(mean, 2),
        extreme_ct_kwh=round(value, 2),
        hours=1.0,
    )


def _negative_stretch(
    series: PriceSeries, hours: list[tuple[int, float]], mean: float
) -> AlertCandidate | None:
    """Cover the longest unbroken stretch of negative hours."""
    best: list[tuple[int, float]] = []
    run: list[tuple[int, float]] = []
    for hour, value in hours:
        if value < 0 and (not run or hour == run[-1][0] + 1):
            run.append((hour, value))
        else:
            if len(run) > len(best):
                best = run
            run = [(hour, value)] if value < 0 else []
    if len(run) > len(best):
        best = run
    if not best:
        return None
    avg = sum(value for _, value in best) / len(best)
    return AlertCandidate(
        kind="negative_prices",
        day=series.date,
        start=_clock(best[0][0]),
        end=_clock(best[-1][0] + 1),
        avg_ct_kwh=round(avg, 2),
        mean_ct_kwh=round(mean, 2),
        extreme_ct_kwh=round(min(value for _, value in best), 2),
        hours=float(len(best)),
    )
