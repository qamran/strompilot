"""SAM 3.1 segmentation over the Responses API streamed SSE."""

import json
import re
from dataclasses import dataclass

import httpx

from strompilot.llm.client import META_BASE_URL
from strompilot.llm.types import LlmError

SAM_MODEL = "sam-3.1"
SAM_TIMEOUT_SECONDS = 120.0

_BOX_TOKEN = re.compile(r"<\|box;([^|]*)\|>")


@dataclass(frozen=True)
class SegmentBox:
    """One detected box in source pixels with optional confidence."""

    x1: int
    y1: int
    x2: int
    y2: int
    width: int
    height: int
    confidence: float | None


def _fields(token: str) -> dict[str, str]:
    """Split one box token body into keyed fields."""
    fields: dict[str, str] = {}
    for part in token.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        if key and value:
            fields[key] = value
    return fields


def parse_boxes(output_text: str) -> list[SegmentBox]:
    """Read every box token from streamed output text, in order."""
    boxes: list[SegmentBox] = []
    for match in _BOX_TOKEN.finditer(output_text):
        fields = _fields(match.group(1))
        try:
            box = SegmentBox(
                x1=int(fields["x1"]),
                y1=int(fields["y1"]),
                x2=int(fields["x2"]),
                y2=int(fields["y2"]),
                width=int(fields["w"]),
                height=int(fields["h"]),
                confidence=(float(fields["c"]) if "c" in fields else None),
            )
        except (KeyError, ValueError):
            continue
        boxes.append(box)
    return boxes


def _accumulate(body: str) -> str:
    """Join the SSE delta lane into one output text."""
    chunks: list[str] = []
    for line in body.splitlines():
        if not line.startswith("data: "):
            continue
        data = line.removeprefix("data: ")
        if data == "[DONE]":
            break
        try:
            event = json.loads(data)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "response.output_text.delta":
            delta = event.get("delta", "")
            if isinstance(delta, str):
                chunks.append(delta)
        elif event.get("type") == "response.completed":
            break
    return "".join(chunks)


class SamClient:
    """Finds objects in one image from a short noun phrase."""

    def __init__(
        self,
        api_key: str,
        base_url: str = META_BASE_URL,
        timeout: float = SAM_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout

    def segment(self, b64: str, mime: str, prompt: str) -> list[SegmentBox]:
        """Return every detected box, or [] when nothing matches."""
        payload: dict[str, object] = {
            "model": SAM_MODEL,
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {
                            "type": "input_image",
                            "image_url": f"data:{mime};base64,{b64}",
                        },
                    ],
                }
            ],
            "stream": True,
            "metadata": {"include_confidence": "true"},
        }
        try:
            response = httpx.post(
                f"{self._base_url}/responses",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Accept": "text/event-stream",
                },
                json=payload,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise LlmError(f"request failed: {exc}") from exc
        if response.status_code != 200:
            raise LlmError(f"HTTP {response.status_code} from {self._base_url}")
        return parse_boxes(_accumulate(response.text))
