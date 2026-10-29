"""Tests for the SAM 3.1 segmentation client."""

import pytest

from strompilot.llm.types import LlmError
from strompilot.metervision.sam import SamClient, SegmentBox


def sse(*events: str) -> str:
    """Build one SSE body from event payloads."""
    return "".join(f"data: {event}\n\n" for event in events)


def delta(text: str) -> str:
    """Build one output-text delta event."""
    escaped = text.replace('"', '\\"')
    return f'{{"type": "response.output_text.delta", "delta": "{escaped}"}}'


COMPLETED = '{"type": "response.completed"}'

BOX_LINE = (
    "<0f>1<|box;x1=100;y1=50;x2=300;y2=150;w=640;h=480;c=0.96|>"
    "<|mask;x=0;y=0;c=0.96;data=9,12,!eJxz|>"
)


def test_segment_posts_prompt_and_image(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200
        text = sse(delta(BOX_LINE), COMPLETED)

    def fake_post(
        url: str,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: float,
    ) -> FakeResponse:
        del timeout
        captured["url"] = url
        captured["json"] = json
        captured["accept"] = headers["Accept"]
        assert headers["Authorization"].removeprefix("Bearer ") == "test-key"
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    boxes = SamClient("test-key").segment(
        b64="aGk=", mime="image/png", prompt="electricity meter display"
    )
    assert captured["url"] == "https://api.meta.ai/v1/responses"
    assert captured["accept"] == "text/event-stream"
    payload = captured["json"]
    assert isinstance(payload, dict)
    assert payload["model"] == "sam-3.1"
    assert payload["stream"] is True
    assert payload["metadata"] == {"include_confidence": "true"}
    (message,) = payload["input"]
    assert message["role"] == "user"
    assert message["content"] == [
        {"type": "input_text", "text": "electricity meter display"},
        {"type": "input_image", "image_url": "data:image/png;base64,aGk="},
    ]
    assert boxes == [
        SegmentBox(
            x1=100, y1=50, x2=300, y2=150, width=640, height=480, confidence=0.96
        )
    ]


def test_zero_matches_returns_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        status_code = 200
        text = sse(COMPLETED)

    def fake_post(
        url: str,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: float,
    ) -> FakeResponse:
        del url, headers, json, timeout
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    assert SamClient("k").segment(b64="eA==", mime="image/jpeg", prompt="x") == []


def test_split_deltas_reassemble_one_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        status_code = 200
        text = sse(delta(BOX_LINE[:40]), delta(BOX_LINE[40:]), COMPLETED)

    def fake_post(
        url: str,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: float,
    ) -> FakeResponse:
        del url, headers, json, timeout
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    (box,) = SamClient("k").segment(b64="eA==", mime="image/jpeg", prompt="x")
    assert (box.x1, box.y1, box.x2, box.y2) == (100, 50, 300, 150)


def test_boxes_without_confidence_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    line = (
        "<0f>2<|box;x1=10;y1=20;x2=30;y2=40;w=100;h=100|>"
        "<|mask;x=0;y=0;data=3,4,~eJxz|>"
    )

    class FakeResponse:
        status_code = 200
        text = sse(delta(line), COMPLETED)

    def fake_post(
        url: str,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: float,
    ) -> FakeResponse:
        del url, headers, json, timeout
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    (box,) = SamClient("k").segment(b64="eA==", mime="image/jpeg", prompt="x")
    assert box.confidence is None
    assert (box.x1, box.x2) == (10, 30)


def test_sparse_ids_all_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    line = (
        "<0f>0<|box;x1=1;y1=1;x2=2;y2=2;w=10;h=10|>"
        "<|mask;x=0;y=0;data=1,1,!e|>,"
        "2<|box;x1=5;y1=5;x2=7;y2=7;w=10;h=10|>"
        "<|mask;x=0;y=0;data=1,1,!e|>"
    )

    class FakeResponse:
        status_code = 200
        text = sse(delta(line), COMPLETED)

    def fake_post(
        url: str,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: float,
    ) -> FakeResponse:
        del url, headers, json, timeout
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    boxes = SamClient("k").segment(b64="eA==", mime="image/jpeg", prompt="x")
    assert [(box.x1, box.y1) for box in boxes] == [(1, 1), (5, 5)]


def test_http_error_raises_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        status_code = 400
        text = "bad prompt"

    def fake_post(
        url: str,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: float,
    ) -> FakeResponse:
        del url, headers, json, timeout
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(LlmError, match="HTTP 400"):
        SamClient("k").segment(b64="eA==", mime="image/jpeg", prompt="x")


def test_transport_error_raises_llm_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(
        url: str,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: float,
    ) -> object:
        del url, headers, json, timeout
        raise httpx.ConnectError("down")

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(LlmError, match="request failed"):
        SamClient("k").segment(b64="eA==", mime="image/jpeg", prompt="x")
