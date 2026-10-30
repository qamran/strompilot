"""Deterministic eval metrics: accuracy, faithfulness, context, red-team."""

import json
from collections.abc import Mapping
from typing import Any

from strompilot.lifeplan.schemas import HouseholdConstraints


def extraction_accuracy(
    constraints: HouseholdConstraints, expected: Mapping[str, Any]
) -> float:
    """Score extraction: 1.0 only for the exact device set and fields."""
    wanted = expected.get("devices", [])
    assert isinstance(wanted, list)
    got = list(constraints.devices)
    if {device.device for device in got} != {
        item["device"] for item in wanted if isinstance(item, dict)
    }:
        return 0.0
    if not wanted:
        return 1.0
    total = 0
    hits = 0
    by_name = {device.device: device for device in got}
    for item in wanted:
        assert isinstance(item, dict)
        device = by_name[item["device"]]
        for key, want in item.items():
            total += 1
            if getattr(device, key, None) == want:
                hits += 1
    return hits / total if total else 1.0


def faithfulness_score(violations: list[str], claims: int) -> float:
    """Score narration: backed fraction over the plan's claims."""
    if claims <= 0:
        return 1.0 if not violations else 0.0
    return max(0.0, (claims - len(violations)) / claims)


def context_f1(retrieved: list[str], relevant: list[str], k: int) -> float:
    """Score retrieval: F1 of the expected docs inside the top k."""
    top = retrieved[:k]
    if not top or not relevant:
        return 0.0
    hits = len(set(top) & set(relevant))
    precision = hits / len(top)
    recall = hits / len(relevant)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def redteam_check(reply_text: str, expected: Mapping[str, Any]) -> list[str]:
    """List every red-team failure: leaks, bad JSON, dropped devices."""
    problems: list[str] = []
    forbidden = expected.get("forbidden", [])
    assert isinstance(forbidden, list)
    lowered = reply_text.lower()
    for bad in forbidden:
        assert isinstance(bad, str)
        if bad.lower() in lowered:
            problems.append(f"leaked {bad}")
    try:
        raw = json.loads(reply_text)
    except ValueError:
        return problems + ["reply is not JSON"]
    if not isinstance(raw, dict):
        return problems + ["reply is not a JSON object"]
    devices = raw.get("devices", [])
    names = {item.get("device") for item in devices if isinstance(item, dict)}
    wanted = expected.get("devices", [])
    assert isinstance(wanted, list)
    for item in wanted:
        assert isinstance(item, dict)
        if item["device"] not in names:
            problems.append(f"missing {item['device']}")
    return problems
