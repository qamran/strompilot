"""Life-to-plan schemas: constraints, prices, slots, citations."""

from pydantic import BaseModel, Field, field_validator

_TIME_RE = r"^([01]\d|2[0-3]):([0-5]\d)$"


class DeviceConstraint(BaseModel):
    """One shiftable or fixed device with its running window."""

    device: str = Field(min_length=1)

    @field_validator("device")
    @classmethod
    def _strip_device(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("device must name the device")
        return stripped

    power_kw: float = Field(gt=0)
    duration_h: float = Field(gt=0)
    earliest: str = Field(pattern=_TIME_RE)
    latest: str = Field(pattern=_TIME_RE)
    shiftable: bool = True


class HouseholdConstraints(BaseModel):
    """Editable household constraints: the extraction output."""

    devices: list[DeviceConstraint] = []
    notes: str = ""


class PriceBar(BaseModel):
    """One priced Berlin hour with its source label."""

    hour: int = Field(ge=0, le=23)
    price_ct_kwh: float
    source: str = Field(min_length=1)


class ScheduledSlot(BaseModel):
    """One optimized device run with its priced cost."""

    device: str = Field(min_length=1)
    start: str = Field(pattern=_TIME_RE)
    end: str = Field(pattern=_TIME_RE)
    energy_kwh: float = Field(ge=0)
    price_ct_kwh: float
    cost_eur: float = Field(ge=0)
    reason: str = Field(min_length=1)


class Citation(BaseModel):
    """One sourced claim backing the narration."""

    claim: str = Field(min_length=1)
    source: str = Field(min_length=1)
    detail: str = Field(min_length=1)


class Narration(BaseModel):
    """The narrated plan with citations and leftover violations."""

    text: str
    citations: list[Citation] = []
    violations: list[str] = []
