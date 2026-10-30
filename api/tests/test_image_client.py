"""Tests for the Muse Image client."""

import base64

import pytest

from strompilot.llm.types import LlmError
from strompilot.report.images import IMAGE_MODEL, ImageClient


def test_generate_posts_shape_and_decodes_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"data": [{"b64_json": base64.b64encode(b"png-bytes").decode()}]}

    def fake_post(
        url: str, headers: dict[str, str], json: dict[str, object], timeout: float
    ) -> FakeResponse:
        captured["url"] = url
        captured["json"] = json
        assert headers["Authorization"].endswith("test-key")
        assert timeout >= 60
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ImageClient("test-key")
    assert client.generate("a dark control room") == b"png-bytes"
    assert captured["url"] == "https://api.meta.ai/v1/images/generations"
    payload = captured["json"]
    assert isinstance(payload, dict)
    assert payload["model"] == "muse-image-1.0"
    assert payload["prompt"] == "a dark control room"
    assert payload["size"] == "1536x1024"
    assert payload["response_format"] == "b64_json"
    assert IMAGE_MODEL == "muse-image-1.0"


def test_generate_rejects_blank_prompt() -> None:
    with pytest.raises(LlmError, match="prompt"):
        ImageClient("k").generate("  ")


def test_http_error_raises_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        status_code = 429
        text = "slow down"

        def json(self) -> dict[str, object]:
            raise AssertionError("must not parse")

    def fake_post(
        url: str, headers: dict[str, str], json: dict[str, object], timeout: float
    ) -> FakeResponse:
        del url, headers, json, timeout
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(LlmError, match="HTTP 429"):
        ImageClient("k").generate("x")


def test_bad_payload_raises_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"data": []}

    def fake_post(
        url: str, headers: dict[str, str], json: dict[str, object], timeout: float
    ) -> FakeResponse:
        del url, headers, json, timeout
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(LlmError, match="unreadable"):
        ImageClient("k").generate("x")
