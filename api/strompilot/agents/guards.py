"""Guard rails: caps, stall detection, cost rail, approval gate."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol

MAX_REVIEW_CYCLES = 3
STALL_REPEATS = 3
MAX_RUN_TOKENS = 200_000
MAX_RUN_COST_USD = 2.00


class GuardError(Exception):
    """A guard rail stopped the run before harm or waste."""


class SpendLike(Protocol):
    """Structural spend entry for the cost rail (see router.SpendEntry)."""

    @property
    def input_tokens(self) -> int: ...

    @property
    def output_tokens(self) -> int: ...

    @property
    def cost_usd(self) -> float | None: ...


def review_cap_reached(iterations: int, cap: int = MAX_REVIEW_CYCLES) -> bool:
    """Whether the critic has used up its review cycles."""
    return iterations >= cap


def has_stall(signatures: Sequence[str], repeats: int = STALL_REPEATS) -> bool:
    """Whether the latest calls repeat the identical signature."""
    return len(signatures) >= repeats and len(set(signatures[-repeats:])) == 1


def cost_rail_hit(entries: Sequence[SpendLike]) -> bool:
    """Whether the run spent too many tokens or too much money."""
    tokens = sum(entry.input_tokens + entry.output_tokens for entry in entries)
    cost = sum(entry.cost_usd for entry in entries if entry.cost_usd is not None)
    return tokens > MAX_RUN_TOKENS or cost > MAX_RUN_COST_USD


def approval_granted(approval: str) -> bool:
    """Whether a human approved the consequential step."""
    return approval == "approved"


def audit_event(node: str, detail: str) -> str:
    """Build one timestamped audit line for a node transition."""
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    return f"{stamp} {node}: {detail}"
