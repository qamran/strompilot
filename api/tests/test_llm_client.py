"""Tests for the shared OpenAI-compatible chat client."""

import pytest

from strompilot.llm.client import (
    BASETEN_BASE_URL,
    META_BASE_URL,
    SPARK_MODEL,
    ChatClient,
)
from strompilot.llm.types import ImageAttachment, LlmError, Message


def test_chat_posts_shape_and_parses_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {
                "choices": [{"message": {"content": "hallo"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3},
            }

    def fake_post(
        url: str, headers: dict[str, str], json: dict[str, object], timeout: float
    ) -> FakeResponse:
        captured["url"] = url
        captured["model"] = json["model"]
        captured["messages"] = json["messages"]
        captured["max_tokens"] = json["max_tokens"]
        assert headers["Authorization"] == "Bearer test-key"
        assert timeout > 0
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ChatClient(META_BASE_URL, "test-key", SPARK_MODEL)
    result = client.chat([Message(role="user", content="hi")], max_tokens=10)
    assert captured["url"] == "https://api.meta.ai/v1/chat/completions"
    assert captured["model"] == "muse-spark-1.3"
    assert captured["messages"] == [{"role": "user", "content": "hi"}]
    assert captured["max_tokens"] == 10
    assert result.content == "hallo"
    assert result.model == "muse-spark-1.3"
    assert (result.input_tokens, result.output_tokens) == (12, 3)


def test_chat_targets_baseten_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "ok"}}]}

    def fake_post(
        url: str, headers: dict[str, str], json: dict[str, object], timeout: float
    ) -> FakeResponse:
        del headers, json, timeout
        captured["url"] = url
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ChatClient(
        BASETEN_BASE_URL, "test-key", "meta-models/muse-spark-open-1026"
    )
    result = client.chat([Message(role="user", content="hi")], max_tokens=10)
    assert captured["url"] == "https://inference.baseten.co/v1/chat/completions"
    assert result.content == "ok"
    assert (result.input_tokens, result.output_tokens) == (0, 0)


def test_chat_raises_on_error_status(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        status_code = 500

        def json(self) -> dict[str, object]:
            return {}

    def fake_post(
        url: str, headers: dict[str, str], json: dict[str, object], timeout: float
    ) -> FakeResponse:
        del url, headers, json, timeout
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ChatClient(META_BASE_URL, "test-key", SPARK_MODEL)
    with pytest.raises(LlmError, match="500"):
        client.chat([Message(role="user", content="hi")], max_tokens=10)


def test_chat_raises_on_broken_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"choices": []}

    def fake_post(
        url: str, headers: dict[str, str], json: dict[str, object], timeout: float
    ) -> FakeResponse:
        del url, headers, json, timeout
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ChatClient(META_BASE_URL, "test-key", SPARK_MODEL)
    with pytest.raises(LlmError, match="unreadable"):
        client.chat([Message(role="user", content="hi")], max_tokens=10)


def test_chat_raises_on_empty_content(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": None}}]}

    def fake_post(
        url: str, headers: dict[str, str], json: dict[str, object], timeout: float
    ) -> FakeResponse:
        del url, headers, json, timeout
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ChatClient(META_BASE_URL, "test-key", SPARK_MODEL)
    with pytest.raises(LlmError, match="unreadable"):
        client.chat([Message(role="user", content="hi")], max_tokens=10)


def test_chat_sends_reasoning_effort_when_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "plan"}}]}

    def fake_post(
        url: str, headers: dict[str, str], json: dict[str, object], timeout: float
    ) -> FakeResponse:
        del url, headers, timeout
        captured["payload"] = json
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ChatClient(META_BASE_URL, "test-key", SPARK_MODEL)
    client.chat(
        [Message(role="user", content="hi")],
        max_tokens=100,
        reasoning_effort="minimal",
    )
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["reasoning_effort"] == "minimal"


def test_chat_omits_reasoning_effort_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "plan"}}]}

    def fake_post(
        url: str, headers: dict[str, str], json: dict[str, object], timeout: float
    ) -> FakeResponse:
        del url, headers, timeout
        captured["payload"] = json
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ChatClient(META_BASE_URL, "test-key", SPARK_MODEL)
    client.chat([Message(role="user", content="hi")], max_tokens=100)
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert "reasoning_effort" not in payload


def test_chat_sends_temperature_when_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "x"}}]}

    def fake_post(
        url: str, headers: dict[str, str], json: dict[str, object], timeout: float
    ) -> FakeResponse:
        del url, headers, timeout
        captured["payload"] = json
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ChatClient(META_BASE_URL, "test-key", SPARK_MODEL)
    client.chat([Message(role="user", content="hi")], max_tokens=100, temperature=0.0)
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["temperature"] == 0.0


def test_chat_omits_temperature_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "x"}}]}

    def fake_post(
        url: str, headers: dict[str, str], json: dict[str, object], timeout: float
    ) -> FakeResponse:
        del url, headers, timeout
        captured["payload"] = json
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ChatClient(META_BASE_URL, "test-key", SPARK_MODEL)
    client.chat([Message(role="user", content="hi")], max_tokens=100)
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert "temperature" not in payload


def test_chat_raises_on_transport_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(
        url: str, headers: dict[str, str], json: dict[str, object], timeout: float
    ) -> object:
        del url, headers, json, timeout
        raise httpx.ConnectError("down")

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ChatClient(META_BASE_URL, "test-key", SPARK_MODEL)
    with pytest.raises(LlmError, match="request failed"):
        client.chat([Message(role="user", content="hi")], max_tokens=10)


def test_chat_serializes_image_parts(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "1234"}}]}

    def fake_post(
        url: str, headers: dict[str, str], json: dict[str, object], timeout: float
    ) -> FakeResponse:
        del url, headers, timeout
        captured["messages"] = json["messages"]
        return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "post", fake_post)
    client = ChatClient(META_BASE_URL, "test-key", SPARK_MODEL)
    message = Message(
        role="user",
        content="read the meter",
        image=ImageAttachment(mime="image/png", b64="aGk="),
    )
    client.chat([message], max_tokens=10)
    assert captured["messages"] == [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "read the meter"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,aGk="},
                },
            ],
        }
    ]
