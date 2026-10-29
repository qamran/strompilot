"""Tests for meter display cropping."""

import io

import pytest
from PIL import Image

from strompilot.metervision.crop import crop_to_box, pick_box
from strompilot.metervision.models import MeterError
from strompilot.metervision.sam import SegmentBox


def box(
    x1: int = 10,
    y1: int = 10,
    x2: int = 50,
    y2: int = 50,
    width: int = 100,
    height: int = 100,
    confidence: float | None = 0.9,
) -> SegmentBox:
    """Build a segment box with test defaults."""
    return SegmentBox(
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
        width=width,
        height=height,
        confidence=confidence,
    )


def red_square() -> bytes:
    """100x100 red PNG with a blue 40x40 block at (10, 10)."""
    image = Image.new("RGB", (100, 100), (255, 0, 0))
    block = Image.new("RGB", (40, 40), (0, 0, 255))
    image.paste(block, (10, 10))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def opened(photo: bytes) -> Image.Image:
    """Decode cropped bytes for pixel assertions."""
    return Image.open(io.BytesIO(photo))


def test_exact_crop_keeps_pixels() -> None:
    cropped = opened(crop_to_box(red_square(), box(), margin=0.0))
    assert cropped.size == (40, 40)
    assert cropped.getpixel((0, 0)) == (0, 0, 255)
    assert cropped.getpixel((39, 39)) == (0, 0, 255)


def test_margin_expands_evenly() -> None:
    cropped = opened(crop_to_box(red_square(), box(), margin=0.25))
    assert cropped.size == (60, 60)
    assert cropped.getpixel((0, 0)) == (255, 0, 0)
    assert cropped.getpixel((10, 10)) == (0, 0, 255)


def test_crop_clamps_to_photo_edges() -> None:
    edge = box(x1=80, y1=80, x2=95, y2=95)
    cropped = opened(crop_to_box(red_square(), edge, margin=1.0))
    assert cropped.size == (35, 35)


def test_box_scales_to_actual_pixels() -> None:
    doubled = box(x1=20, y1=20, x2=100, y2=100, width=200, height=200)
    cropped = opened(crop_to_box(red_square(), doubled, margin=0.0))
    assert cropped.size == (40, 40)
    assert cropped.getpixel((0, 0)) == (0, 0, 255)


def test_garbage_bytes_rejected() -> None:
    with pytest.raises(MeterError, match="photo"):
        crop_to_box(b"not a photo", box())


def test_pick_box_prefers_confidence_then_area() -> None:
    low = box(confidence=0.5)
    high = box(x1=0, y1=0, x2=20, y2=20, confidence=0.9)
    assert pick_box([low, high]) == high
    assert pick_box([]) is None
    unranked = box(confidence=None)
    assert pick_box([unranked, low]) == low


def test_pick_box_breaks_confidence_ties_by_area() -> None:
    small = box(x1=0, y1=0, x2=10, y2=10, confidence=0.8)
    big = box(x1=0, y1=0, x2=40, y2=40, confidence=0.8)
    assert pick_box([small, big]) == big
