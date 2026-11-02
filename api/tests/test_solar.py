"""Tests for the solar teaser: roof measuring plus panel estimates."""

import pytest

from strompilot.metervision.sam import SegmentBox
from strompilot.solar.estimate import estimate_roof


def box(x1: int, y1: int, x2: int, y2: int) -> SegmentBox:
    """One SAM box on an 800x600 photo."""
    return SegmentBox(x1=x1, y1=y1, x2=x2, y2=y2, width=800, height=600, confidence=0.9)


def test_roof_estimate_counts_panels_from_width() -> None:
    """A 400x200 box on a 10 m roof fits 17 panels at 6.8 kWp."""
    estimate = estimate_roof([box(100, 50, 500, 250)], roof_width_m=10.0)
    assert estimate is not None
    assert estimate.roof_m2 == pytest.approx(50.0)
    assert estimate.usable_m2 == pytest.approx(35.0)
    assert estimate.panels == 17
    assert estimate.kwp == pytest.approx(6.8)
    assert estimate.kwh_per_year == pytest.approx(6460.0)
    assert estimate.roof_share == pytest.approx(80000 / 480000)
    assert len(estimate.assumptions) >= 3


def test_roof_estimate_reports_share_without_width() -> None:
    """Without a real-world width the estimate stays in shares."""
    estimate = estimate_roof([box(100, 50, 500, 250)], roof_width_m=None)
    assert estimate is not None
    assert estimate.panels is None
    assert estimate.roof_m2 is None
    assert estimate.roof_share == pytest.approx(80000 / 480000)


def test_roof_estimate_picks_the_largest_box() -> None:
    """Two boxes: the dormer loses to the main roof."""
    estimate = estimate_roof(
        [box(10, 10, 60, 60), box(100, 50, 500, 250)], roof_width_m=10.0
    )
    assert estimate is not None
    assert estimate.roof_m2 == pytest.approx(50.0)


def test_roof_estimate_rejects_empty_and_nonsense() -> None:
    """No boxes means no estimate; bad widths are rejected loudly."""
    assert estimate_roof([], roof_width_m=10.0) is None
    with pytest.raises(ValueError, match="roof_width_m"):
        estimate_roof([box(100, 50, 500, 250)], roof_width_m=0.0)
    with pytest.raises(ValueError, match="roof_width_m"):
        estimate_roof([box(100, 50, 500, 250)], roof_width_m=-3.0)
