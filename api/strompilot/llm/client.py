"""One OpenAI-compatible chat client for all three model legs."""

import httpx

from .types import ChatResult, LlmError, Message

META_BASE_URL = "https://api.meta.ai/v1"
BASETEN_BASE_URL = "https://inference.baseten.co/v1"
SPARK_MODEL = "muse-spark-1.3"
WONDER_MODEL = "muse-wonder-1.0"
SPARK_OPEN_MODEL = "meta-models/muse-spark-open-1026"
MINIMAL_EFFORT = "minimal"
LOW_EFFORT = "low"
TIMEOUT_SECONDS = 60.0


class ChatClient:
    """Posts chat completions and parses content plus usage."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self.model = model
        self._timeout = timeout

    def chat(
        self,
        messages: list[Message],
        max_tokens: int,
        reasoning_effort: str | None = None,
    ) -> ChatResult:
        """Send one chat completion, raising LlmError on any failure.

        Reasoning models can spend the whole budget thinking, so
        callers pin reasoning_effort to bound the thinking first.
        """
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "max_tokens": max_tokens,
        }
        if reasoning_effort is not None:
            payload["reasoning_effort"] = reasoning_effort
        try:
            response = httpx.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise LlmError(f"request failed: {exc}") from exc
        if response.status_code != 200:
            raise LlmError(f"HTTP {response.status_code} from {self._base_url}")
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            usage = body.get("usage", {})
            input_tokens = int(usage.get("prompt_tokens", 0))
            output_tokens = int(usage.get("completion_tokens", 0))
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LlmError("unreadable response body") from exc
        if not isinstance(content, str):
            raise LlmError("unreadable response body")
        return ChatResult(
            content=content,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
