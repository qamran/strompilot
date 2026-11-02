"""Solar teaser value objects."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RoofEstimate:
    """One roof's panel fit, with the assumptions it rests on."""

    roof_share: float
    roof_m2: float | None
    usable_m2: float | None
    panels: int | None
    kwp: float | None
    kwh_per_year: float | None
    assumptions: tuple[str, ...]
