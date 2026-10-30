"""Monthly report math: baseline days priced at bar rates."""

import calendar
import re
from collections.abc import Callable
from datetime import date, datetime, timedelta

from pydantic import BaseModel

from strompilot.flexalarm.watch import scan_windows
from strompilot.lifeplan.schemas import PriceBar
from strompilot.prices.models import BERLIN, PricePoint, PriceSeries
from strompilot.tariff.profiles import baseline_day

_MONTH = re.compile(r"^(19|20)\d\d-(0[1-9]|1[0-2])$")

_MONTH_NAMES = [
    "",
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
]

BarLoader = Callable[[date], tuple[list[PriceBar], bool]]


class CheapWindow(BaseModel):
    """One day's cheapest two hours."""

    start: str
    end: str
    avg_ct_kwh: float


class ReportDay(BaseModel):
    """One priced report day."""

    day: str
    kwh: float
    cost_eur: float
    cheapest_window: CheapWindow | None
    sample: bool


class WorstHour(BaseModel):
    """The month's most expensive priced hour."""

    day: str
    hour: int
    price_ct_kwh: float


class MonthlyReport(BaseModel):
    """One month of background use, priced and compared."""

    month: str
    annual_kwh: float
    days: list[ReportDay]
    total_kwh: float
    total_cost_eur: float
    savings_eur: float
    flat_ct_kwh: float
    worst_hour: WorstHour | None
    sample_days: int
    assumptions: list[str]


def art_prompt(month: str) -> str:
    """Build the cover-art prompt for one month, free of figures."""
    match = _MONTH.match(month)
    if match is None:
        raise ValueError(f"bad month: {month!r}")
    name = _MONTH_NAMES[int(month[5:7])]
    return (
        f"Cover illustration for a German home energy report, {name} theme: "
        "a dark modern control room wall with one glowing abstract heatmap "
        "band from green to amber, a small house silhouette with a solar roof, "
        "no text, no numbers, no people, calm and premium, wide composition."
    )


def _window_for(day: date, bars: list[PriceBar]) -> CheapWindow | None:
    """Find one day's cheapest window through the alarm scanner."""
    points = [
        PricePoint(
            start=datetime_berlin(day, bar.hour),
            end=datetime_berlin(day, bar.hour + 1),
            eur_per_mwh=bar.price_ct_kwh * 10,
        )
        for bar in bars
    ]
    series = PriceSeries(date=day, source="report", attribution="report", prices=points)
    cheap = next((c for c in scan_windows(series) if c.kind == "cheap_window"), None)
    if cheap is None:
        return None
    return CheapWindow(start=cheap.start, end=cheap.end, avg_ct_kwh=cheap.avg_ct_kwh)


def datetime_berlin(day: date, hour: int) -> datetime:
    """Build one Berlin wall-clock instant, rolling past midnight."""
    base = datetime(day.year, day.month, day.day, tzinfo=BERLIN)
    return base + timedelta(hours=hour)


def build_month(
    year: int,
    month: int,
    annual_kwh: float,
    loader: BarLoader,
    flat_ct_kwh: float,
    lang: str = "de",
) -> MonthlyReport:
    """Price every day of one month against the H25 baseline."""
    lang = "en" if lang == "en" else "de"
    month_key = f"{year:04d}-{month:02d}"
    if _MONTH.match(month_key) is None:
        raise ValueError(f"bad month: {month_key!r}")
    days: list[ReportDay] = []
    worst: WorstHour | None = None
    for day_number in range(1, calendar.monthrange(year, month)[1] + 1):
        day = date(year, month, day_number)
        bars, sample = loader(day)
        by_hour = {bar.hour: bar.price_ct_kwh for bar in bars}
        kwh = 0.0
        cost = 0.0
        for baseline in baseline_day(day, annual_kwh):
            rate = by_hour.get(baseline.start.astimezone(BERLIN).hour)
            if rate is None:
                continue
            kwh += baseline.kwh
            cost += baseline.kwh * rate / 100
        for bar in bars:
            if worst is None or bar.price_ct_kwh > worst.price_ct_kwh:
                worst = WorstHour(
                    day=day.isoformat(), hour=bar.hour, price_ct_kwh=bar.price_ct_kwh
                )
        days.append(
            ReportDay(
                day=day.isoformat(),
                kwh=round(kwh, 2),
                cost_eur=round(cost, 2),
                cheapest_window=_window_for(day, bars),
                sample=sample,
            )
        )
    total_kwh = round(sum(day.kwh for day in days), 2)
    total_cost = round(sum(day.cost_eur for day in days), 2)
    return MonthlyReport(
        month=month_key,
        annual_kwh=annual_kwh,
        days=days,
        total_kwh=total_kwh,
        total_cost_eur=total_cost,
        savings_eur=round(total_kwh * flat_ct_kwh / 100 - total_cost, 2),
        flat_ct_kwh=flat_ct_kwh,
        worst_hour=worst,
        sample_days=sum(1 for day in days if day.sample),
        assumptions=_assumptions(annual_kwh, flat_ct_kwh, lang),
    )


def _assumptions(annual_kwh: float, flat_ct_kwh: float, lang: str) -> list[str]:
    """State the report basis in the household language."""
    if lang == "en":
        return [
            f"Annual use {annual_kwh:.0f} kWh on H25 profile basis.",
            f"Reference tariff {flat_ct_kwh:.2f} ct/kWh, assumed.",
            "Hourly prices; billing settles quarter-hourly.",
        ]
    return [
        f"Jahresverbrauch {annual_kwh:.0f} kWh auf H25-Profilbasis.",
        f"Vergleichstarif {flat_ct_kwh:.2f} ct/kWh, Annahme.",
        "Stundenpreise; die Abrechnung erfolgt viertelstündlich.",
    ]
