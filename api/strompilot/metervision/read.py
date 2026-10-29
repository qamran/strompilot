"""Digit reading: Spark vision turns the display crop into kWh."""

from strompilot.llm.client import LOW_EFFORT
from strompilot.llm.types import ChatRouter, ImageAttachment, Message

from .models import DigitReading, MeterError

READ_TOKENS = 500

_SYSTEM = """Read the electricity meter display in the photo. Reply with
exactly one JSON object and nothing else:
{"value_kwh": number, "confidence": "high" or "low"}.
Rules:
- Read the large cumulative register in kWh, the number the billing
uses. German displays use a comma for decimals: 04217,3 means 4217.3.
- Ignore small OBIS codes such as 1.8.0 and serial numbers.
- Say low when any digit is cut off, blurry, or half-flipped."""


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
