"""Live eval pass: production vs challenger prompts with cross-model judges.

Reads META_API_KEY and BASEN_API_KEY from the environment, runs the
model-backed cases twice (production prompts, then challengers),
judges narrations with Spark Open on Baseten, checks every threshold,
and writes one timestamped JSON report into evals/results/.

Exit status is 0 only when the production pass clears all thresholds.
"""

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))

from dotenv import load_dotenv
from strompilot.agents.router import ModelRouter
from strompilot.evals.cases import load_cases
from strompilot.evals.runner import THRESHOLDS, compare_variants, run_live

LIVE_KINDS = ("extraction", "narration", "redteam")


def _mean(records: list[dict[str, Any]], key: str) -> float:
    values = [r[key] for r in records if isinstance(r.get(key), (int, float))]
    return sum(values) / len(values) if values else 0.0


def _verdict(name: str, value: float) -> dict[str, Any]:
    threshold = THRESHOLDS[name]
    return {"value": value, "threshold": threshold, "passed": value >= threshold}


def _summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        kind = record["kind"]
        by_kind.setdefault(kind, []).append(record)
    ext = by_kind.get("extraction", [])
    nar = by_kind.get("narration", [])
    red = by_kind.get("redteam", [])
    judge_min = min(
        (r.get("judge_score", 0) for r in nar),
        default=0,
    )
    checks = {
        "extraction.field_accuracy": _verdict(
            "extraction.field_accuracy", _mean(ext, "score")
        ),
        "narration.faithfulness": _verdict(
            "narration.faithfulness", _mean(nar, "faithfulness")
        ),
        "narration.judge_min": _verdict("narration.judge_min", float(judge_min)),
        "redteam.block_rate": _verdict(
            "redteam.block_rate",
            sum(1 for r in red if r["passed"]) / len(red) if red else 0.0,
        ),
    }
    return {"checks": checks, "passed": all(c["passed"] for c in checks.values())}


def main() -> int:
    """Run both passes, compare, report, and exit on the verdict."""
    load_dotenv(ROOT / ".env")
    meta_key = os.environ.get("META_API_KEY", "")
    baseten_key = os.environ.get("BASETEN_API_KEY", "")
    if not meta_key or not baseten_key:
        print("META_API_KEY and BASETEN_API_KEY must both be set.")
        return 2
    cases = load_cases(ROOT / "evals" / "cases.json")
    live = [c for c in cases if c.kind in LIVE_KINDS]
    prompts = {
        "extraction": (ROOT / "evals" / "prompts" / "challenger_extract.txt")
        .read_text(encoding="utf-8")
        .strip(),
        "narration": (ROOT / "evals" / "prompts" / "challenger_narrate.txt")
        .read_text(encoding="utf-8")
        .strip(),
    }
    router_a = ModelRouter.from_keys(meta_key, baseten_key)
    pass_a = run_live(live, router_a)
    router_b = ModelRouter.from_keys(meta_key, baseten_key)
    pass_b = run_live(live, router_b, system_prompts=prompts)
    pairs: list[tuple[str, float, float]] = []
    for rec_a, rec_b in zip(pass_a["records"], pass_b["records"], strict=True):
        if rec_a["kind"] != "narration":
            continue
        pairs.append(
            (
                rec_a["id"],
                float(rec_a.get("judge_score", 0)),
                float(rec_b.get("judge_score", 0)),
            )
        )
    comparison = compare_variants(pairs)
    summary_a = _summarize(pass_a["records"])
    summary_b = _summarize(pass_b["records"])
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    results_dir = ROOT / "evals" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "stamp": stamp,
        "production": {**pass_a, "summary": summary_a},
        "challenger": {**pass_b, "summary": summary_b},
        "comparison": comparison,
    }
    (results_dir / f"{stamp}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"production: {pass_a['passed']}/{pass_a['total']} cases passed")
    for name, check in summary_a["checks"].items():
        mark = "PASS" if check["passed"] else "FAIL"
        print(f"  [{mark}] {name}: {check['value']} >= {check['threshold']}")
    print(f"challenger: {pass_b['passed']}/{pass_b['total']} cases passed")
    print(f"narration A/B: {comparison}")
    print(f"report: evals/results/{stamp}.json")
    return 0 if summary_a["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
