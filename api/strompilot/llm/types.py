"""Shared chat types for every model leg."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Message:
    """One chat turn."""

    role: str
    content: str


@dataclass(frozen=True)
class ChatResult:
    """A parsed chat reply with usage and the model that wrote it."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int


class LlmError(Exception):
    """Any model call failure: transport, status, or unreadable body."""


class ChatLeg(Protocol):
    """One callable model leg, real or stub."""

    model: str

    def chat(
        self,
        messages: list[Message],
        max_tokens: int,
        reasoning_effort: str | None = ...,
        temperature: float | None = ...,
    ) -> ChatResult: ...


class ChatRouter(Protocol):
    """Per-worker chat entry point, real or fake."""

    def chat(
        self,
        worker: str,
        messages: list[Message],
        max_tokens: int,
        reasoning_effort: str | None = ...,
        temperature: float | None = ...,
    ) -> ChatResult: ...
