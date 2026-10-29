"""Tests for the meter vision pipeline."""

import io

import pytest
from PIL import Image

from strompilot.llm.types import LlmError
from strompilot.metervision.models import MeterError
from strompilot.metervision.pipeline import SAM_PROMPT, process_photo
from strompilot.metervision.sam import SegmentBox
from tests.fakes import FakeRouter, FakeSam, reply


def photo() -> bytes:
    """100x100 red PNG for pipeline tests."""
    image = Image.new("RGB", (100, 100), (255, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def box() -> SegmentBox:
    """Center box covering the test photo's middle."""
    return SegmentBox(x1=10, y1=10, x2=90, y2=90, width=100, height=100, confidence=0.9)


def test_box_found_crops_then_reads() -> None:
    sam = FakeSam([[box()]])
    router = FakeRouter(
        {"analyst": [reply('{"value_kwh": 4217.3, "confidence": "high"}')]}
    )
    proposal = process_photo(photo(), "image/png", sam, router)
    assert proposal.value_kwh == 4217.3
    assert proposal.sam_used is True
    assert proposal.sam_box == box()
    assert sam.prompts == [SAM_PROMPT]
    (sent,) = router.messages
    assert sent[1].image is not None
    assert sent[1].image.mime == "image/png"


def test_no_box_reads_full_photo() -> None:
    sam = FakeSam([[]])
    router = FakeRouter(
        {"analyst": [reply('{"value_kwh": 10.0, "confidence": "low"}')]}
    )
    proposal = process_photo(photo(), "image/jpeg", sam, router)
    assert proposal.sam_used is False
    assert proposal.sam_box is None
    (sent,) = router.messages
    assert sent[1].image is not None
    assert sent[1].image.mime == "image/jpeg"


def test_sam_error_falls_back_to_full_photo() -> None:
    sam = FakeSam([LlmError("sam down")])
    router = FakeRouter(
        {"analyst": [reply('{"value_kwh": 10.0, "confidence": "low"}')]}
    )
    proposal = process_photo(photo(), "image/png", sam, router)
    assert proposal.sam_used is False
    assert proposal.value_kwh == 10.0


def test_crop_read_failure_retries_full_photo() -> None:
    sam = FakeSam([[box()]])
    router = FakeRouter(
        {
            "analyst": [
                reply("keine Ahnung"),
                reply('{"value_kwh": 10.0, "confidence": "low"}'),
            ]
        }
    )
    proposal = process_photo(photo(), "image/jpeg", sam, router)
    assert proposal.value_kwh == 10.0
    assert proposal.sam_used is False
    assert len(router.messages) == 2


def test_double_read_failure_fails_loudly() -> None:
    sam = FakeSam([[box()]])
    router = FakeRouter({"analyst": [reply("nein"), reply("nein")]})
    with pytest.raises(MeterError, match="unreadable digits"):
        process_photo(photo(), "image/png", sam, router)


def test_model_error_passes_through() -> None:
    sam = FakeSam([[box()]])
    router = FakeRouter({"analyst": [LlmError("spark down")]})
    with pytest.raises(LlmError, match="spark down"):
        process_photo(photo(), "image/png", sam, router)


def test_unreadable_photo_rejected() -> None:
    sam = FakeSam([[box()]])
    router = FakeRouter({"analyst": [reply("{}")]})
    with pytest.raises(MeterError, match="photo"):
        process_photo(b"garbage", "image/png", sam, router)
    assert sam.prompts == []
