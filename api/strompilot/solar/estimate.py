"""Roof measuring: turn SAM boxes into a panel-fit estimate.

The math assumes a straight-on photo with square pixels, so one scale
fits both axes. Every result carries its assumptions, because a teaser
that hides them is a sales pitch, not an estimate.
"""

from strompilot.metervision.sam import SegmentBox

from .models import RoofEstimate

USABLE_FRACTION = 0.7
PANEL_M2 = 2.0
PANEL_KW = 0.4
KWH_PER_KWP = 950.0


def estimate_roof(
    boxes: list[SegmentBox], roof_width_m: float | None
) -> RoofEstimate | None:
    """Estimate one roof's panel fit from its largest box."""
    if not boxes:
        return None
    if roof_width_m is not None and roof_width_m <= 0:
        raise ValueError("roof_width_m must be positive")
    roof = max(boxes, key=lambda box: (box.x2 - box.x1) * (box.y2 - box.y1))
    pixels = (roof.x2 - roof.x1) * (roof.y2 - roof.y1)
    share = pixels / (roof.width * roof.height)
    assumptions = [
        "Photo is taken straight-on with square pixels.",
        "70% of the boxed roof is usable (chimney, edges, shade).",
        "One panel covers 2.0 m² at 0.4 kWp.",
    ]
    if roof_width_m is None:
        return RoofEstimate(
            roof_share=share,
            roof_m2=None,
            usable_m2=None,
            panels=None,
            kwp=None,
            kwh_per_year=None,
            assumptions=tuple(
                assumptions + ["Add the roof width in meters for m² and panels."]
            ),
        )
    scale = (roof.x2 - roof.x1) / roof_width_m
    area = pixels / (scale * scale)
    usable = area * USABLE_FRACTION
    panels = int(usable // PANEL_M2)
    kwp = panels * PANEL_KW
    return RoofEstimate(
        roof_share=share,
        roof_m2=area,
        usable_m2=usable,
        panels=panels,
        kwp=kwp,
        kwh_per_year=kwp * KWH_PER_KWP,
        assumptions=tuple(assumptions + ["Berlin yield: 950 kWh per kWp per year."]),
    )
