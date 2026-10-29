"""Model router: per-worker legs, per-call fallback, spend log."""

from dataclasses import dataclass

from strompilot.llm.client import (
    BASETEN_BASE_URL,
    META_BASE_URL,
    SPARK_MODEL,
    SPARK_OPEN_MODEL,
    WONDER_MODEL,
    ChatClient,
)
from strompilot.llm.types import (
    ChatLeg,
    ChatResult,
    ChatRouter,
    LlmError,
    Message,
)
from strompilot.safety import redact

from .guards import GuardError, cost_rail_hit, has_stall

__all__ = ["ChatLeg", "ChatRouter", "ModelRouter", "SpendEntry"]

# Standard-mode USD per 1M tokens, from the Meta pricing docs. The
# Baseten leg has no pinned rate, so its entries record tokens only.
_PRICES = {
    SPARK_MODEL: (1.25, 4.25),
    WONDER_MODEL: (4.00, 20.00),
}


@dataclass(frozen=True)
class SpendEntry:
    """One completed model call with its priced cost, if known."""

    worker: str
    requested_model: str
    actual_model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float | None


def _cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Price one call in USD, or None when the leg has no pinned rate."""
    rates = _PRICES.get(model)
    if rates is None:
        return None
    input_rate, output_rate = rates
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000


class ModelRouter:
    """Pins each worker to a leg, falls back per call, logs spend.

    Call new_run before each planning run, or use one router per run:
    spend and stall tracking accumulate on the instance.
    """

    def __init__(self, legs: dict[str, tuple[ChatLeg, ChatLeg | None]]) -> None:
        self._legs = legs
        self._recent_signatures: list[str] = []
        self.spend_log: list[SpendEntry] = []

    def new_run(self) -> None:
        """Reset spend and stall tracking for the next planning run."""
        self.spend_log.clear()
        self._recent_signatures.clear()

    @classmethod
    def from_keys(cls, meta_key: str, baseten_key: str) -> "ModelRouter":
        """Build the production routing from the register."""
        spark = ChatClient(META_BASE_URL, meta_key, SPARK_MODEL)
        wonder = ChatClient(META_BASE_URL, meta_key, WONDER_MODEL)
        spark_open = ChatClient(BASETEN_BASE_URL, baseten_key, SPARK_OPEN_MODEL)
        # The scheduler is deterministic since SP-05, so it owns no leg.
        return cls(
            {
                "supervisor": (spark, None),
                "analyst": (spark, None),
                "explainer": (spark_open, spark),
                "critic": (wonder, spark),
                "watcher": (spark_open, spark),
            }
        )

    def chat(
        self,
        worker: str,
        messages: list[Message],
        max_tokens: int,
        reasoning_effort: str | None = None,
        temperature: float | None = None,
    ) -> ChatResult:
        """Run one worker call with fallback, rails, and spend logging."""
        if worker not in self._legs:
            known = ", ".join(sorted(self._legs))
            raise ValueError(f"unknown worker {worker!r}; known: {known}")
        messages = [
            Message(role=message.role, content=redact(message.content).text)
            for message in messages
        ]
        primary, fallback = self._legs[worker]
        attempts = [primary] if fallback is None else [primary, fallback]
        if fallback is None:
            attempts.append(primary)
        result: ChatResult | None = None
        last_error: LlmError | None = None
        for leg in attempts:
            try:
                result = leg.chat(messages, max_tokens, reasoning_effort, temperature)
                break
            except LlmError as exc:
                last_error = exc
        if result is None:
            assert last_error is not None
            raise last_error
        entry = SpendEntry(
            worker=worker,
            requested_model=primary.model,
            actual_model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=_cost_usd(result.model, result.input_tokens, result.output_tokens),
        )
        self.spend_log.append(entry)
        self._recent_signatures.append(self._signature(worker, messages))
        if has_stall(self._recent_signatures):
            raise GuardError("run paused: repeated identical calls")
        if cost_rail_hit(self.spend_log):
            raise GuardError("run stopped: cost rail hit")
        return result

    @staticmethod
    def _signature(worker: str, messages: list[Message]) -> str:
        """Identify a call by worker plus its latest turn."""
        last = messages[-1] if messages else Message(role="", content="")
        return f"{worker}:{last.role}:{last.content.strip()}"
