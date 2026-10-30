"""Cross-model judge: Spark Open scores Spark outputs on Baseten."""

import json
import re
from typing import Any

from strompilot.evals.cases import EvalCase
from strompilot.llm.client import LOW_EFFORT
from strompilot.llm.types import ChatRouter, Message

JUDGE_TOKENS = 1200

_JUDGE_SYSTEM = """You judge one German energy-plan output against its expected
result. Score 0-5: 5 means every time, price, cost, and device matches
exactly; 3 means broadly right with small errors; 0 means wrong or
unsafe. Reply exactly two lines, no more:
SCORE: <0-5>
RATIONALE: <one short line>"""

_SCORE_RE = re.compile(r"^SCORE:\s*(\d+)\s*$")


def parse_judge_reply(content: str) -> tuple[int, str]:
    """Parse one judge reply strictly into score plus rationale."""
    lines = [line.strip() for line in content.strip().splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError(f"judge reply needs SCORE plus RATIONALE: {content!r}")
    match = _SCORE_RE.match(lines[0])
    if match is None:
        raise ValueError(f"judge reply needs a SCORE line: {content!r}")
    score = int(match.group(1))
    if score < 0 or score > 5:
        raise ValueError(f"judge SCORE out of range 0-5: {content!r}")
    rationale = lines[1]
    if not rationale.startswith("RATIONALE:"):
        raise ValueError(f"judge reply needs a RATIONALE line: {content!r}")
    return score, rationale.removeprefix("RATIONALE:").strip()


def judge_output(
    router: ChatRouter, case: EvalCase, output_text: str
) -> tuple[int, str, str]:
    """Score one output through the judge worker, returning score and model."""
    expected: dict[str, Any] = case.expected
    user = (
        f"Case {case.id} ({case.kind}).\n"
        f"Expected: {json.dumps(expected, ensure_ascii=False)}\n"
        f"Output:\n{output_text}"
    )
    messages = [
        Message(role="system", content=_JUDGE_SYSTEM),
        Message(role="user", content=user),
    ]
    result = router.chat("judge", messages, JUDGE_TOKENS, LOW_EFFORT, 0.0)
    score, rationale = parse_judge_reply(result.content)
    return score, rationale, result.model
