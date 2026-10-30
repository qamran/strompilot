"""Eval dataset loader: typed cases with strict validation."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

KINDS = frozenset({"extraction", "narration", "schedule", "retrieval", "redteam"})


@dataclass(frozen=True)
class EvalCase:
    """One eval case: id, kind, model input, and expected result."""

    id: str
    kind: str
    input: Any
    expected: dict[str, Any]


def load_cases(path: Path) -> list[EvalCase]:
    """Load and validate the JSON dataset, failing fast on bad cases."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases", [])
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError(f"{path}: dataset holds no cases")
    cases: list[EvalCase] = []
    seen: set[str] = set()
    for raw in raw_cases:
        case_id = raw.get("id", "?")
        kind = raw.get("kind", "?")
        if kind not in KINDS:
            raise ValueError(f"{path}: case {case_id} has unknown kind {kind!r}")
        if not isinstance(raw.get("expected"), dict):
            raise ValueError(f"{path}: case {case_id} has no expected object")
        if case_id in seen:
            raise ValueError(f"{path}: duplicate case id {case_id!r}")
        seen.add(case_id)
        cases.append(
            EvalCase(
                id=case_id,
                kind=kind,
                input=raw.get("input"),
                expected=raw["expected"],
            )
        )
    return cases
