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
BODY_RETRIES = 1


class _Truncated(LlmError):
    """Internal signal: the model hit the length limit before answering."""


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

    @staticmethod
    def _to_wire(message: Message) -> dict[str, object]:
        """Serialize one turn, expanding an image to content parts."""
        if message.image is None:
            return {"role": message.role, "content": message.content}
        return {
            "role": message.role,
            "content": [
                {"type": "text", "text": message.content},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{message.image.mime};base64,{message.image.b64}"
                    },
                },
            ],
        }

    def _parse_body(self, response: httpx.Response, budget: int) -> ChatResult:
        """Parse one completion body, raising LlmError when unreadable."""
        try:
            body = response.json()
            choice = body["choices"][0]
            content = choice["message"]["content"]
            finish = choice.get("finish_reason")
            usage = body.get("usage", {})
            input_tokens = int(usage.get("prompt_tokens", 0))
            output_tokens = int(usage.get("completion_tokens", 0))
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LlmError("unreadable response body") from exc
        if not isinstance(content, str):
            details = usage.get("completion_tokens_details", {})
            reasoning = (
                details.get("reasoning_tokens", 0) if isinstance(details, dict) else 0
            )
            summary = (
                f"finish={finish} completion={output_tokens} reasoning={reasoning}"
            )
            if finish == "length":
                raise _Truncated(f"truncated at {budget} tokens ({summary})")
            raise LlmError(f"unreadable response body ({summary})")
        return ChatResult(
            content=content,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def chat(
        self,
        messages: list[Message],
        max_tokens: int,
        reasoning_effort: str | None = None,
        temperature: float | None = None,
    ) -> ChatResult:
        """Send one chat completion, raising LlmError on any failure.

        Reasoning models can spend the whole budget thinking, so
        callers pin reasoning_effort to bound the thinking first.
        A null body is retried once, with twice the budget when the
        first answer was cut off by the length limit.
        """
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [self._to_wire(message) for message in messages],
            "max_tokens": max_tokens,
        }
        if reasoning_effort is not None:
            payload["reasoning_effort"] = reasoning_effort
        if temperature is not None:
            payload["temperature"] = temperature
        attempts = BODY_RETRIES + 1
        budget = max_tokens
        while True:
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
                return self._parse_body(response, budget)
            except _Truncated:
                attempts -= 1
                if attempts <= 0:
                    raise
                budget *= 2
                payload["max_tokens"] = budget
            except LlmError:
                attempts -= 1
                if attempts <= 0:
                    raise
