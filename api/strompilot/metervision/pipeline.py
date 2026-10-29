"""Vision pipeline: SAM finds the display, Spark reads the digits."""

import base64
import io
from dataclasses import dataclass
from typing import Protocol

from PIL import Image, UnidentifiedImageError

from strompilot.llm.types import ChatRouter, LlmError

from .crop import crop_to_box, pick_box
from .models import MeterError
from .read import read_digits
from .sam import SegmentBox

# Pinned after a live prompt shootout on the meter fixtures: "digital
# display" was the only phrase that boxed the LCD on synthetic photos.
SAM_PROMPT = "digital display"


class Segmenter(Protocol):
    """One object finder, SAM or fake."""

    def segment(self, b64: str, mime: str, prompt: str) -> list[SegmentBox]: ...


@dataclass(frozen=True)
class MeterVision:
    """One request's vision deps: router plus segmenter."""

    router: ChatRouter
    sam: Segmenter


@dataclass(frozen=True)
class PhotoProposal:
    """One processed photo: value, confidence, and the box used."""

    value_kwh: float
    confidence: str
    sam_used: bool
    sam_box: SegmentBox | None


def _encode(photo: bytes) -> str:
    """Encode photo bytes for a data URL."""
    return base64.b64encode(photo).decode("ascii")


def process_photo(
    photo: bytes, mime: str, sam: Segmenter, router: ChatRouter
) -> PhotoProposal:
    """Turn one meter photo into a reading proposal.

    SAM locates the display and Spark reads the crop. A missing box,
    a SAM failure, or a failed crop read falls back to the full photo;
    only the last failure raises.
    """
    try:
        with Image.open(io.BytesIO(photo)) as image:
            image.verify()
    except (UnidentifiedImageError, ValueError, OSError) as exc:
        raise MeterError(f"unreadable photo: {exc}") from exc
    try:
        boxes = sam.segment(_encode(photo), mime, SAM_PROMPT)
    except LlmError:
        boxes = []
    box = pick_box(boxes)
    if box is None:
        reading = read_digits(_encode(photo), mime, router)
        return PhotoProposal(
            value_kwh=reading.value_kwh,
            confidence=reading.confidence,
            sam_used=False,
            sam_box=None,
        )
    crop = crop_to_box(photo, box)
    try:
        reading = read_digits(_encode(crop), "image/png", router)
    except MeterError:
        reading = read_digits(_encode(photo), mime, router)
        return PhotoProposal(
            value_kwh=reading.value_kwh,
            confidence=reading.confidence,
            sam_used=False,
            sam_box=None,
        )
    return PhotoProposal(
        value_kwh=reading.value_kwh,
        confidence=reading.confidence,
        sam_used=True,
        sam_box=box,
    )
