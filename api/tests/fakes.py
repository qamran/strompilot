"""Shared fakes for agent tests."""

from datetime import date, datetime, timedelta

from langchain_core.runnables import RunnableConfig

from strompilot.lifeplan.loaders import LoadedPrices
from strompilot.lifeplan.schemas import DeviceConstraint, PriceBar
from strompilot.llm.client import SPARK_MODEL
from strompilot.llm.types import ChatResult, Message
from strompilot.metervision.sam import SegmentBox
from strompilot.prices.models import BERLIN, PricePoint, PriceSeries
from strompilot.wallbox.client import WallboxStatus


def reply(
    content: str,
    model: str = SPARK_MODEL,
    input_tokens: int = 10,
    output_tokens: int = 5,
) -> ChatResult:
    """Build a scripted chat reply."""
    return ChatResult(
        content=content,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


ANALYST_JSON = """{"facts": ["billig nachts"],
"devices": [
{"device": "Waschmaschine", "power_kw": 2.0, "duration_h": 2.0,
"earliest": "00:00", "latest": "23:00", "shiftable": true}
],
"notes": ""}"""

CLEAN_NARRATION = (
    "Die Waschmaschine läuft von 02:00 bis 04:00 Uhr und kostet 0,60 €. "
    "Die Gesamtkosten betragen 0,60 €."
)


def price_bars() -> list[PriceBar]:
    """Test curve: night dip 02-04, midday dip, evening peak."""
    prices = [30.0] * 24
    prices[2] = 15.0
    prices[3] = 15.0
    prices[12] = 18.0
    prices[13] = 18.0
    prices[18] = 45.0
    prices[19] = 45.0
    return [
        PriceBar(hour=hour, price_ct_kwh=price, source="test")
        for hour, price in enumerate(prices)
    ]


def make_device(
    name: str = "Waschmaschine",
    power_kw: float = 2.0,
    duration_h: float = 2.0,
    earliest: str = "00:00",
    latest: str = "23:00",
    shiftable: bool = True,
) -> DeviceConstraint:
    """Build a device constraint with washer defaults."""
    return DeviceConstraint(
        device=name,
        power_kw=power_kw,
        duration_h=duration_h,
        earliest=earliest,
        latest=latest,
        shiftable=shiftable,
    )


def stub_loader() -> LoadedPrices:
    """Stub price loader over the shared test curve."""
    return LoadedPrices(
        bars=price_bars(), source="test", stale=False, attribution="test"
    )


def thread_config(thread_id: str) -> RunnableConfig:
    """Build a typed thread config for one thread."""
    return {"configurable": {"thread_id": thread_id}}


def day_series(prices_ct: list[float], day: date | None = None) -> PriceSeries:
    """Build one Berlin day of hourly prices from ct/kWh values."""
    target = day or date(2026, 6, 1)
    points = []
    for hour, ct in enumerate(prices_ct):
        start = datetime(target.year, target.month, target.day, hour, tzinfo=BERLIN)
        end = start + timedelta(hours=1)
        points.append(PricePoint(start=start, end=end, eur_per_mwh=round(ct * 10, 2)))
    return PriceSeries(
        date=target,
        source="test",
        attribution="test",
        prices=points,
    )


class StubLeg:
    """Scripted model leg that records its calls."""

    def __init__(self, model: str, script: list[ChatResult | Exception]) -> None:
        self.model = model
        self._script = list(script)
        self.calls: list[list[Message]] = []
        self.efforts: list[str | None] = []
        self.temps: list[float | None] = []

    def chat(
        self,
        messages: list[Message],
        max_tokens: int,
        reasoning_effort: str | None = None,
        temperature: float | None = None,
    ) -> ChatResult:
        del max_tokens
        self.calls.append(messages)
        self.efforts.append(reasoning_effort)
        self.temps.append(temperature)
        if not self._script:
            raise AssertionError(f"no scripted reply left for {self.model}")
        next_up = self._script.pop(0)
        if isinstance(next_up, Exception):
            raise next_up
        return next_up


class FakeWallbox:
    """Scripted wallbox that records programmed windows."""

    def __init__(self, script: list[WallboxStatus | Exception]) -> None:
        self._script = list(script)
        self.programs: list[tuple[str, str, float]] = []
        self.status_calls = 0

    def status(self) -> WallboxStatus:
        """Return an idle status, counting status polls."""
        self.status_calls += 1
        return idle_wallbox_status()

    def program(self, start_iso: str, end_iso: str, max_kw: float) -> WallboxStatus:
        """Record one programmed window or raise the scripted error."""
        self.programs.append((start_iso, end_iso, max_kw))
        if not self._script:
            raise AssertionError("no scripted status left")
        next_up = self._script.pop(0)
        if isinstance(next_up, Exception):
            raise next_up
        return next_up


def idle_wallbox_status() -> WallboxStatus:
    """Build a plugged-in idle wallbox status."""
    return WallboxStatus(
        plugged=True,
        charging=False,
        power_kw=0.0,
        max_kw=0.0,
        session_kwh=0.0,
        total_kwh=0.0,
        sim_now="2026-06-01T00:00:00+02:00",
        program=None,
    )


class FakeSam:
    """Scripted SAM segmenter that records its prompts."""

    def __init__(self, script: list[list[SegmentBox] | Exception]) -> None:
        self._script = list(script)
        self.prompts: list[str] = []

    def segment(self, b64: str, mime: str, prompt: str) -> list[SegmentBox]:
        del b64, mime
        self.prompts.append(prompt)
        if not self._script:
            raise AssertionError("no scripted boxes left")
        next_up = self._script.pop(0)
        if isinstance(next_up, Exception):
            raise next_up
        return next_up


class FakeRouter:
    """Scripted per-worker router for worker and graph tests."""

    def __init__(self, scripts: dict[str, list[ChatResult | Exception]]) -> None:
        self._scripts = {worker: list(script) for worker, script in scripts.items()}
        self.calls: list[str] = []
        self.efforts: list[str | None] = []
        self.temps: list[float | None] = []
        self.prompts: list[str] = []
        self.messages: list[list[Message]] = []

    def chat(
        self,
        worker: str,
        messages: list[Message],
        max_tokens: int,
        reasoning_effort: str | None = None,
        temperature: float | None = None,
    ) -> ChatResult:
        del max_tokens
        self.calls.append(worker)
        self.efforts.append(reasoning_effort)
        self.temps.append(temperature)
        self.messages.append(messages)
        self.prompts.append(
            "\n".join(f"{message.role}: {message.content}" for message in messages)
        )
        script = self._scripts.get(worker, [])
        if not script:
            raise AssertionError(f"no scripted reply left for {worker}")
        next_up = script.pop(0)
        if isinstance(next_up, Exception):
            raise next_up
        return next_up
