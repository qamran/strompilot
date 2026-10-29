"""Shared fakes for agent tests."""

from strompilot.llm.client import SPARK_MODEL
from strompilot.llm.types import ChatResult, Message


def reply(
    content: str,
    model: str = SPARK_MODEL,
    input_tokens: int = 10,
    output_tokens: int = 5,
) -> ChatResult:
    """Build a scripted chat reply."""
    return ChatResult(
        content=content,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


class StubLeg:
    """Scripted model leg that records its calls."""

    def __init__(self, model: str, script: list[ChatResult | Exception]) -> None:
        self.model = model
        self._script = list(script)
        self.calls: list[list[Message]] = []
        self.efforts: list[str | None] = []

    def chat(
        self,
        messages: list[Message],
        max_tokens: int,
        reasoning_effort: str | None = None,
    ) -> ChatResult:
        del max_tokens
        self.calls.append(messages)
        self.efforts.append(reasoning_effort)
        if not self._script:
            raise AssertionError(f"no scripted reply left for {self.model}")
        next_up = self._script.pop(0)
        if isinstance(next_up, Exception):
            raise next_up
        return next_up


class FakeRouter:
    """Scripted per-worker router for worker and graph tests."""

    def __init__(self, scripts: dict[str, list[ChatResult | Exception]]) -> None:
        self._scripts = {worker: list(script) for worker, script in scripts.items()}
        self.calls: list[str] = []
        self.efforts: list[str | None] = []
        self.prompts: list[str] = []

    def chat(
        self,
        worker: str,
        messages: list[Message],
        max_tokens: int,
        reasoning_effort: str | None = None,
    ) -> ChatResult:
        del max_tokens
        self.calls.append(worker)
        self.efforts.append(reasoning_effort)
        self.prompts.append(
            "\n".join(f"{message.role}: {message.content}" for message in messages)
        )
        script = self._scripts.get(worker, [])
        if not script:
            raise AssertionError(f"no scripted reply left for {worker}")
        next_up = script.pop(0)
        if isinstance(next_up, Exception):
            raise next_up
        return next_up
