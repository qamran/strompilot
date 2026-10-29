"""Model legs: one chat client plus shared types."""

from .client import (
    BASETEN_BASE_URL,
    META_BASE_URL,
    SPARK_MODEL,
    SPARK_OPEN_MODEL,
    WONDER_MODEL,
    ChatClient,
)
from .types import ChatResult, LlmError, Message

__all__ = [
    "BASETEN_BASE_URL",
    "META_BASE_URL",
    "SPARK_MODEL",
    "SPARK_OPEN_MODEL",
    "WONDER_MODEL",
    "ChatClient",
    "ChatResult",
    "LlmError",
    "Message",
]
