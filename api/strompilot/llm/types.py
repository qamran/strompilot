"""Shared chat types for every model leg."""

from dataclasses import dataclass


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
