"""Digit reading: Spark vision turns the display crop into kWh."""

from strompilot.llm.client import LOW_EFFORT
from strompilot.llm.types import ChatRouter, ImageAttachment, LlmError, Message

from .models import DigitReading, MeterError, SerialReading

READ_TOKENS = 500

_SYSTEM = """Read the electricity meter display in the photo. Reply with
exactly one JSON object and nothing else:
{"value_kwh": number, "confidence": "high" or "low"}.
Rules:
- Read the large cumulative register in kWh, the number the billing
uses. German displays use a comma for decimals: 04217,3 means 4217.3.
- Ignore small OBIS codes such as 1.8.0 and serial numbers.
- Say low when any digit is cut off, blurry, or half-flipped."""

_SERIAL_SYSTEM = """Find the meter serial number (Zählernummer) printed on
the meter housing in the photo. Reply with exactly one JSON object and
nothing else: {"serial": "the number"}.
Rules:
- Read the long printed number on the housing, not the display.
- Ignore OBIS codes such as 1.8.0 and the kWh register.
- Reply {"serial": null} when no serial is visible."""


def read_digits(b64: str, mime: str, router: ChatRouter) -> DigitReading:
    """Read one display photo through the analyst leg, failing loudly."""
    messages = [
        Message(role="system", content=_SYSTEM),
        Message(
            role="user",
            content="Read this meter display.",
            image=ImageAttachment(mime=mime, b64=b64),
        ),
    ]
    result = router.chat("analyst", messages, READ_TOKENS, LOW_EFFORT, 0.0)
    try:
        reading = DigitReading.model_validate_json(result.content)
    except ValueError:
        raise MeterError("unreadable digits in model reply") from None
    if reading.value_kwh < 0 or reading.confidence not in ("high", "low"):
        raise MeterError("unreadable digits in model reply")
    return reading


def read_serial(b64: str, mime: str, router: ChatRouter) -> str | None:
    """Read one meter serial through the analyst leg, failing softly.

    The serial is a display nicety, never a blocker: any failure reads
    back as None instead of failing the upload.
    """
    messages = [
        Message(role="system", content=_SERIAL_SYSTEM),
        Message(
            role="user",
            content="Find the meter serial number.",
            image=ImageAttachment(mime=mime, b64=b64),
        ),
    ]
    try:
        result = router.chat("analyst", messages, READ_TOKENS, LOW_EFFORT, 0.0)
    except LlmError:
        return None
    try:
        reading = SerialReading.model_validate_json(result.content)
    except ValueError:
        return None
    serial = (reading.serial or "").strip()
    return serial or None
