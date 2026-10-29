"""Tests for Spark vision digit reading."""

import pytest

from strompilot.llm.client import LOW_EFFORT
from strompilot.llm.types import ImageAttachment, LlmError
from strompilot.metervision.models import DigitReading, MeterError
from strompilot.metervision.read import read_digits
from tests.fakes import FakeRouter, reply


def test_clean_reading_parses() -> None:
    router = FakeRouter(
        {"analyst": [reply('{"value_kwh": 4217.3, "confidence": "high"}')]}
    )
    reading = read_digits("aGk=", "image/png", router)
    assert reading == DigitReading(value_kwh=4217.3, confidence="high")
    assert router.calls == ["analyst"]
    assert router.efforts == [LOW_EFFORT]
    assert router.temps == [0.0]


def test_image_reaches_the_wire_message() -> None:
    router = FakeRouter({"analyst": [reply('{"value_kwh": 1.0, "confidence": "low"}')]})
    read_digits("aGk=", "image/jpeg", router)
    (sent,) = router.messages
    assert sent[1].image == ImageAttachment(mime="image/jpeg", b64="aGk=")


def test_prompt_names_the_meter_job() -> None:
    router = FakeRouter({"analyst": [reply('{"value_kwh": 1.0, "confidence": "low"}')]})
    read_digits("aGk=", "image/png", router)
    prompt = router.prompts[0]
    assert "kWh" in prompt
    assert "OBIS" in prompt


def test_garbage_reply_fails_loudly() -> None:
    router = FakeRouter({"analyst": [reply("about four thousand")]})
    with pytest.raises(MeterError, match="unreadable digits"):
        read_digits("aGk=", "image/png", router)


def test_negative_value_rejected() -> None:
    router = FakeRouter(
        {"analyst": [reply('{"value_kwh": -5.0, "confidence": "high"}')]}
    )
    with pytest.raises(MeterError, match="unreadable digits"):
        read_digits("aGk=", "image/png", router)


def test_model_error_passes_through() -> None:
    router = FakeRouter({"analyst": [LlmError("spark down")]})
    with pytest.raises(LlmError, match="spark down"):
        read_digits("aGk=", "image/png", router)
